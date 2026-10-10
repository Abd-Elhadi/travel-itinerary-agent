import json
import math
import os
from pathlib import Path
import requests
from dotenv import load_dotenv
from agents import function_tool

from travel_agent.cities import allocate_parts, parse_cities

load_dotenv(override=True)

MOCK_PATH = Path(__file__).resolve().parents[3] / "data" / "mock" / "stays.json"


def fetch_live_geoapify_stays(destination: str, nights: int, rooms: int) -> list[dict]:
    """Dynamically fetches accommodations for ANY city or location worldwide via Geoapify."""
    api_key = os.getenv("GEOAPIFY_API_KEY") or os.getenv("GEOAPIFY_KEY")
    if not api_key:
        print("[Stay Tool Debug] GEOAPIFY_API_KEY missing.")
        return []

    try:
        geo_url = "https://api.geoapify.com/v1/geocode/search"
        geo_resp = requests.get(
            geo_url,
            params={"text": destination, "apiKey": api_key},
            timeout=8,
        )
        geo_data = geo_resp.json()

        features = geo_data.get("features", [])
        if not features:
            print(f"[Stay Tool Debug] Geocoding found no match for: {destination}")
            return []

        top_feature = features[0]
        properties = top_feature.get("properties", {})
        place_id = properties.get("place_id")
        result_type = properties.get("result_type")
        geocoded_city = properties.get("city") or destination

        lon, lat = top_feature["geometry"]["coordinates"][:2]

        places_url = "https://api.geoapify.com/v2/places"
        places_params = {
            "categories": "accommodation.hotel,accommodation.guest_house",
            "limit": 10,
            "apiKey": api_key,
        }

        if place_id and result_type in ["city", "town", "suburb"]:
            places_params["filter"] = f"place:{place_id}"
        else:
            places_params["bias"] = f"proximity:{lon},{lat}"
            places_params["filter"] = f"circle:{lon},{lat},50000"

        places_resp = requests.get(places_url, params=places_params, timeout=8)
        places_data = places_resp.json()

        results = []
        for feature in places_data.get("features", []):
            props = feature.get("properties", {})
            name = props.get("name") or props.get("formatted")
            if not name:
                continue

            city = props.get("city") or geocoded_city or destination
            nightly_rate = 120.0
            total_price = round(nightly_rate * nights * rooms, 2)

            results.append({
                "name": name,
                "area": city,
                "total_cost_usd": total_price,
                "why": f"Verified accommodation in {city}.",
                "is_estimate": True,
            })

        return results

    except Exception as e:
        print(f"[Stay Tool Debug Exception] {e}")
        return []


def _mock_stays_for_city(city: str, nights: int, rooms: int) -> list[dict]:
    try:
        data = json.loads(MOCK_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    lookup = {key.lower(): value for key, value in data.items()}
    options = lookup.get(city.strip().lower(), lookup.get("default", []))

    results = []
    for option in options:
        total_cost = round(option["nightly_price_usd"] * nights * rooms, 2)
        results.append({
            "name": option["name"],
            "area": option["area"],
            "total_cost_usd": total_cost,
            "why": option["why"],
            "is_estimate": True,
        })
    results.sort(key=lambda r: r["total_cost_usd"])
    return results


def _search_one_city(city: str, nights: int, rooms: int) -> tuple[list[dict], str]:
    live = fetch_live_geoapify_stays(destination=city, nights=nights, rooms=rooms)
    if live:
        live.sort(key=lambda r: r["total_cost_usd"])
        return live, "geoapify_places"
    return _mock_stays_for_city(city, nights, rooms), "mock"


def search_stays_raw(destination: str, nights: int, travelers: int, start_date: str | None = None) -> dict:
    rooms = math.ceil(travelers / 2)
    cities = parse_cities(destination)
    if not cities:
        cities = [destination.strip()] if destination and destination.strip() else []

    if len(cities) <= 1:
        city = cities[0] if cities else (destination or "")
        options, source = _search_one_city(city, nights, rooms)
        return {
            "source": source,
            "destination": destination,
            "nights": nights,
            "travelers": travelers,
            "rooms": rooms,
            "options": options,
        }

    night_parts = allocate_parts(nights, len(cities))
    options = []
    sources: set[str] = set()
    for city, city_nights in zip(cities, night_parts):
        if city_nights <= 0:
            continue
        city_options, source = _search_one_city(city, city_nights, rooms)
        sources.add(source)
        if not city_options:
            continue
        chosen = dict(city_options[0])
        chosen["area"] = city
        options.append(chosen)

    source = "geoapify_places" if "geoapify_places" in sources else "mock"
    return {
        "source": source,
        "destination": destination,
        "nights": nights,
        "travelers": travelers,
        "rooms": rooms,
        "options": options,
    }


@function_tool
def search_stays(destination: str, nights: int, travelers: int) -> str:
    return json.dumps(search_stays_raw(destination, nights, travelers))
