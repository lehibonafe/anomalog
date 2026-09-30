import asyncio
from contextlib import suppress
import threading
from typing import Literal

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError
from starlette.websockets import WebSocketState

from app.config import Settings, get_settings
from app.schemas.cloudwatch import (
    CloudWatchSearchRequest,
    CloudWatchSearchResponse,
    LogGroupsResponse,
)
from app.services import cloudwatch_service
from app.services.live_tail_service import LiveTailSessionLimiter, stream_live_tail

router = APIRouter(prefix="/api/cloudwatch", tags=["cloudwatch"])
live_tail_sessions = LiveTailSessionLimiter()


class LiveTailStartRequest(BaseModel):
    type: Literal["start"]
    log_group_names: list[str] = Field(min_length=1, max_length=10)
    filter_pattern: str | None = Field(default=None, max_length=1024)


@router.get("/log-groups", response_model=LogGroupsResponse)
def get_log_groups(
    keyword: str | None = Query(default=None),
    prefix: str | None = Query(default=None),
    next_token: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=50),
    settings: Settings = Depends(get_settings),
):
    # Keep `prefix` as a compatibility alias for older frontends, but apply
    # substring matching for both parameters.
    return cloudwatch_service.list_log_groups(
        keyword if keyword is not None else prefix,
        next_token,
        limit,
        settings,
    )


@router.post("/logs/search", response_model=CloudWatchSearchResponse)
def search_logs(
    request: CloudWatchSearchRequest,
    settings: Settings = Depends(get_settings),
):
    return cloudwatch_service.search_log_events(
        log_group_names=request.log_group_names,
        start_time=request.start_time,
        end_time=request.end_time,
        filter_pattern=request.filter_pattern,
        limit=request.limit,
        cursor=request.cursor,
        settings=settings,
    )


@router.websocket("/logs/live-tail")
async def live_tail_logs(
    websocket: WebSocket,
    settings: Settings = Depends(get_settings),
):
    """Proxy one explicitly started, masked CloudWatch Live Tail session."""
    origin = websocket.headers.get("origin")
    if origin and "*" not in settings.cors_origins and origin not in settings.cors_origins:
        await websocket.close(code=1008, reason="Origin is not allowed")
        return

    await websocket.accept()
    acquired = False
    disconnected = False
    stop_event = threading.Event()
    stream_holder: dict = {}
    worker_thread: threading.Thread | None = None
    worker_done: threading.Event | None = None
    receiver_task: asyncio.Task | None = None

    try:
        try:
            raw_request = await asyncio.wait_for(websocket.receive_json(), timeout=10)
            request = LiveTailStartRequest.model_validate(raw_request)
        except (TimeoutError, ValidationError, ValueError):
            await websocket.send_json(
                {"type": "error", "message": "Invalid or missing Live Tail start request."}
            )
            return

        log_group_names = list(dict.fromkeys(name.strip() for name in request.log_group_names))
        if any(not name for name in log_group_names):
            await websocket.send_json(
                {"type": "error", "message": "Log group names cannot be blank."}
            )
            return

        acquired = await live_tail_sessions.acquire(settings.live_tail_max_concurrent_sessions)
        if not acquired:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "The Live Tail session limit has been reached. Stop another session and retry.",
                }
            )
            await websocket.close(code=1013, reason="Live Tail session limit reached")
            return

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=50)
        last_activity = [loop.time()]

        def emit(message: dict) -> None:
            def enqueue() -> None:
                if queue.full():
                    stop_event.set()
                    with suppress(asyncio.QueueEmpty):
                        queue.get_nowait()
                    queue.put_nowait(
                        {
                            "type": "error",
                            "message": "Live Tail stopped because the browser could not keep up with the event stream.",
                        }
                    )
                    return
                queue.put_nowait(message)

            try:
                loop.call_soon_threadsafe(enqueue)
            except RuntimeError:
                stop_event.set()

        worker_done = threading.Event()

        def run_worker() -> None:
            try:
                stream_live_tail(
                    log_group_names=log_group_names,
                    filter_pattern=request.filter_pattern,
                    settings=settings,
                    emit=emit,
                    stop_event=stop_event,
                    stream_holder=stream_holder,
                )
            except Exception:
                emit(
                    {
                        "type": "error",
                        "message": "Live Tail stopped because of an unexpected streaming error.",
                    }
                )
            finally:
                worker_done.set()

        worker_thread = threading.Thread(
            target=run_worker,
            name="cloudwatch-live-tail",
            daemon=True,
        )
        worker_thread.start()

        async def receive_controls() -> None:
            def enqueue_control(message: dict) -> None:
                if queue.full():
                    with suppress(asyncio.QueueEmpty):
                        queue.get_nowait()
                queue.put_nowait(message)

            try:
                while True:
                    message = await websocket.receive_json()
                    message_type = message.get("type") if isinstance(message, dict) else None
                    if message_type == "activity":
                        last_activity[0] = loop.time()
                        enqueue_control({"type": "client_activity"})
                    elif message_type == "stop":
                        enqueue_control({"type": "client_stop"})
                        return
            except (WebSocketDisconnect, RuntimeError, ValueError):
                enqueue_control({"type": "client_disconnected"})

        receiver_task = asyncio.create_task(receive_controls())
        inactivity_timeout = max(60, settings.live_tail_inactivity_timeout_seconds)

        while True:
            remaining = inactivity_timeout - (loop.time() - last_activity[0])
            if remaining <= 0:
                await websocket.send_json(
                    {
                        "type": "session_stopped",
                        "reason": f"Stopped after {inactivity_timeout // 60} minutes of inactivity.",
                    }
                )
                break

            try:
                message = await asyncio.wait_for(queue.get(), timeout=remaining)
            except TimeoutError:
                await websocket.send_json(
                    {
                        "type": "session_stopped",
                        "reason": f"Stopped after {inactivity_timeout // 60} minutes of inactivity.",
                    }
                )
                break

            message_type = message.get("type")
            if message_type == "client_activity":
                continue
            if message_type == "client_disconnected":
                disconnected = True
                break
            if message_type == "client_stop":
                await websocket.send_json(
                    {"type": "session_stopped", "reason": "Stopped by user."}
                )
                break
            if message_type == "session_started":
                last_activity[0] = loop.time()
                message.update(
                    {
                        "inactivity_timeout_seconds": inactivity_timeout,
                        "cost_per_minute_usd": settings.live_tail_cost_per_minute_usd,
                        "free_tier_minutes": settings.live_tail_free_tier_minutes,
                    }
                )

            await websocket.send_json(message)
            if message_type in {"error", "session_ended"}:
                break
    except WebSocketDisconnect:
        disconnected = True
    finally:
        stop_event.set()
        stream = stream_holder.get("stream")
        close = getattr(stream, "close", None)
        if callable(close):
            with suppress(Exception):
                close()

        if not disconnected and websocket.application_state == WebSocketState.CONNECTED:
            with suppress(RuntimeError):
                await websocket.close(code=1000)
        if receiver_task:
            receiver_task.cancel()
            with suppress(asyncio.CancelledError, asyncio.TimeoutError):
                await asyncio.wait_for(receiver_task, timeout=1)
        if worker_thread and worker_done and worker_thread.is_alive():
            shutdown_loop = asyncio.get_running_loop()
            deadline = shutdown_loop.time() + 3
            while not worker_done.is_set() and shutdown_loop.time() < deadline:
                await asyncio.sleep(0.01)
        if acquired:
            await live_tail_sessions.release()
