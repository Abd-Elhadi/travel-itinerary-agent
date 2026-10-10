import os
import re

import httpx
from airports import airport_data

from travel_agent.cities import parse_cities

class AirportNotFound(ValueError):
    pass


GEOAPIFY_GEOCODE = "https://api.geoapify.com/v1/geocode/search"
OPEN_METEO_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
MAX_AIRPORT_DISTANCE_KM = 150.0


def _geocode_geoapify(place: str, api_key: str) -> tuple[float, float] | None:
    try:
        response = httpx.get(
            GEOAPIFY_GEOCODE,
            params={
                "text": place,
                "format": "json",
                "limit": 1,
                "lang": "en",
                "apiKey": api_key,
            },
            timeout=15,
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        if not results:
            return None
        return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as exc:
        print(f"[Airports Warning] Geoapify geocode failed for '{place}': {exc}")
        return None


def _geocode_open_meteo(place: str) -> tuple[float, float] | None:
    try:
        response = httpx.get(
            OPEN_METEO_GEOCODE,
            params={"name": place, "count": 1},
            timeout=15,
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        if not results:
            return None
        return float(results[0]["latitude"]), float(results[0]["longitude"])
    except Exception as exc:
        print(f"[Airports Warning] Open-Meteo geocode failed for '{place}': {exc}")
        return None


def _geocode(place: str) -> tuple[float, float] | None:
    api_key = os.getenv("GEOAPIFY_API_KEY") or os.getenv("GEOAPIFY_KEY")
    if api_key:
        coords = _geocode_geoapify(place, api_key)
        if coords:
            return coords
    return _geocode_open_meteo(place)


def _nearest_iata(lat: float, lon: float) -> str | None:
    for airport_type in ("large_airport", "medium_airport"):
        found = airport_data.find_nearest_airport(
            lat,
            lon,
            filters={"type": airport_type, "has_scheduled_service": True},
        )
        if not found:
            continue
        iata = (found.get("iata") or "").strip()
        distance = found.get("distance")
        if iata and distance is not None and distance <= MAX_AIRPORT_DISTANCE_KM:
            return iata.upper()
    return None


def resolve_airport(place: str | None) -> str:
    """Resolve a city, multi-city string, or IATA code to a nearby airport code."""
    if not place or not place.strip():
        raise AirportNotFound("Place is empty.")

    cities = parse_cities(place)
    primary_place = cities[0] if cities else place.strip()

    if re.fullmatch(r"[a-zA-Z]{3}", primary_place):
        return primary_place.upper()

    coords = _geocode(primary_place)
    if coords:
        iata = _nearest_iata(*coords)
        if iata:
            return iata

    raise AirportNotFound(
        f"No airport mapping found for '{primary_place}'. Please enter a valid city or IATA code."
    )
