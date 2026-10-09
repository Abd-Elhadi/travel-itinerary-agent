import asyncio

from agents import RunContextWrapper

from travel_agent.agents.intake_agent import intake_agent
from travel_agent.agents.planner_agent import planner_agent
from travel_agent.guardrails import PlanContext, check_itinerary, itinerary_guardrail
from travel_agent.models import DayPlan, Itinerary


def _ctx(**overrides):
    base = dict(
        num_days=2, base_city="Kyoto", total_usd=4380.0,
        visa_needs_verification=True, other_stay_names=["Sample Tokyo City Hotel"],
    )
    base.update(overrides)
    return PlanContext(**base)


def _itinerary(**overrides):
    base = dict(
        title="Kyoto trip",
        summary="Two days of temples and food.",
        visa_note="Visa free for 90 days. Please verify on the official government site.",
        days=[
            DayPlan(day=1, date="2026-10-26", city="Kyoto", items=["Arrive", "Tenryu-ji Temple"]),
            DayPlan(day=2, date="2026-10-27", city="Kyoto", items=["Depart"]),
        ],
        budget_note="Total $4,380.00 against a $6,000 budget. Within budget.",
    )
    base.update(overrides)
    return Itinerary(**base)


def test_good_itinerary_has_no_problems():
    assert check_itinerary(_itinerary(), _ctx()) == []


def test_wrong_day_count():
    problems = check_itinerary(_itinerary(), _ctx(num_days=7))
    assert any("expected 7" in p for p in problems)


def test_wrong_city():
    days = [DayPlan(day=1, date=None, city="Kyoto", items=["a"]),
            DayPlan(day=2, date=None, city="Tokyo", items=["b"])]
    problems = check_itinerary(_itinerary(days=days), _ctx())
    assert any("Tokyo" in p for p in problems)


def test_alternative_hotel_mentioned():
    days = [DayPlan(day=1, date=None, city="Kyoto", items=["Check in at Sample Tokyo City Hotel"]),
            DayPlan(day=2, date=None, city="Kyoto", items=["Depart"])]
    problems = check_itinerary(_itinerary(days=days), _ctx())
    assert any("Alternative hotel" in p for p in problems)


def test_budget_note_must_contain_total():
    problems = check_itinerary(_itinerary(budget_note="Within budget."), _ctx())
    assert any("budget_note" in p for p in problems)


def test_visa_note_must_say_verify_when_mock():
    problems = check_itinerary(_itinerary(visa_note="Visa free for 90 days."), _ctx())
    assert any("visa_note" in p for p in problems)
    assert check_itinerary(_itinerary(visa_note="Visa free for 90 days."), _ctx(visa_needs_verification=False)) == []


def test_invented_preference_is_flagged():
    problems = check_itinerary(_itinerary(summary="No day trips, as per your preference."), _ctx())
    assert any("preference" in p for p in problems)


def test_output_guardrail_function_trips_on_problems():
    ctx = RunContextWrapper(context=_ctx(num_days=7))
    result = asyncio.run(itinerary_guardrail.guardrail_function(ctx, planner_agent, _itinerary()))
    assert result.tripwire_triggered is True
    assert result.output_info["problems"]


def test_guardrails_are_attached():
    assert len(intake_agent.input_guardrails) == 1
    assert len(planner_agent.output_guardrails) == 1