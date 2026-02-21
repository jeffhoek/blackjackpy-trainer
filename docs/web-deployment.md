# Web UI

Browser-based blackjack trainer using FastAPI + WebSocket + xterm.js. The Python game logic runs server-side; the browser renders a real terminal via xterm.js connected over WebSocket.

## Running

```bash
uv run uvicorn web.server:app --reload
# open http://localhost:8000
```

## Architecture

```
browser                           server
├── xterm.js (CDN)   ←──WS──►   ├── FastAPI (web/server.py)
└── index.html                   └── WebSession (web/session.py)
                                      └── Trainer / Strategy (unchanged)
```

One WebSocket per browser session. The server streams raw ANSI bytes to the client; xterm.js renders them natively with no transformation. Keystrokes flow the other direction as plain text. No build step — xterm.js and its addons load from CDN.

## Files

**`web/server.py`** — FastAPI app with two routes:
- `GET /` serves `web/index.html`
- `WebSocket /ws` accepts a connection, wires up send/recv asyncio queues, and runs a `WebSession`

The sender task drains the send queue to the WebSocket; the receiver task feeds incoming characters into the recv queue. After the session ends, `asyncio.Queue.join()` ensures all buffered output is flushed before the connection closes. A `None` sentinel in the recv queue signals client disconnection.

**`web/session.py`** — `WebSession` class that mirrors the flow of `blackjack/ui.py` using async I/O:
- `send(text)` replaces `print()`
- `recv_line()` replaces `input()` — collects characters into a buffer, echoes them back, handles backspace, and returns on Enter
- `recv_char()` replaces `getch()` — returns the next single character
- Line endings use `\r\n` for raw terminal compatibility

The session runs the same three phases as the CLI: welcome screen → rules configuration → training loop → final stats.

**`web/index.html`** — Single-file frontend. xterm.js, FitAddon, and AttachAddon are loaded from jsDelivr CDN (xterm 5.3.0). The terminal fills the full viewport with a dark background. `AttachAddon` connects the WebSocket directly to the terminal — incoming text is rendered, keystrokes are sent back. `FitAddon` resizes the terminal on window resize. A close handler displays a reconnect prompt if the server disconnects.

## Dependencies

`fastapi` and `uvicorn[standard]` are declared in `pyproject.toml` and installed into the project virtualenv. The existing CLI and test suite are unaffected.
