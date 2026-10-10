from travel_agent.budget import build_budget_report
from travel_agent.models import (
    Activity,
    ActivityPlan,
    StayOption,
    StayPlan,
    TransportOption,
    TransportPlan,
    TripRequest,
)


def test_budget_calculates_group_total():
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

    transport = TransportPlan(
        options=[
            TransportOption(mode="flight", description="Sample return flights", cost_usd_total=2400, is_estimate=True),
            TransportOption(mode="local", description="Sample rail and local transport", cost_usd_total=450, is_estimate=True),
        ],
        notes="Sample transport data.",
    )

    stay = StayPlan(
        options=[
            StayOption(name="Sample Kyoto Guesthouse", area="Kyoto", total_cost_usd=510, why="Sample value option.", is_estimate=True)
        ],
        notes="Sample stay estimate.",
    )

    activities = ActivityPlan(
        destination="Japan",
        weather_summary="Sample weather summary.",
        activities=[
            Activity(name="Sample Temple", category="tourism.sights", city="Kyoto", why="Matches temple interest.",
                     estimated_cost_usd=20, duration_hours=2, from_tool=True),
            Activity(name="Sample Food Tour", category="food", city="Kyoto", why="Matches food interest.",
                     estimated_cost_usd=90, duration_hours=3, from_tool=False),
        ],
    )

    report = build_budget_report(trip=trip, transport=transport, stay=stay, activities=activities)

    assert report.flights_usd == 2400
    assert report.stay_usd == 510
    assert report.local_transport_usd == 450
    assert report.activities_usd == 60    # temple 20 x 3 travelers; food category skipped
    assert report.food_usd == 945         # 45 x 3 travelers x 7 days
    assert report.total_usd == 4365
    assert report.within_budget is True
    assert report.remaining_usd == 1635


def test_multi_city_stay_costs_are_summed():
    trip = TripRequest(
        trip_type="leisure",
        passport_country="France",
        origin="Miami",
        destination="Kathmandu, Pokhara",
        start_date="2026-10-26",
        end_date="2026-11-01",
        num_days=7,
        travelers=3,
        budget_usd=6000,
        interests=["food", "temples"],
        meeting_address=None,
        needs_car_rental=None,
    )
    transport = TransportPlan(options=[], notes="")
    stay = StayPlan(
        options=[
            StayOption(name="KTM Hotel", area="Kathmandu", total_cost_usd=720, why="w", is_estimate=True),
            StayOption(name="PKR Hotel", area="Pokhara", total_cost_usd=720, why="w", is_estimate=True),
        ],
        notes="",
    )
    activities = ActivityPlan(destination="Kathmandu, Pokhara", weather_summary="", activities=[])
    report = build_budget_report(trip=trip, transport=transport, stay=stay, activities=activities)
    assert report.stay_usd == 1440