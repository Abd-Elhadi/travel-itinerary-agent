import asyncio
import json

from agents import OutputGuardrailTripwireTriggered, Runner, trace

from travel_agent.agents.activities_agent import run_activities_agent
from travel_agent.agents.planner_agent import planner_agent
from travel_agent.agents.stay_agent import run_stay_agent
from travel_agent.agents.transport_agent import transport_agent
from travel_agent.agents.visa_agent import visa_agent
from travel_agent.airports import AirportNotFound, resolve_airport
from travel_agent.budget import build_budget_report
from travel_agent.cities import allocate_parts, expand_city_plan, parse_cities
from travel_agent.guardrails import PlanContext
from travel_agent.models import (
    ActivityPlan,
    Itinerary,
    StayPlan,
    TransportPlan,
    TripPlan,
    TripRequest,
    VisaResult,
)
from travel_agent.render import _usd

REQUIRED = [
    "trip_type", "passport_country", "origin", "destination",
    "start_date", "end_date", "num_days", "travelers", "budget_usd",
]
MAX_PLANNER_ATTEMPTS = 2


def _check(trip: TripRequest) -> None:
    missing = [f for f in REQUIRED if getattr(trip, f) in (None, "")]
    if missing:
        raise ValueError(f"Trip incomplete, missing: {missing}")


async def _visa(trip: TripRequest) -> VisaResult:
    prompt = f"Passport: {trip.passport_country}. Destination: {trip.destination}."
    result = await Runner.run(visa_agent, prompt)
    return result.final_output


async def _activities(
    trip: TripRequest,
    cities: list[str],
    days_per_city: list[int] | None = None,
) -> ActivityPlan:
    return await run_activities_agent(trip, cities=cities, days_per_city=days_per_city)


async def _stay(trip: TripRequest) -> StayPlan:
    return await run_stay_agent(trip)


async def _transport(
    trip: TripRequest, origin_iata: str | None, destination_iata: str | None
) -> TransportPlan:
    if not origin_iata or not destination_iata:
        return TransportPlan(options=[], notes="Airport codes missing. Flights not searched.")
    payload = {
        **trip.model_dump(),
        "origin": origin_iata,
        "destination": destination_iata,
        "origin_name": trip.origin,
        "destination_name": trip.destination,
    }
    result = await Runner.run(transport_agent, json.dumps(payload))
    return result.final_output


async def _plan(payload: dict, ctx: PlanContext, warnings: list[str]) -> Itinerary:
    """Run the Planner. If the output guardrail fails, retry once with the problems listed."""
    last_problems: list[str] = []
    last_output: Itinerary | None = None

    for _ in range(MAX_PLANNER_ATTEMPTS):
        try:
            result = await Runner.run(planner_agent, json.dumps(payload), context=ctx)
            return result.final_output
        except OutputGuardrailTripwireTriggered as exc:
            last_output = exc.guardrail_result.agent_output
            last_problems = exc.guardrail_result.output.output_info["problems"]
            payload = {**payload, "fix_these_problems": last_problems}

    warnings.append("Itinerary failed checks after retry: " + " | ".join(last_problems))
    return last_output


def _unwrap(result, name: str, default, warnings: list[str]):
    if isinstance(result, Exception):
        warnings.append(f"{name} failed: {type(result).__name__}: {result}")
        return default
    return result


async def build_plan(
    trip: TripRequest,
    origin_iata: str | None = None,
    destination_iata: str | None = None,
) -> TripPlan:
    _check(trip)
    warnings: list[str] = []

    try:
        origin_iata = origin_iata or resolve_airport(trip.origin)
        destination_iata = destination_iata or resolve_airport(trip.destination)
    except AirportNotFound as exc:
        origin_iata = destination_iata = None
        warnings.append(str(exc))

    with trace("Plan trip"):
        # Stage 1: independent specialists run in parallel.
        visa_r, transport_r, stay_r = await asyncio.gather(
            _visa(trip),
            _transport(trip, origin_iata, destination_iata),
            _stay(trip),
            return_exceptions=True,
        )
        visa = _unwrap(
            visa_r, "Visa",
            VisaResult(
                passport=trip.passport_country or "", destination=trip.destination or "",
                requirement="unknown", allowed_days=None,
                summary="Visa check failed. Verify on the destination's official government site.",
                source="mock",
            ),
            warnings,
        )
        transport = _unwrap(
            transport_r, "Transport", TransportPlan(options=[], notes="Transport search failed."), warnings
        )
        stay = _unwrap(stay_r, "Stay", StayPlan(options=[], notes="Stay search failed."), warnings)

        parsed_cities = parse_cities(trip.destination)
        multi_city = len(parsed_cities) > 1
        if multi_city:
            stay_cities = parsed_cities
        elif stay.options:
            stay_cities = [stay.options[0].area]
        else:
            stay_cities = parsed_cities

        days_per_city = allocate_parts(trip.num_days or 1, max(len(stay_cities), 1))
        city_plan = expand_city_plan(stay_cities, trip.num_days or 1)
        base_city = stay_cities[0] if stay_cities else None

        try:
            activities = await _activities(trip, stay_cities, days_per_city)
        except Exception as exc:
            warnings.append(f"Activities failed: {type(exc).__name__}: {exc}")
            activities = ActivityPlan(
                destination=trip.destination or "", weather_summary="Not available.", activities=[]
            )

        if not any(o.mode == "flight" for o in transport.options):
            warnings.append("No flight options. Budget excludes flights.")
        if not stay.options:
            warnings.append("No stay options. Budget excludes accommodation.")
        if not activities.activities:
            warnings.append("No activities found. Itinerary will mostly be free time.")

        budget = build_budget_report(trip, transport, stay, activities)
        raw_budget = budget.model_dump()
        budget_display = {
            **raw_budget,
            **{k: _usd(v) for k, v in raw_budget.items() if k.endswith("_usd")},
        }

        other_stay_names = [] if multi_city else [o.name for o in stay.options[1:]]

        # Stage 3: planner writes the itinerary; the output guardrail checks it.
        ctx = PlanContext(
            num_days=trip.num_days,
            base_city=base_city,
            total_usd=budget.total_usd,
            visa_needs_verification=visa.source == "mock" or visa.requirement == "unknown",
            other_stay_names=other_stay_names,
            city_plan=city_plan,
        )
        itinerary = await _plan(
            {
                "trip": trip.model_dump(),
                "visa": visa.model_dump(),
                "activities": activities.model_dump(),
                "transport": transport.model_dump(),
                "stay": stay.model_dump(),
                "budget": budget.model_dump(),
                "budget_display": budget_display,
                "warnings": warnings,
                "city_plan": city_plan,
            },
            ctx,
            warnings,
        )

    return TripPlan(
        trip=trip, visa=visa, activities=activities, transport=transport,
        stay=stay, budget=budget, itinerary=itinerary, warnings=warnings,
    )