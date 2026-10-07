import importlib

from pydantic import ValidationError
import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.websockets import WebSocketState

from app.api.routes_cloudwatch import live_tail_logs
from app.config import Settings, get_settings


API_KEY = "a" * 32


@pytest.fixture
def main_module(monkeypatch):
    monkeypatch.setenv("LITELLM_API_KEY", "test")
    get_settings.cache_clear()
    module = importlib.import_module("app.main")
    yield module
    module.app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_production_requires_a_long_api_key():
    with pytest.raises(ValidationError, match="ANOMALOG_API_KEY is required"):
        Settings(litellm_api_key="test", require_api_key=True, anomalog_api_key=None)
    with pytest.raises(ValidationError, match="at least 32"):
        Settings(litellm_api_key="test", require_api_key=True, anomalog_api_key="short")


def test_blank_api_key_keeps_local_development_open():
    settings = Settings(litellm_api_key="test", anomalog_api_key="")
    assert settings.anomalog_api_key is None


async def test_http_api_rejects_missing_and_wrong_keys(monkeypatch, main_module):
    monkeypatch.setattr(
        main_module, "settings", Settings(litellm_api_key="test", anomalog_api_key=API_KEY, require_api_key=True)
    )
    called = 0

    async def next_handler(request):
        nonlocal called
        called += 1
        return JSONResponse({"ok": True})

    def request(path: str, key: str | None = None, method: str = "GET") -> Request:
        headers = [(b"x-api-key", key.encode())] if key is not None else []
        return Request({
            "type": "http", "method": method, "path": path,
            "scheme": "http", "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345), "headers": headers,
        })

    assert (await main_module.enforce_api_key_and_rate_limit(request("/api/health"), next_handler)).status_code == 200
    assert (await main_module.enforce_api_key_and_rate_limit(request("/api/health", method="POST"), next_handler)).status_code == 401
    assert (await main_module.enforce_api_key_and_rate_limit(request("/api/config"), next_handler)).status_code == 401
    assert (await main_module.enforce_api_key_and_rate_limit(request("/api/config", "wrong"), next_handler)).status_code == 401
    assert (await main_module.enforce_api_key_and_rate_limit(request("/api/config", API_KEY), next_handler)).status_code == 200
    assert (await main_module.enforce_api_key_and_rate_limit(request("/openapi.json"), next_handler)).status_code == 401
    assert (await main_module.enforce_api_key_and_rate_limit(request("/api/config", method="OPTIONS"), next_handler)).status_code == 200
    assert called == 3


async def test_live_tail_accepts_correct_key_for_handshake():
    settings = Settings(
        litellm_api_key="test", anomalog_api_key=API_KEY,
        require_api_key=True, cors_origins=["http://testserver"]
    )
    class FakeWebSocket:
        headers = {"x-api-key": API_KEY, "origin": "http://testserver"}
        application_state = WebSocketState.CONNECTING
        accepted = False
        sent: list[dict] = []

        async def accept(self):
            self.accepted = True
            self.application_state = WebSocketState.CONNECTED

        async def receive_json(self):
            return {"type": "invalid"}

        async def send_json(self, message):
            self.sent.append(message)

        async def close(self, *, code: int, reason: str | None = None):
            self.application_state = WebSocketState.DISCONNECTED

    websocket = FakeWebSocket()
    await live_tail_logs(websocket, settings)
    assert websocket.accepted is True
    assert websocket.sent[0]["type"] == "error"


async def test_live_tail_rejects_missing_key_before_accepting():
    class FakeWebSocket:
        headers = {"origin": "http://testserver"}
        closed: tuple[int, str] | None = None

        async def accept(self):
            raise AssertionError("WebSocket was accepted before authentication")

        async def close(self, *, code: int, reason: str):
            self.closed = (code, reason)

    websocket = FakeWebSocket()
    settings = Settings(
        litellm_api_key="test", anomalog_api_key=API_KEY,
        require_api_key=True, cors_origins=["http://testserver"]
    )
    await live_tail_logs(websocket, settings)
    assert websocket.closed == (1008, "Invalid API key")
