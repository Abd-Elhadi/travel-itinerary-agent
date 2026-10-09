import os
import re
import smtplib
import ssl
from email.message import EmailMessage

from travel_agent.models import TripPlan


def validate_recipient(value: str) -> str:
    recipient = (value or "").strip()

    # Intentionally accept one simple address, not a recipient list.
    if (
        len(recipient) > 254
        or not re.fullmatch(r"[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+", recipient)
    ):
        raise ValueError("Enter one valid recipient email address.")

    return recipient


def check_email_configuration() -> tuple[str, str]:
    sender = os.getenv("EMAIL_SENDER", "").strip()
    password = os.getenv("EMAIL_APP_PASSWORD", "").replace(" ", "").strip()

    if not sender or not password:
        raise ValueError(
            "Email is not configured. Add EMAIL_SENDER and "
            "EMAIL_APP_PASSWORD to .env, then restart the app."
        )

    return validate_recipient(sender), password


def build_report_text(plan: TripPlan) -> str:
    trip = plan.trip
    budget = plan.budget
    itinerary = plan.itinerary

    lines = [
        itinerary.title,
        "=" * 50,
        "",
        f"Destination: {trip.destination}",
        f"Origin: {trip.origin}",
        f"Dates: {trip.start_date} to {trip.end_date}",
        f"Duration: {trip.num_days} days",
        f"Travelers: {trip.travelers}",
        "",
        "SUMMARY",
        itinerary.summary,
        "",
        "VISA INFORMATION",
        itinerary.visa_note,
        "",
        "DAILY ITINERARY",
    ]

    for day in itinerary.days:
        lines.extend([
            "",
            f"Day {day.day} | {day.date or 'Date not specified'} | {day.city}",
        ])
        lines.extend(f"- {item}" for item in day.items)

    lines.extend([
        "",
        "BUDGET — WHOLE GROUP, WHOLE TRIP",
        f"Flights: ${budget.flights_usd:,.2f}",
        f"Accommodation: ${budget.stay_usd:,.2f}",
        f"Activities: ${budget.activities_usd:,.2f}",
        f"Local transport / car rental: ${budget.local_transport_usd:,.2f}",
        f"Food: ${budget.food_usd:,.2f}",
        f"Total estimate: ${budget.total_usd:,.2f}",
        f"Your budget: ${budget.budget_usd:,.2f}",
    ])

    if budget.within_budget:
        lines.append(f"Remaining: ${budget.remaining_usd:,.2f}")
    else:
        lines.append(f"Over budget by: ${abs(budget.remaining_usd):,.2f}")

    lines.extend([
        "",
        "BUDGET NOTES",
        itinerary.budget_note,
        "Food uses a demo allowance of $45 per person per day.",
        "A $0 category may mean pricing was unavailable, not that it is free.",
        "",
        "WEATHER",
        plan.activities.weather_summary,
        "",
        "TRANSPORT NOTES",
        plan.transport.notes,
        "",
        "ACCOMMODATION NOTES",
        plan.stay.notes,
    ])

    if any(option.is_estimate for option in plan.transport.options):
        lines.append("\nSome transport options are marked as estimates.")

    if any(option.is_estimate for option in plan.stay.options):
        lines.append("\nSome accommodation options are marked as estimates.")

    if plan.warnings:
        lines.extend(["", "WARNINGS"])
        lines.extend(f"- {warning}" for warning in plan.warnings)

    lines.extend([
        "",
        "This report contains recommendations and estimated prices.",
        "No flights, accommodation, or activities have been booked.",
        "Verify visa requirements with official government sources.",
    ])

    return "\n".join(lines)


def send_plan_email(recipient: str, plan: TripPlan) -> None:
    recipient = validate_recipient(recipient)
    sender, password = check_email_configuration()

    # Prevent line breaks in the email subject.
    title = " ".join(plan.itinerary.title.splitlines())

    message = EmailMessage()
    message["Subject"] = f"Your travel plan — {title}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(build_report_text(plan))

    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(
        "smtp.gmail.com",
        465,
        context=context,
        timeout=30,
    ) as smtp:
        smtp.login(sender, password)
        refused = smtp.send_message(
            message,
            from_addr=sender,
            to_addrs=[recipient],
        )

        if refused:
            raise RuntimeError("The email server refused the recipient.")