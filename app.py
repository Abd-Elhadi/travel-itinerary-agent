from datetime import date, timedelta
from pathlib import Path
import asyncio
import logging
import sys


# Allow root-level app.py to import the package from src/.
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


import gradio as gr
from agents import InputGuardrailTripwireTriggered, Runner

import travel_agent.config
from travel_agent.agents.intake_agent import intake_agent
from travel_agent.email_service import (
    check_email_configuration,
    send_plan_email,
    validate_recipient,
)
from travel_agent.models import IntakeResult, TripPlan, TripRequest
from travel_agent.pipeline import REQUIRED, build_plan


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def empty_state():
    return {
        "agent_history": [],
        "trip": None,
        "ready": False,
    }


def normalize_dates(trip: TripRequest) -> TripRequest:
    trip = trip.model_copy(deep=True)

    if trip.start_date and trip.end_date:
        start = date.fromisoformat(trip.start_date)
        end = date.fromisoformat(trip.end_date)

        if end < start:
            raise ValueError(
                "The end date must not be before the start date."
            )

        trip.num_days = (end - start).days + 1

    elif trip.start_date and trip.num_days:
        if trip.num_days < 1:
            raise ValueError("The trip must last at least one day.")

        start = date.fromisoformat(trip.start_date)
        trip.end_date = (
            start + timedelta(days=trip.num_days - 1)
        ).isoformat()

    return trip


def check_readiness(out: IntakeResult, trip: TripRequest):
    missing = list(out.missing_fields)

    for field in REQUIRED:
        if getattr(trip, field) in (None, "") and field not in missing:
            missing.append(field)

    if trip.trip_type == "leisure" and not trip.interests:
        if "interests" not in missing:
            missing.append("interests")

    if trip.trip_type == "business":
        for field in ("meeting_address", "needs_car_rental"):
            if (
                getattr(trip, field) in (None, "")
                and field not in missing
            ):
                missing.append(field)

    problems = []

    if trip.travelers is not None and trip.travelers < 1:
        problems.append("Travelers must be at least 1.")

    if trip.num_days is not None and trip.num_days < 1:
        problems.append("Trip duration must be at least 1 day.")

    if trip.budget_usd is not None and trip.budget_usd <= 0:
        problems.append("Budget must be greater than 0 USD.")

    ready = out.is_complete and not missing and not problems
    return ready, missing, problems


def format_itinerary(plan: TripPlan) -> str:
    itinerary = plan.itinerary

    lines = [
        f"# {itinerary.title}",
        "",
        itinerary.summary,
        "",
        "## Visa information",
        itinerary.visa_note,
        "",
        "## Daily itinerary",
    ]

    for day in itinerary.days:
        label = f"Day {day.day}"

        if day.date:
            label += f" — {day.date}"

        label += f" — {day.city}"

        lines.extend(["", f"### {label}"])
        lines.extend(f"- {item}" for item in day.items)

    lines.extend([
        "",
        "## Planning notes",
        itinerary.budget_note,
        "",
        "## Weather",
        plan.activities.weather_summary,
    ])

    if plan.transport.notes:
        lines.extend([
            "",
            "## Transport notes",
            plan.transport.notes,
        ])

    if plan.stay.notes:
        lines.extend([
            "",
            "## Accommodation notes",
            plan.stay.notes,
        ])

    if plan.warnings:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in plan.warnings)

    return "\n".join(lines)


def format_budget(plan: TripPlan) -> str:
    budget = plan.budget

    status = (
        "Within budget"
        if budget.within_budget
        else "Over budget"
    )
    balance_label = (
        "Remaining"
        if budget.within_budget
        else "Over by"
    )
    balance = abs(budget.remaining_usd)

    lines = [
        f"## {status}",
        "",
        "| Category | Whole-group cost (USD) |",
        "|---|---:|",
        f"| Flights | ${budget.flights_usd:,.2f} |",
        f"| Accommodation | ${budget.stay_usd:,.2f} |",
        f"| Activities | ${budget.activities_usd:,.2f} |",
        (
            "| Local transport / car rental | "
            f"${budget.local_transport_usd:,.2f} |"
        ),
        f"| Food | ${budget.food_usd:,.2f} |",
        f"| Total estimate | ${budget.total_usd:,.2f} |",
        f"| Your budget | ${budget.budget_usd:,.2f} |",
        f"| {balance_label} | ${balance:,.2f} |",
        "",
        "Costs are estimates for the whole group and trip.",
        "",
        "The existing budget calculation counts the first flight option, "
        "the first non-flight transport option, and the first stay option.",
        "",
        "Non-meal activity costs are multiplied by the traveler count.",
        "",
        "Food uses your project's demo assumption of "
        "$45 per person per day.",
        "",
        "A $0 category may mean no priced option was available"
        "—not that it is free.",
    ]

    if any(option.is_estimate for option in plan.transport.options):
        lines.append(
            "\nSome transport options are marked as estimates."
        )

    if any(option.is_estimate for option in plan.stay.options):
        lines.append(
            "\nSome accommodation options are marked as estimates."
        )

    if plan.warnings:
        lines.extend(["", "### Budget completeness warnings"])
        lines.extend(f"- {warning}" for warning in plan.warnings)

    return "\n".join(lines)


async def send_message(message, chat_history, state):
    message = (message or "").strip()
    state = state or empty_state()
    chat_history = list(chat_history or [])

    if not message:
        raise gr.Error("Enter a travel message first.")

    new_chat = chat_history + [
        {"role": "user", "content": message}
    ]

    try:
        agent_input = state["agent_history"] + [
            {"role": "user", "content": message}
        ]

        result = await Runner.run(intake_agent, agent_input)
        out = result.final_output

        if not isinstance(out, IntakeResult):
            raise TypeError(
                "Intake did not return an IntakeResult."
            )

        trip = normalize_dates(out.trip)
        ready, missing, problems = check_readiness(out, trip)

        reply = out.next_question or (
            "Your trip details are complete. Click Build plan."
            if ready
            else "Please provide the remaining trip details."
        )

        if missing:
            reply += "\n\nStill needed: " + ", ".join(missing)

        if problems:
            reply += "\n\n" + "\n".join(problems)

        new_state = {
            "agent_history": result.to_input_list(),
            "trip": trip.model_dump(mode="json"),
            "ready": ready,
        }

        new_chat.append({
            "role": "assistant",
            "content": reply,
        })

        status = (
            "Trip ready. Click Build plan."
            if ready
            else "Collecting trip details."
        )

        # Clear results and email status after an accepted Intake turn.
        return (
            "",
            new_chat,
            new_state,
            new_state["trip"],
            status,
            gr.Button(interactive=ready),
            "",
            "",
            None,
            "",
        )

    except InputGuardrailTripwireTriggered:
        new_chat.append({
            "role": "assistant",
            "content": (
                "Please keep this conversation about travel planning."
            ),
        })

        return (
            "",
            new_chat,
            state,
            state["trip"],
            "Message blocked by the travel guardrail.",
            gr.Button(interactive=state["ready"]),
            gr.skip(),
            gr.skip(),
            gr.skip(),
            gr.skip(),
        )

    except Exception:
        logger.exception("Intake failed")

        raise gr.Error(
            "Intake failed. Check the terminal for details, "
            "then retry your message."
        )


async def generate_plan(state, recipient, email_requested):
    if not state or not state["ready"] or not state["trip"]:
        raise gr.Error(
            "Complete the Intake conversation first."
        )

    # Validate email settings before spending time generating a plan.
    if email_requested:
        try:
            recipient = validate_recipient(recipient)
            check_email_configuration()
        except ValueError as exc:
            raise gr.Error(str(exc)) from exc

    # Clear previously generated results while rebuilding.
    yield (
        "",
        "",
        "Generating your itinerary and budget...",
        None,
        (
            "Email will be sent after successful plan generation."
            if email_requested
            else "Email not requested."
        ),
    )

    try:
        trip = TripRequest.model_validate(state["trip"])
        plan = await build_plan(trip)

        itinerary_text = format_itinerary(plan)
        budget_text = format_budget(plan)
        plan_data = plan.model_dump(mode="json")

    except Exception:
        logger.exception("Plan generation failed")

        raise gr.Error(
            "Plan generation failed. Check the terminal for details. "
            "Your trip details are still available for a retry."
        )

    status = (
        f"Plan generated with {len(plan.warnings)} warning(s)."
        if plan.warnings
        else "Plan generated successfully."
    )

    if not email_requested:
        yield (
            itinerary_text,
            budget_text,
            status,
            plan_data,
            "Email not requested.",
        )
        return

    # Display the generated plan before starting SMTP delivery.
    yield (
        itinerary_text,
        budget_text,
        status,
        plan_data,
        f"Sending report to {recipient}...",
    )

    try:
        await asyncio.to_thread(
            send_plan_email,
            recipient,
            plan,
        )

        email_result = (
            f"Report accepted by the email server for {recipient}. "
            "Check the inbox and spam folder."
        )

    except Exception:
        logger.exception("Email delivery failed")

        email_result = (
            "The plan was generated, but email delivery failed. "
            "Check the terminal for details. "
            "Your itinerary and budget remain available."
        )

    yield (
        itinerary_text,
        budget_text,
        status,
        plan_data,
        email_result,
    )


def reset_ui():
    return (
        "",
        [],
        empty_state(),
        None,
        "Describe your trip to begin.",
        gr.Button(interactive=False),
        "",
        "",
        None,
        "",
        "",
        False,
    )


with gr.Blocks(title="Travel Itinerary Assistant") as demo:
    gr.Markdown(
        "# Travel Itinerary Assistant\n"
        "Chat to collect your trip details, then generate an itinerary "
        "and estimated budget. Search and recommendations only—no bookings."
    )

    state = gr.State(empty_state())

    with gr.Row():
        with gr.Column(scale=1):
            chatbot = gr.Chatbot(
                label="Intake chat",
                height=480,
            )

            message = gr.Textbox(
                label="Your message",
                placeholder=(
                    "I want to visit Japan with 2 friends starting "
                    "October 26 for 7 days, budget 6000 USD."
                ),
                lines=2,
            )

            with gr.Row():
                send_button = gr.Button(
                    "Send",
                    variant="primary",
                )
                reset_button = gr.Button("Reset")

            gr.Markdown("### Optional email report")

            recipient_email = gr.Textbox(
                label="Recipient email",
                placeholder="you@example.com",
                lines=1,
            )

            email_requested = gr.Checkbox(
                label=(
                    "Email this itinerary, budget, and trip details "
                    "to the address above when I click Build plan"
                ),
                value=False,
            )

            gr.Markdown(
                "Check the recipient address before building. "
                "Leave the checkbox off to generate without emailing."
            )

            build_button = gr.Button(
                "Build plan",
                variant="primary",
                interactive=False,
            )

            status = gr.Markdown(
                "Describe your trip to begin."
            )

            email_status = gr.Markdown()

            with gr.Accordion(
                "Collected trip details",
                open=False,
            ):
                trip_json = gr.JSON(label="Trip request")

        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.Tab("Itinerary"):
                    itinerary_output = gr.Markdown()

                with gr.Tab("Budget"):
                    budget_output = gr.Markdown()

                with gr.Tab("Raw plan"):
                    plan_json = gr.JSON(
                        label="Complete plan"
                    )

    intake_inputs = [
        message,
        chatbot,
        state,
    ]

    intake_outputs = [
        message,
        chatbot,
        state,
        trip_json,
        status,
        build_button,
        itinerary_output,
        budget_output,
        plan_json,
        email_status,
    ]

    reset_outputs = intake_outputs + [
        recipient_email,
        email_requested,
    ]

    # Serialize actions to avoid overlapping state changes.
    event_settings = {
        "concurrency_id": "travel-ui",
        "concurrency_limit": 1,
    }

    send_button.click(
        send_message,
        inputs=intake_inputs,
        outputs=intake_outputs,
        **event_settings,
    )

    message.submit(
        send_message,
        inputs=intake_inputs,
        outputs=intake_outputs,
        **event_settings,
    )

    build_button.click(
        generate_plan,
        inputs=[
            state,
            recipient_email,
            email_requested,
        ],
        outputs=[
            itinerary_output,
            budget_output,
            status,
            plan_json,
            email_status,
        ],
        **event_settings,
    )

    reset_button.click(
        reset_ui,
        inputs=[],
        outputs=reset_outputs,
        **event_settings,
    )


if __name__ == "__main__":
    demo.queue().launch(
        server_name="127.0.0.1",
        share=False,
    )