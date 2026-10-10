import json

from travel_agent.tools import stay_tool

DATA = {
    "Japan": [
        {"name": "Tokyo Hotel", "area": "Tokyo", "nightly_price_usd": 125, "why": "w"},
        {"name": "Kyoto Guesthouse", "area": "Kyoto", "nightly_price_usd": 85, "why": "w"},
    ],
    "default": [
        {"name": "Default Hotel", "area": "Center", "nightly_price_usd": 100, "why": "w"},
    ],
}


def _use_data(monkeypatch, tmp_path):
    path = tmp_path / "stays.json"
    path.write_text(json.dumps(DATA), encoding="utf-8")
    monkeypatch.setattr(stay_tool, "MOCK_PATH", path)
    monkeypatch.delenv("GEOAPIFY_API_KEY", raising=False)
    monkeypatch.delenv("GEOAPIFY_KEY", raising=False)
    monkeypatch.setattr(stay_tool, "fetch_live_geoapify_stays", lambda **k: [])


def test_sorted_cheapest_first_and_rooms_scale(monkeypatch, tmp_path):
    _use_data(monkeypatch, tmp_path)
    result = stay_tool.search_stays_raw("Japan", nights=6, travelers=3)
    assert result["rooms"] == 2
    assert [o["name"] for o in result["options"]] == ["Kyoto Guesthouse", "Tokyo Hotel"]
    assert result["options"][0]["total_cost_usd"] == 85 * 6 * 2


def test_lookup_is_case_insensitive(monkeypatch, tmp_path):
    _use_data(monkeypatch, tmp_path)
    result = stay_tool.search_stays_raw("japan", nights=2, travelers=1)
    assert result["options"][0]["name"] == "Kyoto Guesthouse"


def test_unknown_destination_uses_default(monkeypatch, tmp_path):
    _use_data(monkeypatch, tmp_path)
    result = stay_tool.search_stays_raw("Narnia", nights=1, travelers=2)
    assert [o["name"] for o in result["options"]] == ["Default Hotel"]


def test_live_area_uses_city_not_suburb(monkeypatch):
    monkeypatch.setenv("GEOAPIFY_API_KEY", "test")
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        if "geocode" in url:
            return FakeResponse({
                "features": [{
                    "geometry": {"coordinates": [85.32, 27.72]},
                    "properties": {
                        "place_id": "ktm",
                        "result_type": "city",
                        "city": "Kathmandu",
                    },
                }],
            })
        return FakeResponse({
            "features": [{
                "properties": {
                    "name": "Nobel Peace Hotel",
                    "suburb": "Baudha",
                    "city": "Kathmandu",
                },
            }],
        })

    monkeypatch.setattr(stay_tool.requests, "get", fake_get)
    result = stay_tool.fetch_live_geoapify_stays("Kathmandu", nights=3, rooms=2)
    assert result[0]["area"] == "Kathmandu"
    assert result[0]["area"] != "Baudha"


def test_multi_city_picks_one_hotel_per_city(monkeypatch, tmp_path):
    _use_data(monkeypatch, tmp_path)
    monkeypatch.delenv("GEOAPIFY_API_KEY", raising=False)
    monkeypatch.delenv("GEOAPIFY_KEY", raising=False)
    monkeypatch.setattr(stay_tool, "fetch_live_geoapify_stays", lambda **k: [])
    result = stay_tool.search_stays_raw("Kathmandu, Pokhara", nights=6, travelers=3)
    assert [o["area"] for o in result["options"]] == ["Kathmandu", "Pokhara"]
    assert result["options"][0]["total_cost_usd"] == 100 * 3 * 2
    assert result["options"][1]["total_cost_usd"] == 100 * 3 * 2