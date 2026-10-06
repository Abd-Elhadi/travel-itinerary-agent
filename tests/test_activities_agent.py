import pytest

from travel_agent.agents.activities_agent import run_activities_agent
from travel_agent.models import TripRequest


@pytest.mark.live
@pytest.mark.asyncio
async def test_activities_returns_plan():
    trip = TripRequest(
        trip_type="leisure",
        passport_country="France",
        origin="Miami",
        destination="Japan",
        start_date="2026-10-20",
        end_date="2026-10-26",
        num_days=7,
        travelers=3,
        budget_usd=6000,
        interests=["food", "temples"],
        meeting_address=None,
        needs_car_rental=None,
    )

    plan = await run_activities_agent(trip)

    assert plan.destination
    assert plan.weather_summary
    assert len(plan.activities) > 0

    for activity in plan.activities:
        assert activity.name
        assert activity.category
        assert activity.why
        assert isinstance(activity.from_tool, bool)