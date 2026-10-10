from travel_agent.models import TripPlan


def _usd(value: float) -> str:
    return f"${value:,.2f}"


def render_plan_markdown(plan: TripPlan) -> str:
    """Turn a TripPlan into a readable Markdown report for the UI or an email body."""
    it = plan.itinerary
    b = plan.budget
    lines = [
        f"## {it.title}",
        "",
        it.summary,
        "",
        "### Visa",
        it.visa_note,
        "",
        "### Budget",
        "| Item | Estimate |",
        "| --- | --- |",
        f"| Flights | {_usd(b.flights_usd)} |",
        f"| Stay | {_usd(b.stay_usd)} |",
        f"| Activities | {_usd(b.activities_usd)} |",
        f"| Local transport | {_usd(b.local_transport_usd)} |",
        f"| Food | {_usd(b.food_usd)} |",
        f"| Total | {_usd(b.total_usd)} |",
        f"| Your budget | {_usd(b.budget_usd)} |",
        f"| Remaining | {_usd(b.remaining_usd)} |",
        "",
        it.budget_note,
        "",
        "### Day by day",
    ]
    for day in it.days:
        date_text = f" ({day.date})" if day.date else ""
        lines.append(f"**Day {day.day}{date_text}, {day.city}**")
        lines.extend(f"- {item}" for item in day.items)
        lines.append("")

    if plan.warnings:
        lines.append("### Warnings")
        lines.extend(f"- {w}" for w in plan.warnings)
        lines.append("")

    lines.append("_Prices are estimates from sample or public data. Verify before booking._")
    return "\n".join(lines)