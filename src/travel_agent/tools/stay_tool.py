import json
from pathlib import Path
import math

from agents import function_tool


MOCK_PATH = Path(__file__).resolve().parents[3] / "data" / "mock" / "stays.json"


def search_stays_raw(destination: str, nights: int, travelers: int) -> dict:
    """Load mock accommodation options and calculate full-trip costs."""

    try:
        data = json.loads(MOCK_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    options = data.get(destination, data.get("default", []))
    results = []

    for option in options:
        rooms = math.ceil(travelers / 2)
        total_cost = round(option["nightly_price_usd"] * nights * rooms, 2)

        results.append(
            {
                "name": option["name"],
                "area": option["area"],
                "total_cost_usd": total_cost,
                "why": option["why"],
                "is_estimate": True,
            }
        )

    return {
        "source": "mock",
        "destination": destination,
        "nights": nights,
        "travelers": travelers,
        "options": results,
    }


@function_tool
def search_stays(destination: str, nights: int, travelers: int) -> str:
    """Find sample accommodation options for trip planning.

    Args:
        destination: Destination country or city.
        nights: Number of hotel nights.
        travelers: Number of travelers.
    """
    return json.dumps(search_stays_raw(destination, nights, travelers))