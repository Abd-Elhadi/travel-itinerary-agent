import json
import os

import httpx
from agents import function_tool

GEO = "https://api.geoapify.com"
_cache: dict[str, list] = {}

MOCK_PLACES = [
    {"name": "Sample Temple", "category": "religion.place_of_worship", "address": "Sample address"},
    {"name": "Sample Museum", "category": "entertainment.museum", "address": "Sample address"},
]


def search_places_raw(city: str, category: str, limit: int, radius_m: int) -> dict:
    key = os.getenv("GEOAPIFY_API_KEY")
    if not key:
        return {"source": "mock", "places": MOCK_PLACES}

    cache_key = f"{city}|{category}|{limit}|{radius_m}"
    if cache_key in _cache:
        return {"source": "geoapify", "places": _cache[cache_key]}

    g = httpx.get(
        f"{GEO}/v1/geocode/search",
        params={"text": city, "format": "json", "limit": 1, "lang": "en", "apiKey": key},
        timeout=15,
    )
    g.raise_for_status()
    results = g.json().get("results")
    if not results:
        return {"source": "geoapify", "places": [], "error": f"City not found: {city}"}
    lon, lat = results[0]["lon"], results[0]["lat"]

    p = httpx.get(
        f"{GEO}/v2/places",
        params={
            "categories": category,
            "conditions": "named",
            "filter": f"circle:{lon},{lat},{radius_m}",
            "bias": f"proximity:{lon},{lat}",
            "limit": limit,
            "lang": "en",
            "apiKey": key,
        },
        timeout=15,
    )
    p.raise_for_status()
    places = []
    for f in p.json().get("features", []):
        props = f["properties"]
        if props.get("name"):
            places.append(
                {
                    "name": props["name"],
                    "category": (props.get("categories") or [category])[0],
                    "address": props.get("formatted"),
                }
            )
    _cache[cache_key] = places
    return {"source": "geoapify", "places": places}


@function_tool
def search_places(city: str, category: str = "tourism.attraction", limit: int = 10, radius_m: int = 10000) -> str:
    """Find places of interest in a city.

    Args:
        city: City name, e.g. Kyoto.
        category: Geoapify category: tourism.attraction, tourism.sights,
            religion.place_of_worship, catering.restaurant, entertainment.museum,
            leisure.park, entertainment.culture.
        limit: Maximum number of places.
        radius_m: Search radius in meters around the city center.
    """
    return json.dumps(search_places_raw(city, category, limit, radius_m))