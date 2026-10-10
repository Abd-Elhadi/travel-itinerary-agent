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


def _days(*item_lists):
    return [DayPlan(day=i + 1, date=None, city="Kyoto", items=items) for i, items in enumerate(item_lists)]


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


def test_city_plan_requires_planned_order():
    ctx = _ctx(
        num_days=4,
        city_plan=["Kathmandu", "Kathmandu", "Pokhara", "Pokhara"],
        other_stay_names=[],
    )
    days = [
        DayPlan(day=1, date=None, city="Kathmandu", items=["Arrive"]),
        DayPlan(day=2, date=None, city="Kathmandu", items=["Temple"]),
        DayPlan(day=3, date=None, city="Pokhara", items=["Lake"]),
        DayPlan(day=4, date=None, city="Pokhara", items=["Depart"]),
    ]
    assert check_itinerary(_itinerary(days=days), ctx) == []

    bad_days = list(days)
    bad_days[2] = DayPlan(day=3, date=None, city="Baudha", items=["Lake"])
    problems = check_itinerary(_itinerary(days=bad_days), ctx)
    assert any("Baudha" in p and "Pokhara" in p for p in problems)


def test_alternative_hotel_mentioned():
    days = _days(["Check in at Sample Tokyo City Hotel"], ["Depart"])
    problems = check_itinerary(_itinerary(days=days), _ctx())
    assert any("Alternative hotel" in p for p in problems)


def test_budget_note_must_contain_total():
    problems = check_itinerary(_itinerary(budget_note="Within budget."), _ctx())
    assert any("budget_note" in p for p in problems)


def test_visa_note_must_say_verify():
    problems = check_itinerary(_itinerary(visa_note="Visa free for 90 days."), _ctx())
    assert any("visa_note" in p for p in problems)
    assert check_itinerary(_itinerary(visa_note="Visa free for 90 days."), _ctx(visa_needs_verification=False)) == []


def test_invented_preference_is_flagged():
    problems = check_itinerary(_itinerary(summary="No day trips, as per your preference."), _ctx())
    assert any("preference" in p for p in problems)


def test_repeated_place_is_flagged_across_meal_labels():
    days = _days(
        ["Lunch at Marumaru Seimen"],
        ["Dinner at Marumaru Seimen (Marumaru Noodle Shop)"],
    )
    problems = check_itinerary(_itinerary(days=days), _ctx())
    assert any("repeats an earlier activity" in p for p in problems)


def test_repeated_free_time_and_hotel_lines_are_allowed():
    days = _days(
        ["Arrival at KIX", "Free time", "Check in at Sample Kyoto Guesthouse"],
        ["Free time", "Check out of Sample Kyoto Guesthouse", "Departure flight"],
    )
    assert check_itinerary(_itinerary(days=days), _ctx()) == []


def test_leaked_reasoning_is_flagged():
    days = _days(
        ["Dinner at Nouvelle Bar (to fill meal options, as no repeats allowed, adjusted to free time)"],
        ["Depart"],
    )
    problems = check_itinerary(_itinerary(days=days), _ctx())
    assert any("no repeat" in p or "adjusted to" in p for p in problems)


def test_source_endorsement_is_flagged():
    note = "Visa free. Orizn is reliable. Please verify on the official site."
    problems = check_itinerary(_itinerary(visa_note=note), _ctx())
    assert any("reliable" in p for p in problems)


def test_output_guardrail_function_trips_on_problems():
    ctx = RunContextWrapper(context=_ctx(num_days=7))
    result = asyncio.run(itinerary_guardrail.guardrail_function(ctx, planner_agent, _itinerary()))
    assert result.tripwire_triggered is True
    assert result.output_info["problems"]


def test_guardrails_are_attached():
    assert len(intake_agent.input_guardrails) == 1
    assert len(planner_agent.output_guardrails) == 1