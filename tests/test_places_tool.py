from travel_agent.tools import places_tool


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_places_request_params(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params))
        if "geocode" in url:
            return FakeResponse({"results": [{"lon": 135.7, "lat": 35.0}]})
        return FakeResponse({"features": [
            {"properties": {"name": "Kiyomizu-dera", "categories": ["religion.place_of_worship"], "formatted": "Kyoto"}},
            {"properties": {"categories": ["tourism.attraction"]}},
        ]})

    monkeypatch.setenv("GEOAPIFY_API_KEY", "test")
    monkeypatch.setattr(places_tool.httpx, "get", fake_get)
    places_tool._cache.clear()

    result = places_tool.search_places_raw("Kyoto", "religion.place_of_worship", 10, 10000)

    place_params = calls[1][1]
    assert place_params["lang"] == "en"
    assert place_params["conditions"] == "named"
    assert place_params["categories"] == "religion.place_of_worship"
    assert [p["name"] for p in result["places"]] == ["Kiyomizu-dera"]  # unnamed place dropped