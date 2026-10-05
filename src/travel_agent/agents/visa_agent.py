from agents import Agent

from src.travel_agent.config import MODEL
from src.travel_agent.models import VisaResult
from src.travel_agent.tools.visa_tool import check_visa

INSTRUCTIONS = """You are the visa agent. Input: passport country and destination country, as names or codes.
1. Call check_visa once with the passport country and destination country as given.
2. Return VisaResult. Use the passport and destination codes from the tool output.
3. Return VisaResult. Put the tool's requirement and visa_free_days in the fields. Write one or two sentences in summary.
4. Copy the tool's source field. If source is mock, say the result is sample data.
5. If requirement is unknown, say it is unverified and tell the user to check the destination's official government site.
Never state visa rules that the tool did not return."""

visa_agent = Agent(
    name="Visa",
    instructions=INSTRUCTIONS,
    model=MODEL,
    tools=[check_visa],
    output_type=VisaResult,
)