from datetime import date

from agents import Agent, Runner, WebSearchTool

from travel_agent.config import MODEL
from travel_agent.models import ActivityPlan, TripRequest
from travel_agent.tools.places_tool import search_places
from travel_agent.tools.weather_tool import get_weather

# Web search fills gaps with well-known attractions. It costs more per run.
USE_WEB_SEARCH = True


INSTRUCTIONS = f"""You are the activities agent for a travel-planning application.
Today is {date.today().isoformat()}.

Input contains destination, base city, dates, number of days, travelers, budget, interests, and trip type.

1. If a base city is given, use only that city. Otherwise choose one suitable
   city in the destination for the interests.
2. If start_date and end_date are set, call get_weather for the city. If either
   is null, skip weather and say it was not checked.
3. Call search_places for the city with categories that match the interests:
   - temples, shrines, churches, religion: religion.place_of_worship
   - sights, culture, landmarks, history: tourism.attraction
   - food, restaurants: catering.restaurant
   - museums, art: entertainment.museum
   - parks, nature: leisure.park
   Make at least 5 calls with limit 20 each.
4. Return between 2 x num_days and 3 x num_days activities, restaurants included,
   when tool data permits. Never invent places. Skip places a traveler would not
   visit, such as government offices, parking, and generic statues or memorials.
5. If search_places gives too few well-known attractions and web search is
   available, add famous attractions of the city from web search and set from_tool=false.
6. Set city to the city searched. Set from_tool=true for every place that came
   from search_places.
7. estimated_cost_usd is a typical per person entry fee or meal cost in USD.
   Use 0 for free places and null only if truly unknown. duration_hours is an estimate.
8. Prefer outdoor activities on low-rain days and mention weather in weather_summary.
9. For business trips, suggest activities under 3 hours near the city center.
10. If a tool returns mock or sample data, say so in the activity why field.
"""


_tools = [search_places, get_weather]
if USE_WEB_SEARCH:
    _tools.append(WebSearchTool())

activities_agent = Agent(
    name="Activities",
    instructions=INSTRUCTIONS,
    model=MODEL,
    tools=_tools,
    output_type=ActivityPlan,
)


async def run_activities_agent(trip: TripRequest, base_city: str | None = None) -> ActivityPlan:
    """Run the Activities agent. base_city is the hotel city, when known."""

    if not trip.destination:
        raise ValueError("Activities requires a destination.")

    interests = ", ".join(trip.interests) or "general sightseeing"
    prompt = (
        f"Destination: {trip.destination}. "
        f"Base city: {base_city or 'not set'}. "
        f"Start date: {trip.start_date}. "
        f"End date: {trip.end_date}. "
        f"Number of days: {trip.num_days}. "
        f"Travelers: {trip.travelers}. "
        f"Budget USD: {trip.budget_usd}. "
        f"Interests: {interests}. "
        f"Trip type: {trip.trip_type}."
    )

    result = await Runner.run(activities_agent, prompt)
    return result.final_output