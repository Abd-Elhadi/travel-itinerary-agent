import json
import os
from pathlib import Path

import httpx
import pycountry
from agents import function_tool

BASE_URL = "https://visa.orizn.app/api/v1/visa/check"
MOCK_PATH = Path(__file__).resolve().parents[3] / "data" / "mock" / "visa.json"
_cache: dict[str, dict] = {}


def to_iso3(value: str) -> str:
    return pycountry.countries.lookup(value.strip()).alpha_3


def _unknown(passport: str, destination: str, **extra) -> dict:
    return {
        "passport": passport,
        "destination": destination,
        "requirement": "unknown",
        "visa_free_days": None,
        "source": "mock",
        **extra,
    }


def _mock(passport: str, destination: str) -> dict:
    try:
        data = json.loads(MOCK_PATH.read_text())
    except FileNotFoundError:
        data = {}
    hit = data.get(f"{passport}-{destination}")
    return {**hit, "source": "mock"} if hit else _unknown(passport, destination)


def check_visa_raw(passport: str, destination: str) -> dict:
    try:
        passport, destination = to_iso3(passport), to_iso3(destination)
    except LookupError:
        return _unknown(passport, destination, error="Country not recognized")

    cache_key = f"{passport}-{destination}"
    if cache_key in _cache:
        return _cache[cache_key]

    api_key = os.getenv("ORIZN_API_KEY")
    if api_key:
        try:
            r = httpx.get(
                BASE_URL,
                params={"passport": passport, "destination": destination},
                headers={"x-api-key": api_key},
                timeout=15,
            )
            r.raise_for_status()
            result = {**r.json(), "source": "orizn_api"}
            _cache[cache_key] = result
            return result
        except httpx.HTTPError:
            pass
    return _mock(passport, destination)


@function_tool
def check_visa(passport_country: str, destination_country: str) -> str:
    """Check visa and entry requirements for a passport and destination.

    Args:
        passport_country: Country name or ISO code of the passport, e.g. France or FRA.
        destination_country: Country name or ISO code of the destination, e.g. Japan or JPN.
    """
    return json.dumps(check_visa_raw(passport_country, destination_country))