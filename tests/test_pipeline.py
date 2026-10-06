import asyncio

from travel_agent import pipeline
from travel_agent.models import Itinerary, VisaResult

VISA = VisaResult(passport="FRA", destination="JPN", requirement="visa_free",
                  allowed_days=90, summary="ok", source="mock")
ITIN = Itinerary(title="t", summary="s", visa_note="v", days=[], budget_note="b")


def _patch(monkeypatch, transport, stay, activities, captured):
    async def visa(trip): return VISA

    async def acts(trip, base_city):
        captured["base_city"] = base_city
        return activities

    async def tr(trip, o, d): return transport

    async def st(trip): return stay

    async def plan(payload):
        captured.update(payload)
        return ITIN

    monkeypatch.setattr(pipeline, "_visa", visa)
    monkeypatch.setattr(pipeline, "_activities", acts)
    monkeypatch.setattr(pipeline, "_transport", tr)
    monkeypatch.setattr(pipeline, "_stay", st)
    monkeypatch.setattr(pipeline, "_plan", plan)


def test_happy_path(monkeypatch, trip, transport, stay, activities):
    captured = {}
    _patch(monkeypatch, transport, stay, activities, captured)
    result = asyncio.run(pipeline.build_plan(trip))
    assert result.budget.total_usd == 5475
    assert result.warnings == []
    assert {"trip", "visa", "activities", "transport", "stay", "budget", "warnings"} <= captured.keys()


def test_activities_use_stay_city(monkeypatch, trip, transport, stay, activities):
    captured = {}
    _patch(monkeypatch, transport, stay, activities, captured)
    asyncio.run(pipeline.build_plan(trip))
    assert captured["base_city"] == "Kyoto"


def test_stay_failure_degrades(monkeypatch, trip, transport, stay, activities):
    captured = {}
    _patch(monkeypatch, transport, stay, activities, captured)

    async def broken(trip): raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "_stay", broken)

    result = asyncio.run(pipeline.build_plan(trip))
    assert result.stay.options == []
    assert captured["base_city"] is None
    assert any("Stay failed" in w for w in result.warnings)
    assert any("excludes accommodation" in w for w in result.warnings)
    assert captured["warnings"] == result.warnings


def test_activities_failure_degrades(monkeypatch, trip, transport, stay, activities):
    captured = {}
    _patch(monkeypatch, transport, stay, activities, captured)

    async def broken(trip, base_city): raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "_activities", broken)

    result = asyncio.run(pipeline.build_plan(trip))
    assert result.activities.activities == []
    assert any("Activities failed" in w for w in result.warnings)


def test_unknown_airport_adds_warning(monkeypatch, trip, transport, stay, activities):
    captured = {}
    _patch(monkeypatch, transport, stay, activities, captured)
    trip.origin = "Atlantis City"
    result = asyncio.run(pipeline.build_plan(trip))
    assert any("No airport mapping" in w for w in result.warnings)


def test_incomplete_trip_raises(trip):
    trip.start_date = None
    try:
        asyncio.run(pipeline.build_plan(trip))
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "start_date" in str(exc)