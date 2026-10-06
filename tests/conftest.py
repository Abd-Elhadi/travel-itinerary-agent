import pytest

from travel_agent.models import (
    Activity, ActivityPlan, StayOption, StayPlan, TransportOption, TransportPlan, TripRequest,
)


@pytest.fixture
def trip():
    return TripRequest(
        trip_type="leisure", passport_country="France", origin="Miami", destination="Japan",
        start_date="2026-10-26", end_date="2026-11-01", num_days=7, travelers=3,
        budget_usd=6000.0, interests=["food", "temples"], meeting_address=None,
        needs_car_rental=None,
    )


@pytest.fixture
def transport():
    return TransportPlan(
        options=[
            TransportOption(mode="flight", description="a", cost_usd_total=3000, is_estimate=True),
            TransportOption(mode="flight", description="b", cost_usd_total=3500, is_estimate=True),
            TransportOption(mode="train", description="c", cost_usd_total=300, is_estimate=True),
        ],
        notes="",
    )


@pytest.fixture
def stay():
    return StayPlan(
        options=[
            StayOption(name="h1", area="Kyoto", total_cost_usd=1200, why="w", is_estimate=True),
            StayOption(name="h2", area="Tokyo", total_cost_usd=2000, why="w", is_estimate=True),
        ],
        notes="",
    )


@pytest.fixture
def activities():
    return ActivityPlan(
        destination="Japan", weather_summary="mild",
        activities=[
            Activity(name="Temple", category="tourism.sights", city="Kyoto", why="w",
                     estimated_cost_usd=10, duration_hours=2, from_tool=True),
            Activity(name="Ramen", category="Food", city="Kyoto", why="w",
                     estimated_cost_usd=20, duration_hours=1, from_tool=True),
        ],
    )