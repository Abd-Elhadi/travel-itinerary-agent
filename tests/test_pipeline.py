import asyncio
from types import SimpleNamespace

from agents import GuardrailFunctionOutput, OutputGuardrailTripwireTriggered
from agents.guardrail import OutputGuardrailResult

from travel_agent import pipeline
from travel_agent.agents.planner_agent import planner_agent
from travel_agent.guardrails import PlanContext, itinerary_guardrail
from travel_agent.models import Itinerary, VisaResult

VISA = VisaResult(passport="FRA", destination="JPN", requirement="visa_free",
                  allowed_days=90, summary="ok", source="mock")
ITIN = Itinerary(title="t", summary="s", visa_note="v", days=[], budget_note="b")
BAD = Itinerary(title="bad", summary="s", visa_note="v", days=[], budget_note="b")


def _patch(monkeypatch, transport, stay, activities, captured):
    async def visa(trip): return VISA

    async def acts(trip, base_city):
        captured["base_city"] = base_city
        return activities

    async def tr(trip, o, d): return transport

    async def st(trip): return stay

    async def plan(payload, ctx, warnings):
        captured.update(payload)
        captured["ctx"] = ctx
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


def test_planner_context_is_built_from_results(monkeypatch, trip, transport, stay, activities):
    captured = {}
    _patch(monkeypatch, transport, stay, activities, captured)
    asyncio.run(pipeline.build_plan(trip))
    ctx = captured["ctx"]
    assert ctx.num_days == 7
    assert ctx.base_city == "Kyoto"
    assert ctx.total_usd == 5475
    assert ctx.visa_needs_verification is True   # VISA source is mock
    assert ctx.other_stay_names == ["h2"]


def test_planner_payload_has_formatted_budget(monkeypatch, trip, transport, stay, activities):
    captured = {}
    _patch(monkeypatch, transport, stay, activities, captured)
    asyncio.run(pipeline.build_plan(trip))
    assert captured["budget_display"]["total_usd"] == "$5,475.00"
    assert captured["budget_display"]["within_budget"] is True


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


# ---- planner retry on output guardrail failure ----

def _ctx():
    return PlanContext(num_days=1, base_city="Kyoto", total_usd=1.0, visa_needs_verification=False)


def _tripwire(output, problems):
    result = OutputGuardrailResult(
        guardrail=itinerary_guardrail,
        agent_output=output,
        agent=planner_agent,
        output=GuardrailFunctionOutput(output_info={"problems": problems}, tripwire_triggered=True),
    )
    return OutputGuardrailTripwireTriggered(result)


def test_planner_retries_with_problems(monkeypatch):
    seen = []

    async def fake_run(agent, input, context=None):
        seen.append(input)
        if len(seen) == 1:
            raise _tripwire(BAD, ["Itinerary has 0 days; expected 1."])
        return SimpleNamespace(final_output=ITIN)

    monkeypatch.setattr(pipeline.Runner, "run", fake_run)
    warnings = []
    out = asyncio.run(pipeline._plan({"trip": {}}, _ctx(), warnings))
    assert out is ITIN
    assert "fix_these_problems" in seen[1]
    assert warnings == []


def test_planner_gives_up_after_retry(monkeypatch):
    async def fake_run(agent, input, context=None):
        raise _tripwire(BAD, ["still wrong"])

    monkeypatch.setattr(pipeline.Runner, "run", fake_run)
    warnings = []
    out = asyncio.run(pipeline._plan({"trip": {}}, _ctx(), warnings))
    assert out is BAD
    assert any("failed checks" in w and "still wrong" in w for w in warnings)