import json
import os
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
from agents import function_tool


DUFFEL_URL = "https://api.duffel.com/air/offer_requests"

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MOCK_PATH = PROJECT_ROOT / "data" / "mock" / "transport.json"


def load_mock(
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    travelers: int,
    reason: str,
) -> dict:
    fixture = json.loads(MOCK_PATH.read_text(encoding="utf-8"))

    options = []

    for flight in fixture["flights"]:
        total = (
            Decimal(str(flight["round_trip_usd_per_adult"]))
            * travelers
        )

        options.append({
            "mode": "flight",
            "description": (
                f"MOCK: {flight['name']}. "
                f"Round trip {origin} → {destination} → {origin}. "
                f"Outbound: {start_date}. Return: {end_date}. "
                f"{travelers} adult travelers. "
                "No real airline or schedule is represented."
            ),
            "cost_usd_total": float(total),
            "is_estimate": True,
        })

    options.sort(key=lambda item: item["cost_usd_total"])

    return {
        "source": "mock",
        "options": options,
        "notes": (
            f"{fixture['notice']} "
            f"Fallback reason: {reason}. "
            "Costs cover the whole group and round trip. "
            "Choose one flight option; do not sum all options."
        ),
    }


async def search_flights_raw(
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    travelers: int,
    force_mock: bool = False,
) -> dict:
    origin = origin.strip().upper()
    destination = destination.strip().upper()

    try:
        if not re.fullmatch(r"[A-Z]{3}", origin):
            raise ValueError("Origin must be a three-letter IATA code.")

        if not re.fullmatch(r"[A-Z]{3}", destination):
            raise ValueError(
                "Destination must be a three-letter IATA code."
            )

        if origin == destination:
            raise ValueError("Origin and destination must differ.")

        departure = date.fromisoformat(start_date)
        returning = date.fromisoformat(end_date)

        if departure < date.today():
            raise ValueError("Departure date cannot be in the past.")

        if returning <= departure:
            raise ValueError("Return date must be after departure.")

        if travelers < 1:
            raise ValueError("At least one traveler is required.")

    except ValueError as exc:
        return {
            "source": "validation",
            "options": [],
            "notes": str(exc),
        }

    def fallback(reason: str) -> dict:
        return load_mock(
            origin,
            destination,
            start_date,
            end_date,
            travelers,
            reason,
        )

    if force_mock:
        return fallback("Mock mode explicitly requested")

    token = os.getenv("DUFFEL_ACCESS_TOKEN", "").strip()

    if not token:
        return fallback("DUFFEL_ACCESS_TOKEN is missing")

    if not token.startswith("duffel_test_"):
        return {
            "source": "validation",
            "options": [],
            "notes": (
                "This implementation only accepts Duffel test tokens. "
                "The provided non-test token was not used."
            ),
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Duffel-Version": "v2",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    payload = {
        "data": {
            "cabin_class": "economy",
            "passengers": [
                {"type": "adult"}
                for _ in range(travelers)
            ],
            "slices": [
                {
                    "origin": origin,
                    "destination": destination,
                    "departure_date": start_date,
                },
                {
                    "origin": destination,
                    "destination": origin,
                    "departure_date": end_date,
                },
            ],
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                DUFFEL_URL,
                params={"return_offers": "true"},
                headers=headers,
                json=payload,
            )

        response.raise_for_status()
        offers = response.json()["data"].get("offers", [])

        options = []

        for offer in offers:
            if offer.get("total_currency") != "USD":
                continue

            total = Decimal(offer["total_amount"])

            if not total.is_finite() or total < 0:
                continue

            journeys = []

            for flight_slice in offer.get("slices", []):
                segments = []

                for segment in flight_slice.get("segments", []):
                    carrier = segment["operating_carrier"]["name"]
                    segment_origin = segment["origin"]["iata_code"]
                    segment_destination = (
                        segment["destination"]["iata_code"]
                    )

                    segments.append(
                        f"{carrier}: "
                        f"{segment_origin} → {segment_destination}; "
                        f"departure {segment['departing_at']}; "
                        f"arrival {segment['arriving_at']}"
                    )

                journeys.append(" / ".join(segments))

            options.append({
                "mode": "flight",
                "description": (
                    "DUFFEL TEST SAMPLE: "
                    + " | ".join(journeys)
                    + f". Offer ID: {offer['id']}"
                ),
                "cost_usd_total": float(total),
                "is_estimate": True,
            })

        if not options:
            return fallback("Duffel returned no usable USD offers")

        options.sort(key=lambda item: item["cost_usd_total"])

        return {
            "source": "duffel_test",
            "options": options[:3],
            "notes": (
                "Duffel test-mode sample results, not real market quotes. "
                "Costs cover all requested adult travelers and both "
                "flight directions. Additional paid services are "
                "excluded. Choose one flight option; do not sum them."
            ),
        }

    except httpx.HTTPStatusError as exc:
        return fallback(
            f"Duffel returned HTTP {exc.response.status_code}"
        )

    except httpx.RequestError:
        return fallback("Duffel network error or timeout")

    except (KeyError, TypeError, ValueError, ArithmeticError):
        return fallback("Unexpected Duffel response format")


@function_tool
async def search_flights(
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    travelers: int,
    force_mock: bool = False,
) -> str:
    """Search round-trip economy flights for adult travelers.

    Args:
        origin: Explicit three-letter origin IATA code.
        destination: Explicit three-letter destination IATA code.
        start_date: Outbound departure date in YYYY-MM-DD format.
        end_date: Return departure date in YYYY-MM-DD format.
        travelers: Number of adult travelers.
        force_mock: Use local sample data without calling Duffel.
    """
    result = await search_flights_raw(
        origin,
        destination,
        start_date,
        end_date,
        travelers,
        force_mock,
    )

    return json.dumps(result)