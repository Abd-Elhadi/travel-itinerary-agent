import pytest

from travel_agent.airports import AirportNotFound, resolve_airport


def test_known_places():
    assert resolve_airport("Miami") == "MIA"
    assert resolve_airport("Japan") == "NRT"
    assert resolve_airport("Miami, Florida") == "MIA"


def test_iata_passthrough():
    assert resolve_airport("sfo") == "SFO"


def test_unknown_raises():
    with pytest.raises(AirportNotFound):
        resolve_airport("Atlantis City")