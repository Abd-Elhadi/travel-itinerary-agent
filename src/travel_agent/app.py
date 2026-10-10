import asyncio
import logging
from pathlib import Path
import uuid

import gradio as gr
from agents import InputGuardrailTripwireTriggered, Runner, SQLiteSession

import travel_agent.config  # noqa: F401 (loads .env and sets the API key)
from travel_agent.agents.intake_agent import intake_agent
from travel_agent.email_service import (
    check_email_configuration,
    send_plan_email,
    validate_recipient,
)
from travel_agent.memory import ProfileStore
from travel_agent.models import TripRequest
from travel_agent.pipeline import build_plan
from travel_agent.render import render_plan_markdown

ROOT = Path(__file__).resolve().parents[2]
SESSIONS_DB = ROOT / "data" / "sessions.db"  # keep in .gitignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WELCOME = (
    "Hi! Tell me about your trip: where you want to go, for how long, who is traveling, "
    "and your budget."
)


def new_state() -> dict:
    return {"session_id": f"ui-{uuid.uuid4().hex[:8]}", "trip": None, "profile_sent": False}


def _clean_user(user_id: str | None) -> str:
    return (user_id or "").strip().lower() or "demo"


async def handle_message(message, chat, state, user_id, store: ProfileStore):
    message = (message or "").strip()
    chat = list(chat or [])
    if not message:
        return chat, "", state, gr.update(interactive=state.get("trip") is not None)

    text = message
    if not state["profile_sent"]:
        profile = store.as_text(_clean_user(user_id))
        if profile:
            text = f"{message}\n\n(Saved traveler profile. Use it as defaults and confirm it with me: {profile})"
        state["profile_sent"] = True

    SESSIONS_DB.parent.mkdir(parents=True, exist_ok=True)
    session = SQLiteSession(state["session_id"], str(SESSIONS_DB))

    chat.append({"role": "user", "content": message})
    try:
        result = await Runner.run(intake_agent, text, session=session)
    except InputGuardrailTripwireTriggered as exc:
        reason = exc.guardrail_result.output.output_info.reason
        chat.append({"role": "assistant", "content": f"I can only help with trip planning. {reason}"})
        return chat, "", state, gr.update(interactive=state.get("trip") is not None)

    out = result.final_output
    state["trip"] = out.trip.model_dump() if out.is_complete else None
    reply = out.next_question or "I have everything I need. Click Build plan."
    chat.append({"role": "assistant", "content": reply})
    return chat, "", state, gr.update(interactive=out.is_complete)


async def handle_build(state, user_id, recipient_email, email_requested, store: ProfileStore):
    if not state.get("trip"):
        yield "Finish the trip details in the chat first.", "", "Email not requested.", gr.update(interactive=False)
        return

    if email_requested:
        try:
            recipient = validate_recipient(recipient_email)
            check_email_configuration()
        except ValueError as exc:
            yield f"Email configuration error: {exc}", "", "Email validation failed.", gr.update(interactive=True)
            return

    trip = TripRequest(**state["trip"])
    user = _clean_user(user_id)

    yield "Planning your trip. This takes about a minute.", "", "Email pending plan generation.", gr.update(interactive=False)
    try:
        plan = await build_plan(trip)
    except Exception as exc:
        logger.exception("Plan generation failed")
        yield f"Planning failed: {type(exc).__name__}: {exc}", "", "Email not sent due to planning failure.", gr.update(interactive=True)
        return

    store.save_from_trip(user, trip)
    store.save_trip(user, trip, plan.budget.total_usd)
    profile = store.as_text(user) or ""
    plan_md = render_plan_markdown(plan)

    if not email_requested:
        yield plan_md, f"**Saved profile:** {profile}", "Email not requested.", gr.update(interactive=True)
        return

    yield plan_md, f"**Saved profile:** {profile}", f"Sending report to {recipient}...", gr.update(interactive=False)

    try:
        await asyncio.to_thread(send_plan_email, recipient, plan)
        email_result = f"Report accepted by the email server for {recipient}. Check inbox and spam folder."
    except Exception:
        logger.exception("Email delivery failed")
        email_result = "The plan was generated, but email delivery failed. Check terminal for details."

    yield plan_md, f"**Saved profile:** {profile}", email_result, gr.update(interactive=True)


def build_demo(store: ProfileStore | None = None) -> gr.Blocks:
    store = store or ProfileStore()

    async def _send(message, chat, state, user_id):
        return await handle_message(message, chat, state, user_id, store)

    async def _build(state, user_id, recipient_email, email_requested):
        async for update in handle_build(state, user_id, recipient_email, email_requested, store):
            yield update

    def _reset():
        return (
            [{"role": "assistant", "content": WELCOME}],
            "",
            new_state(),
            gr.update(interactive=False),
            "The plan appears here.",
            "",
            "",
            False,
        )

    with gr.Blocks(title="Smart Travel Itinerary Assistant") as demo:
        gr.Markdown(
            "# Smart Travel Itinerary Assistant\n"
            "Describe your trip in the chat. When the details are complete, click Build plan."
        )
        state = gr.State(new_state)
        with gr.Row():
            with gr.Column(scale=1):
                user_id = gr.Textbox(label="Traveler name (used for the saved profile)", value="demo")
                chatbot = gr.Chatbot(
                    value=[{"role": "assistant", "content": WELCOME}], height=420, label="Trip chat"
                )
                box = gr.Textbox(placeholder="Type your message and press Enter", show_label=False)
                with gr.Row():
                    send = gr.Button("Send", variant="primary")
                    build = gr.Button("Build plan", interactive=False)
                    reset = gr.Button("New trip")

                gr.Markdown("### Optional email report")
                recipient_email = gr.Textbox(label="Recipient email", placeholder="you@example.com", lines=1)
                email_requested = gr.Checkbox(
                    label="Email this itinerary, budget, and trip details to the address above when I click Build plan",
                    value=False,
                )
                email_status = gr.Markdown()
                profile_md = gr.Markdown()

            with gr.Column(scale=1):
                plan_md = gr.Markdown("The plan appears here.")

        send.click(_send, [box, chatbot, state, user_id], [chatbot, box, state, build])
        box.submit(_send, [box, chatbot, state, user_id], [chatbot, box, state, build])
        build.click(
            _build,
            [state, user_id, recipient_email, email_requested],
            [plan_md, profile_md, email_status, build],
        )
        reset.click(
            _reset,
            None,
            [chatbot, box, state, build, plan_md, profile_md, recipient_email, email_requested],
        )

    return demo


if __name__ == "__main__":
    build_demo().launch()