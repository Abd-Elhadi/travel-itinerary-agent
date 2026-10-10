import pytest

from travel_agent.airports import AirportNotFound, _nearest_iata, resolve_airport

KATHMANDU = (27.7172, 85.3240)
MIAMI = (25.7617, -80.1918)
TOKYO = (35.6762, 139.6503)


def test_nearest_iata_from_city_coords():
    assert _nearest_iata(*KATHMANDU) == "KTM"
    assert _nearest_iata(*MIAMI) == "MIA"
    assert _nearest_iata(*TOKYO) == "HND"


def test_known_places(monkeypatch):
    coords = {
        "kathmandu": KATHMANDU,
        "miami": MIAMI,
        "tokyo": TOKYO,
    }
    monkeypatch.setattr(
        "travel_agent.airports._geocode",
        lambda place: coords.get(place.lower()),
    )
    assert resolve_airport("Kathmandu") == "KTM"
    assert resolve_airport("Kathmandu and Pokhara") == "KTM"
    assert resolve_airport("Miami") == "MIA"
    assert resolve_airport("Miami, Florida") == "MIA"
    assert resolve_airport("Tokyo") == "HND"


def test_iata_passthrough():
    assert resolve_airport("sfo") == "SFO"


def test_unknown_raises(monkeypatch):
    monkeypatch.setattr("travel_agent.airports._geocode", lambda place: None)
    with pytest.raises(AirportNotFound):
        resolve_airport("Atlantis City")
