import re


def parse_cities(destination: str | None) -> list[str]:
    """Split a destination string into city names.

    Handles comma lists ("Kathmandu, Pokhara") and 'and' lists
    ("Kathmandu and Pokhara").
    """
    if not destination or not destination.strip():
        return []
    parts = re.split(r",|\band\b", destination, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def allocate_parts(total: int, n: int) -> list[int]:
    """Split `total` into `n` parts. Remainder goes to the first parts (gateway first)."""
    if n <= 0:
        return []
    if total <= 0:
        return [0] * n
    base, remainder = divmod(total, n)
    return [base + (1 if i < remainder else 0) for i in range(n)]


def expand_city_plan(cities: list[str], num_days: int) -> list[str]:
    """One city name per itinerary day, extra days on the first city."""
    if not cities or num_days <= 0:
        return []
    parts = allocate_parts(num_days, len(cities))
    plan: list[str] = []
    for city, count in zip(cities, parts):
        plan.extend([city] * count)
    return plan
