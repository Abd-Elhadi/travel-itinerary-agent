from travel_agent.cities import parse_cities
from travel_agent.models import (
    ActivityPlan,
    BudgetReport,
    StayPlan,
    TransportPlan,
    TripRequest,
)

FOOD_PER_PERSON_PER_DAY_USD = 45.0  # demo assumption, covers all meals


def _is_meal(category: str) -> bool:
    c = category.lower()
    return any(word in c for word in ("food", "restaurant", "catering", "cafe"))


def build_budget_report(
    trip: TripRequest,
    transport: TransportPlan,
    stay: StayPlan,
    activities: ActivityPlan,
) -> BudgetReport:
    """Group-level budget estimate.

    Options are alternatives, so only the first option of each kind is counted.
    Activity costs are treated as per person. Meal activities are skipped because
    the food line already covers meals.
    """
    travelers = trip.travelers or 1
    num_days = trip.num_days or 1

    flights_usd = next(
        (o.cost_usd_total for o in transport.options if o.mode == "flight"), 0.0
    )
    local_transport_usd = next(
        (o.cost_usd_total for o in transport.options if o.mode != "flight"), 0.0
    )

    stay_usd = 0.0
    multi_city = len(parse_cities(trip.destination)) > 1
    if stay.options:
        if multi_city:
            stay_usd = sum(o.total_cost_usd or 0.0 for o in stay.options)
        elif stay.options[0].total_cost_usd is not None:
            stay_usd = stay.options[0].total_cost_usd

    activities_usd = travelers * sum(
        a.estimated_cost_usd or 0.0
        for a in activities.activities
        if not _is_meal(a.category)
    )

    food_usd = FOOD_PER_PERSON_PER_DAY_USD * travelers * num_days

    total_usd = round(
        flights_usd + stay_usd + activities_usd + local_transport_usd + food_usd, 2
    )
    budget_usd = trip.budget_usd or 0.0

    return BudgetReport(
        flights_usd=round(flights_usd, 2),
        stay_usd=round(stay_usd, 2),
        activities_usd=round(activities_usd, 2),
        local_transport_usd=round(local_transport_usd, 2),
        food_usd=round(food_usd, 2),
        total_usd=total_usd,
        budget_usd=budget_usd,
        within_budget=total_usd <= budget_usd,
        remaining_usd=round(budget_usd - total_usd, 2),
    )