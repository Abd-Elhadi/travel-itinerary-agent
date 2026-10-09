import httpx

from travel_agent.tools import visa_tool


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(visa_tool, "CACHE_PATH", tmp_path / "cache" / "visa.json")
    mock = tmp_path / "visa_mock.json"
    mock.write_text('{"FRA-JPN": {"passport": "FRA", "destination": "JPN", '
                    '"requirement": "visa_free", "visa_free_days": 90}}')
    monkeypatch.setattr(visa_tool, "MOCK_PATH", mock)


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.com")
            raise httpx.HTTPStatusError("err", request=request, response=httpx.Response(self.status_code, request=request))

    def json(self):
        return self._payload


def test_missing_key_falls_back_with_reason(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.delenv("ORIZN_API_KEY", raising=False)
    r = visa_tool.check_visa_raw("France", "Japan")
    assert r["source"] == "mock"
    assert r["requirement"] == "visa_free"
    assert "ORIZN_API_KEY" in r["fallback_reason"]


def test_http_429_reason_is_visible(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("ORIZN_API_KEY", "x")
    monkeypatch.setattr(visa_tool.httpx, "get", lambda *a, **k: FakeResponse(429))
    r = visa_tool.check_visa_raw("France", "Japan")
    assert r["source"] == "mock"
    assert "429" in r["fallback_reason"]


def test_success_is_cached_on_disk(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("ORIZN_API_KEY", "x")
    calls = []

    def fake_get(*a, **k):
        calls.append(1)
        return FakeResponse(200, {"requirement": "visa_free", "visa_free_days": 90})

    monkeypatch.setattr(visa_tool.httpx, "get", fake_get)
    first = visa_tool.check_visa_raw("France", "Japan")
    second = visa_tool.check_visa_raw("France", "Japan")
    assert first["source"] == second["source"] == "orizn_api"
    assert len(calls) == 1