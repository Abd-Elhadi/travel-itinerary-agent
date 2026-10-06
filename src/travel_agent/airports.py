import re

# Demo mapping.
AIRPORTS: dict[str, str] = {
    # origins
    "miami": "MIA", "hollywood": "MIA", "fort lauderdale": "FLL", "new york": "JFK",
    "chicago": "ORD", "atlanta": "ATL", "los angeles": "LAX", "san francisco": "SFO",
    "des moines": "DSM", "cedar rapids": "CID", "fairfield": "CID",
    # destinations (country keys map to the main international airport)
    "japan": "NRT", "tokyo": "NRT", "kyoto": "KIX", "osaka": "KIX",
    "france": "CDG", "paris": "CDG", "italy": "FCO", "rome": "FCO",
    "united kingdom": "LHR", "uk": "LHR", "london": "LHR",
    "spain": "MAD", "madrid": "MAD", "barcelona": "BCN", "germany": "FRA",
    "egypt": "CAI", "cairo": "CAI", "turkey": "IST", "istanbul": "IST",
    "thailand": "BKK", "bangkok": "BKK", "south korea": "ICN", "seoul": "ICN",
    "singapore": "SIN", "united arab emirates": "DXB", "dubai": "DXB",
    "mexico": "MEX", "canada": "YYZ", "brazil": "GRU", "australia": "SYD",
}


class AirportNotFound(ValueError):
    pass


def resolve_airport(place: str | None) -> str:
    """Return an IATA code for a city or country, or raise AirportNotFound."""
    if not place or not place.strip():
        raise AirportNotFound("Place is empty.")
    key = place.split(",")[0].strip().lower()
    if key in AIRPORTS:
        return AIRPORTS[key]
    if re.fullmatch(r"[a-z]{3}", key):
        return key.upper()
    raise AirportNotFound(f"No airport mapping for '{place}'. Add it to airports.py or pass an IATA code.")