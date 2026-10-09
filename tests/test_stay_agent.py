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