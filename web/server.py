"""FastAPI server for the browser-based blackjack trainer."""

import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from web.session import Disconnected, WebSession

app = FastAPI()

_DATA_DIR = Path(__file__).parent.parent / "data"
_INDEX_HTML = Path(__file__).parent / "index.html"


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse(_INDEX_HTML.read_text())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

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
                data = await websocket.receive_text()
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
        pass
    finally:
        # Flush any remaining output before closing
        await send_queue.join()
        sender_task.cancel()
        receiver_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass
