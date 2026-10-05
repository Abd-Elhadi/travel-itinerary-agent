import pytest

from travel_agent.agents.stay_agent import run_stay_agent
from travel_agent.models import TripRequest


@pytest.mark.asyncio
async def test_stay_returns_options():
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

    stay = await run_stay_agent(trip)

    assert len(stay.options) > 0
    assert stay.options[0].name
    assert stay.options[0].area
    assert stay.options[0].total_cost_usd is not None
    assert stay.options[0].is_estimate is True
    assert "sample" in stay.notes.lower()