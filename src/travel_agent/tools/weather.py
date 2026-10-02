import json
from datetime import date, timedelta

import httpx
from agents import function_tool

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def get_weather_raw(city: str, start_date: str, end_date: str) -> dict:
    g = httpx.get(GEOCODE_URL, params={"name": city, "count": 1}, timeout=15)
    g.raise_for_status()
    results = g.json().get("results")
    if not results:
        return {"error": f"City not found: {city}"}
    lat, lon = results[0]["latitude"], results[0]["longitude"]

    limit = date.today() + timedelta(days=15)
    if date.fromisoformat(start_date) > limit:
        return {"note": "Dates are beyond the 16 day forecast range. Use typical seasonal weather."}
    end = min(date.fromisoformat(end_date), limit).isoformat()

    f = httpx.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "start_date": start_date,
            "end_date": end,
        },
        timeout=15,
    )
    f.raise_for_status()
    return f.json().get("daily", {})


@function_tool
def get_weather(city: str, start_date: str, end_date: str) -> str:
    """Get daily weather forecast for a city.

    Args:
        city: City name, e.g. Tokyo.
        start_date: First day, format YYYY-MM-DD.
        end_date: Last day, format YYYY-MM-DD.
    """
    return json.dumps(get_weather_raw(city, start_date, end_date))