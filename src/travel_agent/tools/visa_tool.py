import json
import os
from pathlib import Path

import httpx
import pycountry
from agents import function_tool

BASE_URL = "https://visa.orizn.app/api/v1/visa/check"
ROOT = Path(__file__).resolve().parents[3]
MOCK_PATH = ROOT / "data" / "mock" / "visa.json"
CACHE_PATH = ROOT / "data" / "cache" / "visa.json"  # keep in .gitignore


def to_iso3(value: str) -> str:
    return pycountry.countries.lookup(value.strip()).alpha_3


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_cache(key: str, value: dict) -> None:
    cache = _read_json(CACHE_PATH)
    cache[key] = value
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _unknown(passport: str, destination: str, reason: str) -> dict:
    return {
        "passport": passport,
        "destination": destination,
        "requirement": "unknown",
        "visa_free_days": None,
        "source": "mock",
        "fallback_reason": reason,
    }


def _mock(passport: str, destination: str, reason: str) -> dict:
    hit = _read_json(MOCK_PATH).get(f"{passport}-{destination}")
    if hit:
        return {**hit, "source": "mock", "fallback_reason": reason}
    return _unknown(passport, destination, reason)


def check_visa_raw(passport: str, destination: str) -> dict:
    try:
        passport, destination = to_iso3(passport), to_iso3(destination)
    except LookupError:
        return _unknown(passport, destination, "Country not recognized")

    key = f"{passport}-{destination}"
    cached = _read_json(CACHE_PATH).get(key)
    if cached:
        return cached  # saves the free-tier quota across runs

    api_key = os.getenv("ORIZN_API_KEY")
    if not api_key:
        return _mock(passport, destination, "ORIZN_API_KEY is missing")

    try:
        r = httpx.get(
            BASE_URL,
            params={"passport": passport, "destination": destination},
            headers={"x-api-key": api_key},
            timeout=15,
        )
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return _mock(passport, destination, f"Orizn returned HTTP {exc.response.status_code}")
    except httpx.HTTPError:
        return _mock(passport, destination, "Orizn network error or timeout")

    result = {**r.json(), "source": "orizn_api"}
    _write_cache(key, result)
    return result


@function_tool
def check_visa(passport_country: str, destination_country: str) -> str:
    """Check visa and entry requirements for a passport and destination.

    Args:
        passport_country: Country name or ISO code of the passport, e.g. France or FRA.
        destination_country: Country name or ISO code of the destination, e.g. Japan or JPN.
    """
    return json.dumps(check_visa_raw(passport_country, destination_country))