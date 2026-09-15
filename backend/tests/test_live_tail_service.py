import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.config import Settings
from app.api import routes_cloudwatch
from app.services.live_tail_service import LiveTailSessionLimiter, stream_live_tail


def make_settings(**overrides) -> Settings:
    return Settings(
        gemini_api_key="test-key",
        litellm_api_key="test-litellm-key",
        masking_service_api_key=None,
        **overrides,
    )


class FakeEventStream(list):
    def __init__(self, messages):
        super().__init__(messages)
        self.closed = False

    def close(self):
        self.closed = True


@patch("app.services.live_tail_service.get_logs_client")
def test_stream_live_tail_masks_and_emits_events(mock_get_client):
    client = MagicMock()
    mock_get_client.return_value = client
    arn = "arn:aws:logs:ap-southeast-1:123456789012:log-group:/aws/lambda/example"
    client.describe_log_groups.return_value = {
        "logGroups": [{"logGroupName": "/aws/lambda/example", "logGroupArn": arn}]
    }
    stream = FakeEventStream(
        [
            {"sessionStart": {"sessionId": "session-1"}},
            {
                "sessionUpdate": {
                    "sessionMetadata": {"sampled": True},
                    "sessionResults": [
                        {
                            "logGroupIdentifier": arn,
                            "logStreamName": "stream-a",
                            "timestamp": 1000,
                            "message": "user jane@example.com failed",
                        }
                    ],
                }
            },
        ]
    )
    client.start_live_tail.return_value = {"responseStream": stream}
    emitted = []

    stream_live_tail(
        log_group_names=["/aws/lambda/example"],
        filter_pattern="ERROR",
        settings=make_settings(),
        emit=emitted.append,
        stop_event=threading.Event(),
        stream_holder={},
    )

    client.start_live_tail.assert_called_once_with(
        logGroupIdentifiers=[arn], logEventFilterPattern="ERROR"
    )
    assert emitted[0] == {"type": "session_started"}
    event_message = emitted[1]
    assert event_message["sampled"] is True
    assert event_message["events"][0]["origin"] == "/aws/lambda/example"
    assert event_message["events"][0]["stream_or_key"] == "stream-a"
    assert "jane@example.com" not in event_message["events"][0]["message"]
    assert "***MASKED***" in event_message["events"][0]["message"]
    assert emitted[-1]["type"] == "session_ended"
    assert stream.closed is True


@patch("app.services.live_tail_service.get_logs_client")
def test_stream_live_tail_reports_missing_log_group(mock_get_client):
    mock_get_client.return_value.describe_log_groups.return_value = {"logGroups": []}
    emitted = []

    stream_live_tail(
        log_group_names=["missing"],
        filter_pattern=None,
        settings=make_settings(),
        emit=emitted.append,
        stop_event=threading.Event(),
        stream_holder={},
    )

    assert emitted == [{"type": "error", "message": "CloudWatch log group not found: missing"}]


async def test_live_tail_session_limiter_enforces_and_releases_limit():
    limiter = LiveTailSessionLimiter()

    assert await limiter.acquire(1) is True
    assert await limiter.acquire(1) is False
    assert limiter.active == 1

    await limiter.release()

    assert limiter.active == 0
    assert await limiter.acquire(1) is True


@pytest.mark.parametrize("control_type", ["stop", "disconnect"])
async def test_live_tail_websocket_closes_worker_on_stop_or_disconnect(control_type):
    worker_finished = threading.Event()

    class FakeWebSocket:
        def __init__(self):
            self.headers = {"origin": "http://testserver"}
            self.application_state = WebSocketState.CONNECTING
            self.incoming = asyncio.Queue()
            self.outgoing = asyncio.Queue()

        async def accept(self):
            self.application_state = WebSocketState.CONNECTED

        async def receive_json(self):
            message = await self.incoming.get()
            if message.get("type") == "disconnect":
                self.application_state = WebSocketState.DISCONNECTED
                raise WebSocketDisconnect
            return message

        async def send_json(self, message):
            await self.outgoing.put(message)

        async def close(self, code=1000, reason=None):
            self.application_state = WebSocketState.DISCONNECTED

    class FakeStream:
        closed = False

        def close(self):
            self.closed = True

    fake_stream = FakeStream()

    def run_fake_stream(*, emit, stop_event, stream_holder, **kwargs):
        stream_holder["stream"] = fake_stream
        emit({"type": "session_started"})
        deadline = time.monotonic() + 2
        while not stop_event.is_set() and time.monotonic() < deadline:
            time.sleep(0.001)
        worker_finished.set()

    websocket = FakeWebSocket()
    settings = make_settings(cors_origins=["http://testserver"])
    await websocket.incoming.put(
        {
            "type": "start",
            "log_group_names": ["/aws/lambda/example"],
            "filter_pattern": None,
        }
    )

    limiter = LiveTailSessionLimiter()
    with (
        patch.object(routes_cloudwatch, "stream_live_tail", run_fake_stream),
        patch.object(routes_cloudwatch, "live_tail_sessions", limiter),
    ):
        route_task = asyncio.create_task(
            routes_cloudwatch.live_tail_logs(websocket, settings)
        )
        started = await asyncio.wait_for(websocket.outgoing.get(), timeout=1)
        assert started["type"] == "session_started"
        assert started["inactivity_timeout_seconds"] == 900

        await websocket.incoming.put({"type": control_type})
        if control_type == "stop":
            stopped = await asyncio.wait_for(websocket.outgoing.get(), timeout=1)
            assert stopped == {"type": "session_stopped", "reason": "Stopped by user."}
        await asyncio.wait_for(route_task, timeout=2)

    assert worker_finished.is_set()
    assert fake_stream.closed is True
    assert limiter.active == 0
    assert websocket.application_state == WebSocketState.DISCONNECTED
