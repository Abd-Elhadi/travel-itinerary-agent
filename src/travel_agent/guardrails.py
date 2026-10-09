import re
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
You may see only the latest message, without the earlier conversation.

on_topic is true when the message is about planning a trip, answers a question about a trip
(passport country, dates, budget, number of travelers, interests, origin, destination, trip purpose),
or is a short greeting. Short replies such as "France", "3 people", "yes", "business", or a date are
on topic: assume they answer the assistant's last question about a trip.

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


# Text that leaks the model's reasoning or makes claims nobody supplied.
META_PHRASES = ("no repeat", "adjusted to", "as instructed", "your preference", "reliable")

# Items that may legitimately appear more than once (or are not places).
_SKIP_WORDS = (
    "free time", "free day", "free morning", "free afternoon", "free evening",
    "arrival", "arrive", "departure", "depart", "check in", "check-in",
    "check out", "check-out", "transfer",
)
_PREFIXES = ("breakfast at ", "lunch at ", "dinner at ", "meals at ", "visit ", "explore ", "tour ")


def _normalize(item: str) -> str:
    text = re.sub(r"\(.*?\)", "", item.lower()).strip(" .")
    for prefix in _PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.strip()


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

    # The same place must not appear twice.
    seen: set[str] = set()
    for d in itinerary.days:
        for item in d.items:
            low = item.lower()
            if any(word in low for word in _SKIP_WORDS):
                continue
            key = _normalize(item)
            if key in seen:
                problems.append(f"'{item}' repeats an earlier activity. Use free time instead.")
            seen.add(key)

    note = itinerary.budget_note.replace(",", "")
    candidates = {str(int(ctx.total_usd)), str(int(round(ctx.total_usd)))}
    if not any(c in note for c in candidates):
        problems.append("budget_note must state the total cost from the budget input.")

    if ctx.visa_needs_verification and "verify" not in itinerary.visa_note.lower():
        problems.append("visa_note must tell the traveler to verify on an official government site.")

    all_text = [itinerary.title, itinerary.summary, itinerary.visa_note, itinerary.budget_note]
    all_text += [item for d in itinerary.days for item in d.items]
    for value in all_text:
        low = value.lower()
        hit = next((p for p in META_PHRASES if p in low), None)
        if hit:
            problems.append(f"Text contains '{hit}', which does not belong in a traveler itinerary: {value[:60]}")

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