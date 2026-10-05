from datetime import date

from agents import Agent, Runner

from travel_agent.config import MODEL
from travel_agent.models import ActivityPlan, TripRequest
from travel_agent.tools.places_tool import search_places
from travel_agent.tools.weather_tool import get_weather


INSTRUCTIONS = f"""You are the activities agent for a travel-planning application.
Today is {date.today().isoformat()}.

Input contains destination, dates, travelers, budget, interests, and trip type.

1. Choose 1 to 3 suitable destination cities based on the destination,
   trip length, and interests. If the destination is already a city, use it.
2. If start_date and end_date are available, call get_weather for the first
   selected city. If either date is null, do not call weather and state that
   weather was not checked.
3. Call search_places for each selected city, choosing categories that match
   the user's interests.
4. Return an ActivityPlan with 6 to 10 activities when tool data permits.
   Return fewer if tool data is limited; never invent places.
5. Set from_tool=true only for activities returned by search_places.
6. estimated_cost_usd and duration_hours are estimates; use null when unknown.
7. Prefer outdoor activities on low-rain days and mention weather in
   weather_summary.
8. For business trips, suggest activities under 3 hours near the city center.
9. If a tool returns mock/sample data, say so clearly in the activity's
   why field.
"""


activities_agent = Agent(
    name="Activities",
    instructions=INSTRUCTIONS,
    model=MODEL,
    tools=[search_places, get_weather],
    output_type=ActivityPlan,
)


async def run_activities_agent(trip: TripRequest) -> ActivityPlan:
    """Run the Activities agent from a completed TripRequest."""

    if not trip.destination:
        raise ValueError("Activities requires a destination.")

    prompt = (
        f"Destination: {trip.destination}. "
        f"Start date: {trip.start_date}. "
        f"End date: {trip.end_date}. "
        f"Number of days: {trip.num_days}. "
        f"Travelers: {trip.travelers}. "
        f"Budget USD: {trip.budget_usd}. "
        f"Interests: {', '.join(trip.interests) or 'general sightseeing'}. "
        f"Trip type: {trip.trip_type}."
    )

    result = await Runner.run(activities_agent, prompt)
    return result.final_output