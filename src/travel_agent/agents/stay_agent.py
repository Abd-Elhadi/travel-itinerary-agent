from agents import Agent, Runner

from travel_agent.config import MODEL
from travel_agent.models import StayPlan, TripRequest
from travel_agent.tools.stay_tool import search_stays


INSTRUCTIONS = """You are the accommodation specialist for a travel-planning application.

Call search_stays exactly once using the destination, hotel nights, and number
of travelers in the input.

Rules:
1. Return only the required structured StayPlan output.
2. Preserve the accommodation names, areas, costs, and reasons from the tool.
3. If the destination has more than one city, the tool returns one hotel per
   city in visit order. Keep that order. Those stays are sequential, not
   alternatives.
4. If the destination is a single city, order options from best value to more
   expensive. Later options are alternatives.
5. State in notes that all prices are sample estimates, not booking prices.
6. State that final hotel cost depends on dates, room count, taxes, and
   availability.
7. Never claim a property is available. Never book anything.
"""


stay_agent = Agent(
    name="Stay",
    instructions=INSTRUCTIONS,
    model=MODEL,
    tools=[search_stays],
    output_type=StayPlan,
)


async def run_stay_agent(trip: TripRequest) -> StayPlan:
    """Run the Stay agent from a completed TripRequest."""

    if not trip.destination:
        raise ValueError("Stay planning requires a destination.")

    nights = max((trip.num_days or 1) - 1, 1)

    prompt = (
        f"Destination: {trip.destination}. "
        f"Trip duration: {trip.num_days} days. "
        f"Hotel nights: {nights}. "
        f"Travelers: {trip.travelers}. "
        f"Budget USD: {trip.budget_usd}. "
        f"Interests: {', '.join(trip.interests) or 'general travel'}."
    )

    result = await Runner.run(stay_agent, prompt)
    return result.final_output