# Cloud Deployment Security

Security measures implemented for the FastAPI/WebSocket/xterm.js trainer on GCP Cloud Run.

**Prerequisites for tests:**
```bash
uv add websockets
export SERVICE_URL=<your-service-url>
: "${SERVICE_URL:?Set SERVICE_URL first}"
```

---

## Implemented measures

### 1. SRI hashes on CDN assets

All xterm.js assets loaded from `cdn.jsdelivr.net` carry `integrity="sha384-..."` and `crossorigin="anonymous"` attributes (`web/index.html`), preventing execution if the CDN content is tampered with.

**Test:**
```bash
curl -s https://$SERVICE_URL/ | grep -o 'integrity="[^"]*"'
```
**Expected:** four `integrity="sha384-..."` lines (xterm CSS, xterm JS, xterm-addon-fit, xterm-addon-attach).

---

### 2. Origin validation

Origin is checked before `websocket.accept()`. Rejected connections receive HTTP 403 / close code `1008`. Set `WS_ALLOWED_ORIGINS` (comma-separated) to enable; leave empty to skip the check for local dev.

**Test:**
```bash
uv run python3 -c "
import asyncio, websockets

async def test():
    try:
        async with websockets.connect(
            'wss://$SERVICE_URL/ws',
            additional_headers={'Origin': 'https://evil.example.com'}
        ) as ws:
            print('Connected (unexpected)')
    except websockets.exceptions.InvalidStatus as e:
        print(f'Rejected at handshake: HTTP {e.response.status_code}')  # expect 403
    except websockets.exceptions.ConnectionClosedError as e:
        print(f'Rejected with code: {e.code}')  # expect 1008

asyncio.run(test())
"
```
**Expected:** `Rejected at handshake: HTTP 403`

---

### 3. Connection cap

`_active_connections` counter with `WS_MAX_CONNECTIONS` (default 100). Connections over the cap receive HTTP 503 / close code `1013 Try Again Later`.

**Test** (temporarily lower the cap first):
```bash
gcloud run services update blackjack-trainer \
  --region us-central1 \
  --set-env-vars WS_MAX_CONNECTIONS=3
```
```bash
uv run python3 -c "
import asyncio, websockets

async def open_conn(n):
    try:
        ws = await websockets.connect(
            'wss://$SERVICE_URL/ws',
            additional_headers={'Origin': 'https://$SERVICE_URL'}
        )
        print(f'Conn {n}: accepted')
        return ws
    except websockets.exceptions.InvalidStatus as e:
        print(f'Conn {n}: rejected at handshake: HTTP {e.response.status_code}')
        return None
    except websockets.exceptions.ConnectionClosedError as e:
        print(f'Conn {n}: rejected with code {e.code}')
        return None

async def test():
    conns = [await open_conn(i) for i in range(4)]
    await asyncio.sleep(2)
    for ws in conns:
        if ws: await ws.close()

asyncio.run(test())
"
```
**Expected:** first 3 accepted, 4th rejected with `HTTP 503`. Restore: `--set-env-vars WS_MAX_CONNECTIONS=100`.

---

### 4. Per-message size limit

Messages larger than `WS_MAX_MESSAGE_BYTES` (default 16 bytes) drop the connection with code `1009`. 16 bytes covers any legitimate xterm.js keypress including multi-byte escape sequences.

**Test:**
```bash
uv run python3 -c "
import asyncio, websockets

async def test():
    async with websockets.connect(
        'wss://$SERVICE_URL/ws',
        additional_headers={'Origin': 'https://$SERVICE_URL'}
    ) as ws:
        await ws.send('x' * 20)
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                print('Still open, got:', repr(msg[:50]))
        except websockets.exceptions.ConnectionClosed as e:
            print(f'Connection closed after oversized msg: {e.code}')  # expect 1009

asyncio.run(test())
"
```
**Expected:** connection closed with code `1009`.

---

### 5. Idle session timeout

Sessions that send no messages for `WS_IDLE_TIMEOUT` seconds (default 300) are closed with code `1011`.

**Test** (temporarily lower the timeout):
```bash
gcloud run services update blackjack-trainer \
  --region us-central1 \
  --set-env-vars WS_IDLE_TIMEOUT=10
```
```bash
uv run python3 -c "
import asyncio, websockets

async def test():
    async with websockets.connect(
        'wss://$SERVICE_URL/ws',
        additional_headers={'Origin': 'https://$SERVICE_URL'}
    ) as ws:
        print('Connected, waiting for idle timeout...')
        try:
            while True:
                await ws.recv()  # drain server messages; never send anything back
        except websockets.exceptions.ConnectionClosed as e:
            print(f'Server closed idle connection: {e.code}')  # expect 1011

asyncio.run(test())
"
```
**Expected:** server closes after ~10 seconds. Restore: `--set-env-vars WS_IDLE_TIMEOUT=300`.

---

### 6. Structured logging

`logger.exception()` replaces bare `except: pass`. Connection open/close, origin rejections, cap hits, oversized messages, and idle timeouts are all logged at INFO/WARNING. Cloud Run forwards stdout/stderr to Cloud Logging automatically.

**Verify after running the above tests:**
```bash
gcloud logging read 'resource.type="cloud_run_revision" textPayload=~"Rejected|Oversized|Idle timeout"' --limit=50 --format="table(timestamp,textPayload)"
```
**Expected log lines:**
- `Rejected WS — bad origin: https://evil.example.com`
- `Rejected WS — cap reached (3/3)`
- `Oversized message (20 bytes) — closing`
- `Idle timeout — closing session`

---

### 7. Security headers

Five HTTP security headers are added by middleware (`web/server.py`):

```
strict-transport-security: max-age=31536000; includeSubDomains
x-frame-options: DENY
x-content-type-options: nosniff
referrer-policy: strict-origin-when-cross-origin
content-security-policy: default-src 'none'; script-src 'self' https://cdn.jsdelivr.net; ...
```

**Test:**
```bash
curl -sI https://$SERVICE_URL/ | grep -Ei "strict-transport|x-frame|x-content-type|referrer-policy|content-security-policy"
```
**Expected:** five lines, one per header.

---

## Future enhancements

- **WebSocket authentication** — the endpoint is currently open to any client that can reach the URL. Options: Cloud Run IAM (remove `--allow-unauthenticated`, zero code changes), a shared secret token in the URL (`/ws?token=...`), or a reverse proxy enforcing auth before the WebSocket upgrade.
- **HTTPS redirect** — HTTP is not actively redirected to HTTPS at the platform level. On Cloud Run this requires a load balancer rule or Cloud Armor policy; App Runner enforces HTTPS by default on its managed domain.
