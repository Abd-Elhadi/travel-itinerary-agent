from dataclasses import dataclass, field

from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
    input_guardrail,
    output_guardrail,
)
from pydantic import BaseModel

from travel_agent.config import MODEL
from travel_agent.models import Itinerary


# ---------------------------------------------------------------------------
# Input guardrail: runs before the Intake agent
# ---------------------------------------------------------------------------

class TravelInputCheck(BaseModel):
    on_topic: bool
    unsafe: bool
    reason: str


INPUT_CHECK_INSTRUCTIONS = """You check messages sent to a travel planning assistant.
Judge the latest user message in the context of the conversation.

on_topic is true when the message is about planning a trip, answers a question about a trip
(passport country, dates, budget, number of travelers, interests, origin, destination, trip purpose),
or is a short greeting. Short answers such as "France", "3 people", or "yes" are on topic when they
answer the assistant's last question.

unsafe is true when the user asks for help with illegal travel activity: forged documents, evading
border or visa checks, smuggling, or trafficking.

Write a one sentence reason."""

input_check_agent = Agent(
    name="Travel input check",
    instructions=INPUT_CHECK_INSTRUCTIONS,
    model=MODEL,
    output_type=TravelInputCheck,
)


@input_guardrail(run_in_parallel=False)
async def travel_input_guardrail(
    ctx: RunContextWrapper, agent: Agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    result = await Runner.run(input_check_agent, input, context=ctx.context)
    check = result.final_output
    return GuardrailFunctionOutput(
        output_info=check,
        tripwire_triggered=(not check.on_topic) or check.unsafe,
    )


# ---------------------------------------------------------------------------
# Output guardrail: runs on the Planner's itinerary
# ---------------------------------------------------------------------------

@dataclass
class PlanContext:
    num_days: int
    base_city: str | None
    total_usd: float
    visa_needs_verification: bool
    other_stay_names: list[str] = field(default_factory=list)


def check_itinerary(itinerary: Itinerary, ctx: PlanContext) -> list[str]:
    """Deterministic checks. Returns a list of problems, empty when the itinerary is fine."""
    problems: list[str] = []

    if len(itinerary.days) != ctx.num_days:
        problems.append(f"Itinerary has {len(itinerary.days)} days; expected {ctx.num_days}.")

    numbers = [d.day for d in itinerary.days]
    if numbers != list(range(1, len(numbers) + 1)):
        problems.append("Day numbers must run 1, 2, 3 in order.")

    if ctx.base_city:
        base = ctx.base_city.strip().lower()
        wrong = sorted({d.city for d in itinerary.days if d.city.strip().lower() != base})
        if wrong:
            problems.append(f"All days must be in {ctx.base_city}; found: {', '.join(wrong)}.")

    text = " ".join(item.lower() for d in itinerary.days for item in d.items)
    for name in ctx.other_stay_names:
        if name.lower() in text:
            problems.append(f"Alternative hotel '{name}' appears in the plan. Use only the first stay option.")

    note = itinerary.budget_note.replace(",", "")
    candidates = {str(int(ctx.total_usd)), str(int(round(ctx.total_usd)))}
    if not any(c in note for c in candidates):
        problems.append("budget_note must state the total cost from the budget input.")

    if ctx.visa_needs_verification and "verify" not in itinerary.visa_note.lower():
        problems.append("visa_note must tell the traveler to verify on an official government site.")

    for label, value in (("summary", itinerary.summary), ("budget_note", itinerary.budget_note)):
        low = value.lower()
        if "your preference" in low or "as instructed" in low:
            problems.append(f"{label} claims a preference or instruction the traveler never gave.")

    return problems


@output_guardrail
async def itinerary_guardrail(
    ctx: RunContextWrapper[PlanContext], agent: Agent, output: Itinerary
) -> GuardrailFunctionOutput:
    problems = check_itinerary(output, ctx.context)
    return GuardrailFunctionOutput(
        output_info={"problems": problems},
        tripwire_triggered=bool(problems),
    )