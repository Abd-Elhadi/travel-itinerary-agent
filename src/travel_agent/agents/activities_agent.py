import asyncio
from datetime import date

from agents import Agent, Runner

from travel_agent.cities import allocate_parts, parse_cities
from travel_agent.config import MODEL
from travel_agent.models import ActivityPlan, TripRequest
from travel_agent.tools.places_tool import search_places
from travel_agent.tools.rag_tool import search_destination_knowledge
from travel_agent.tools.weather_tool import get_weather

INSTRUCTIONS = f"""You are the activities agent for a travel-planning application.
Today is {date.today().isoformat()}.

Input contains destination, cities to search, dates, number of days in this city,
travelers, budget, interests, and trip type.

1. Search only the given city. Do not switch to a suburb or a different city.
2. If start_date and end_date are set, call get_weather for the city. If either
   is null, skip weather and say it was not checked.
3. Call search_destination_knowledge for the city with queries matching the traveler's interests 
   to retrieve rich qualitative context, hidden gems, local tips, and top attractions.
4. Call search_places for the city with categories that match the interests:
- temples, shrines, churches, religion: religion.place_of_worship
- sights, culture, landmarks, history: tourism.attraction
- food, restaurants: catering.restaurant
- museums, art: entertainment.museum
- parks, nature: leisure.park
   Make at least 5 calls with limit 20 each.
5. Return between 2 x num_days and 3 x num_days activities, restaurants included,
   when tool data permits. Never invent places. Skip places a traveler would not
   visit, such as government offices, parking, and generic statues or memorials.
6. Set city to the city searched. Set from_tool=true for every place that came
   from search_places or search_destination_knowledge.
7. estimated_cost_usd is a typical per person entry fee or meal cost in USD.
   Use 0 for free places and null only if truly unknown. duration_hours is an estimate.
8. Prefer outdoor activities on low-rain days and mention weather in weather_summary.
9. For business trips, suggest activities under 3 hours near the city center.
10. If a tool returns mock or sample data, say so in the activity why field.
"""

_tools = [search_places, get_weather, search_destination_knowledge]

activities_agent = Agent(
    name="Activities",
    instructions=INSTRUCTIONS,
    model=MODEL,
    tools=_tools,
    output_type=ActivityPlan,
)


async def _run_city(trip: TripRequest, city: str, num_days: int) -> ActivityPlan:
    interests = ", ".join(trip.interests) or "general sightseeing"
    prompt = (
        f"Destination: {trip.destination}. "
        f"City to search: {city}. "
        f"Start date: {trip.start_date}. "
        f"End date: {trip.end_date}. "
        f"Number of days in this city: {num_days}. "
        f"Travelers: {trip.travelers}. "
        f"Budget USD: {trip.budget_usd}. "
        f"Interests: {interests}. "
        f"Trip type: {trip.trip_type}."
    )
    result = await Runner.run(activities_agent, prompt)
    return result.final_output


async def run_activities_agent(
    trip: TripRequest,
    cities: list[str] | None = None,
    days_per_city: list[int] | None = None,
    base_city: str | None = None,
) -> ActivityPlan:
    """Run the Activities agent for one or more cities."""

    if not trip.destination:
        raise ValueError("Activities requires a destination.")

    if not cities:
        if base_city:
            cities = [base_city]
        else:
            cities = parse_cities(trip.destination)
    if not cities:
        raise ValueError("Activities requires a city.")

    if days_per_city is None or len(days_per_city) != len(cities):
        days_per_city = allocate_parts(trip.num_days or 1, len(cities))

    if len(cities) == 1:
        return await _run_city(trip, cities[0], days_per_city[0])

    plans = await asyncio.gather(
        *[_run_city(trip, city, days) for city, days in zip(cities, days_per_city)]
    )
    activities = [item for plan in plans for item in plan.activities]
    weather = " ".join(plan.weather_summary for plan in plans if plan.weather_summary)
    return ActivityPlan(
        destination=trip.destination or "",
        weather_summary=weather or "Not available.",
        activities=activities,
    )