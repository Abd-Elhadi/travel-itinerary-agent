import asyncio
from types import SimpleNamespace

from agents import GuardrailFunctionOutput, InputGuardrailTripwireTriggered
from agents.guardrail import InputGuardrailResult

from travel_agent import app
from travel_agent.guardrails import TravelInputCheck, travel_input_guardrail
from travel_agent.memory import ProfileStore
from travel_agent.models import (
    BudgetReport, DayPlan, IntakeResult, Itinerary, TripPlan, VisaResult,
)
from travel_agent.render import render_plan_markdown


def _intake(trip, complete):
    return IntakeResult(
        trip=trip,
        missing_fields=[] if complete else ["origin"],
        next_question=None if complete else "Where are you flying from?",
        is_complete=complete,
    )


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "SESSIONS_DB", tmp_path / "sessions.db")
    return ProfileStore(tmp_path / "memory.db")


def _plan(trip, transport, stay, activities):
    return TripPlan(
        trip=trip,
        visa=VisaResult(passport="FRA", destination="JPN", requirement="visa_free",
                        allowed_days=90, summary="ok", source="orizn_api"),
        activities=activities, transport=transport, stay=stay,
        budget=BudgetReport(flights_usd=2400, stay_usd=1020, activities_usd=0, local_transport_usd=0,
                            food_usd=945, total_usd=4365, budget_usd=6000, within_budget=True,
                            remaining_usd=1635),
        itinerary=Itinerary(
            title="Kyoto Leisure Trip", summary="A week of temples and food.",
            visa_note="Visa free for 90 days. Please verify on the official site.",
            days=[DayPlan(day=1, date="2026-10-26", city="Kyoto", items=["Arrive", "Fushimi Inari Taisha"])],
            budget_note="Total $4,365.00 within a $6,000.00 budget.",
        ),
        warnings=["Example warning"],
    )


def test_render_contains_key_sections(trip, transport, stay, activities):
    md = render_plan_markdown(_plan(trip, transport, stay, activities))
    assert "## Kyoto Leisure Trip" in md
    assert "| Total | $4,365.00 |" in md
    assert "**Day 1 (2026-10-26), Kyoto**" in md
    assert "- Fushimi Inari Taisha" in md
    assert "### Warnings" in md


def test_demo_builds(tmp_path):
    demo = app.build_demo(ProfileStore(tmp_path / "memory.db"))
    assert demo is not None


def test_message_incomplete_then_complete(monkeypatch, tmp_path, trip):
    store = _setup(monkeypatch, tmp_path)
    replies = iter([_intake(trip, False), _intake(trip, True)])
    seen = []

    async def fake_run(agent, input, session=None):
        seen.append(input)
        return SimpleNamespace(final_output=next(replies))

    monkeypatch.setattr(app.Runner, "run", fake_run)
    state = app.new_state()

    chat, box, state, build = asyncio.run(app.handle_message("Japan please", [], state, "omar", store))
    assert chat[-1]["content"] == "Where are you flying from?"
    assert state["trip"] is None
    assert build["interactive"] is False

    chat, box, state, build = asyncio.run(app.handle_message("Miami", chat, state, "omar", store))
    assert state["trip"]["destination"] == "Japan"
    assert build["interactive"] is True
    assert "Build plan" in chat[-1]["content"]


def test_saved_profile_is_added_to_first_message_only(monkeypatch, tmp_path, trip):
    store = _setup(monkeypatch, tmp_path)
    store.save_from_trip("omar", trip)
    seen = []

    async def fake_run(agent, input, session=None):
        seen.append(input)
        return SimpleNamespace(final_output=_intake(trip, False))

    monkeypatch.setattr(app.Runner, "run", fake_run)
    state = app.new_state()
    chat, _, state, _ = asyncio.run(app.handle_message("Plan a trip", [], state, "omar", store))
    asyncio.run(app.handle_message("Japan", chat, state, "omar", store))
    assert "passport France" in seen[0]
    assert seen[1] == "Japan"


def test_blocked_message_shows_reason(monkeypatch, tmp_path):
    store = _setup(monkeypatch, tmp_path)

    async def fake_run(agent, input, session=None):
        check = TravelInputCheck(on_topic=False, unsafe=False, reason="This is not about travel.")
        result = InputGuardrailResult(
            guardrail=travel_input_guardrail,
            output=GuardrailFunctionOutput(output_info=check, tripwire_triggered=True),
        )
        raise InputGuardrailTripwireTriggered(result)

    monkeypatch.setattr(app.Runner, "run", fake_run)
    chat, _, state, build = asyncio.run(app.handle_message("Write a poem", [], app.new_state(), "omar", store))
    assert "only help with trip planning" in chat[-1]["content"]
    assert "not about travel" in chat[-1]["content"]
    assert build["interactive"] is False


def test_build_saves_memory_and_renders(monkeypatch, tmp_path, trip, transport, stay, activities):
    store = _setup(monkeypatch, tmp_path)
    plan = _plan(trip, transport, stay, activities)

    async def fake_build(t):
        return plan

    monkeypatch.setattr(app, "build_plan", fake_build)
    state = {**app.new_state(), "trip": trip.model_dump()}

    async def collect():
        return [u async for u in app.handle_build(state, "omar", "", False, store)]

    updates = asyncio.run(collect())
    assert "Planning your trip" in updates[0][0]
    assert "## Kyoto Leisure Trip" in updates[-1][0]
    assert "Japan (7 days)" in updates[-1][1]
    assert store.load("omar")["passport_country"] == "France"


def test_build_failure_is_shown_not_raised(monkeypatch, tmp_path, trip):
    store = _setup(monkeypatch, tmp_path)

    async def broken(t):
        raise RuntimeError("boom")

    monkeypatch.setattr(app, "build_plan", broken)
    state = {**app.new_state(), "trip": trip.model_dump()}

    async def collect():
        return [u async for u in app.handle_build(state, "omar", "", False, store)]

    updates = asyncio.run(collect())
    assert "Planning failed: RuntimeError: boom" in updates[-1][0]


def test_build_without_trip_asks_to_finish_chat(tmp_path):
    store = ProfileStore(tmp_path / "memory.db")

    async def collect():
        return [u async for u in app.handle_build(app.new_state(), "omar", "", False, store)]

    updates = asyncio.run(collect())
    assert "Finish the trip details" in updates[0][0]