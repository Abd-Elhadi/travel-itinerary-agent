from agents import Agent, WebSearchTool

from datetime import date

from travel_agent.config import MODEL
from travel_agent.models import ActivityPlan
from travel_agent.tools.places import search_places
from travel_agent.tools.weather import get_weather

INSTRUCTIONS = f"""You are the activities agent. Input: destination, dates, travelers, budget, interests, trip type.
Today is {date.today().isoformat()}.
1. If start_date and end_date are set, call get_weather for the first city. If they are null, skip weather and say it was not checked.
2. The destination may be a country. Pick 1 to 3 cities that fit the interests and trip length. Call search_places for each city.
3. Use web search only for current events or gaps the places tool cannot fill.
4. Return ActivityPlan with 6 to 10 activities. Set from_tool true for places tool results, false for web search.
5. estimated_cost_usd and duration_hours are estimates; use null when unknown.
6. Prefer outdoor activities on low rain days. Mention the weather in weather_summary.
7. For business trips, suggest short activities (under 3 hours) near the city center.
Never invent places that come from neither tool."""

activities_agent = Agent(
    name="Activities",
    instructions=INSTRUCTIONS,
    model=MODEL,
    tools=[search_places, get_weather, WebSearchTool()],
    output_type=ActivityPlan,
)