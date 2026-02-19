# Web Deployment Plan

Browser-based blackjack trainer using FastAPI + WebSocket + xterm.js.

## Architecture

```
browser                           server
├── xterm.js (CDN)   ←──WS──►   ├── FastAPI (web/server.py)
└── index.html                   └── async game session
                                      └── Trainer / Strategy (unchanged)
```

## Implementation Checklist

- [ ] Add `fastapi` and `uvicorn[standard]` to `pyproject.toml`
- [ ] Create `web/` package directory
- [ ] Create `web/session.py` — async game session (send/recv queues)
- [ ] Create `web/server.py` — FastAPI app with WebSocket endpoint + static file serving
- [ ] Create `web/index.html` — xterm.js terminal connected to WebSocket
- [ ] Smoke-test: run server locally, open browser, complete a full training session
- [ ] Verify existing CLI (`uv run python main.py`) still works
- [ ] Verify `uv run pytest` still passes
