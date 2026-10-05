from travel_agent.models import (
    ActivityPlan,
    BudgetReport,
    StayPlan,
    TransportPlan,
    TripRequest,
)


def build_budget_report(
    trip: TripRequest,
    transport: TransportPlan,
    stay: StayPlan,
    activities: ActivityPlan,
) -> BudgetReport:
    """Create a transparent group-level trip budget estimate."""

    flights_usd = sum(
        option.cost_usd_total
        for option in transport.options
        if option.mode == "flight"
    )

    local_transport_usd = sum(
        option.cost_usd_total
        for option in transport.options
        if option.mode in {"car_rental", "train", "local"}
    )

    stay_usd = 0.0
    if stay.options and stay.options[0].total_cost_usd is not None:
        stay_usd = stay.options[0].total_cost_usd

    activities_usd = sum(
        activity.estimated_cost_usd or 0.0
        for activity in activities.activities
    )

    travelers = trip.travelers or 1
    num_days = trip.num_days or 1

    # Transparent demo assumption: $45 per traveler per day for food.
    food_usd = round(travelers * num_days * 45.0, 2)

    total_usd = round(
        flights_usd
        + stay_usd
        + activities_usd
        + local_transport_usd
        + food_usd,
        2,
    )

    budget_usd = trip.budget_usd or 0.0
    remaining_usd = round(budget_usd - total_usd, 2)

    return BudgetReport(
        flights_usd=round(flights_usd, 2),
        stay_usd=round(stay_usd, 2),
        activities_usd=round(activities_usd, 2),
        local_transport_usd=round(local_transport_usd, 2),
        food_usd=food_usd,
        total_usd=total_usd,
        budget_usd=budget_usd,
        within_budget=total_usd <= budget_usd,
        remaining_usd=remaining_usd,
    )