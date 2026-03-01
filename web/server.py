"""FastAPI server for the browser-based blackjack trainer."""

import asyncio
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response

from web.session import Disconnected, WebSession

logger = logging.getLogger(__name__)

_MAX_CONNECTIONS = int(os.environ.get("WS_MAX_CONNECTIONS", "100"))
_MAX_MESSAGE_BYTES = int(os.environ.get("WS_MAX_MESSAGE_BYTES", "16"))
_IDLE_TIMEOUT = float(os.environ.get("WS_IDLE_TIMEOUT", "300"))
_ALLOWED_ORIGINS: set[str] = set(
    filter(None, os.environ.get("WS_ALLOWED_ORIGINS", "").split(","))
)

_active_connections: int = 0

app = FastAPI()

_SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'none'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "img-src 'self';"
    ),
}


@app.middleware("http")
async def add_security_headers(request: Request, call_next: object) -> Response:
    response = await call_next(request)  # type: ignore[operator]
    response.headers.update(_SECURITY_HEADERS)
    return response


_DATA_DIR = Path(__file__).parent.parent / "data"
_INDEX_HTML = Path(__file__).parent / "index.html"
_APP_JS = Path(__file__).parent / "app.js"


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse(_INDEX_HTML.read_text())


@app.get("/app.js")
async def app_js() -> Response:
    return Response(_APP_JS.read_text(), media_type="application/javascript")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    global _active_connections

    origin = websocket.headers.get("origin", "")
    if _ALLOWED_ORIGINS and origin not in _ALLOWED_ORIGINS:
        await websocket.send({"type": "websocket.http.response.start", "status": 403, "headers": []})
        await websocket.send({"type": "websocket.http.response.body", "body": b"", "more_body": False})
        logger.warning("Rejected WS — bad origin: %s", origin)
        return
    if _active_connections >= _MAX_CONNECTIONS:
        await websocket.send({"type": "websocket.http.response.start", "status": 503, "headers": []})
        await websocket.send({"type": "websocket.http.response.body", "body": b"", "more_body": False})
        logger.warning(
            "Rejected WS — cap reached (%d/%d)", _active_connections, _MAX_CONNECTIONS
        )
        return

    await websocket.accept()
    _active_connections += 1
    logger.info("WS opened (active=%d)", _active_connections)

    send_queue: asyncio.Queue[str] = asyncio.Queue()
    recv_queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def sender() -> None:
        """Forward messages from send_queue to WebSocket, tracking task_done."""
        try:
            while True:
                text = await send_queue.get()
                try:
                    await websocket.send_text(text)
                finally:
                    send_queue.task_done()
        except Exception:
            pass

    async def receiver() -> None:
        """Forward incoming WebSocket messages to recv_queue as individual chars."""
        try:
            while True:
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_text(), timeout=_IDLE_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    logger.info("Idle timeout — closing session")
                    break
                if len(data) > _MAX_MESSAGE_BYTES:
                    logger.warning("Oversized message (%d bytes) — closing", len(data))
                    await websocket.close(code=1009)
                    break
                for ch in data:
                    await recv_queue.put(ch)
        except (WebSocketDisconnect, Exception):
            pass
        finally:
            await recv_queue.put(None)  # signal disconnection

    sender_task = asyncio.create_task(sender())
    receiver_task = asyncio.create_task(receiver())

    session = WebSession(send_queue, recv_queue, _DATA_DIR)
    try:
        await session.run()
    except Disconnected:
        pass
    except Exception:
        logger.exception("Unhandled error in WebSocket session")
    finally:
        _active_connections -= 1
        logger.info("WS closed (active=%d)", _active_connections)
        receiver_task.cancel()
        sender_task.cancel()
        await asyncio.gather(sender_task, receiver_task, return_exceptions=True)
        try:
            await websocket.close()
        except Exception:
            pass
