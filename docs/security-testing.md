# Security Testing — Cloud Run Deployment

Manual tests to verify each implemented security measure. Run these from your laptop against the live service.

**Prerequisites:**
```bash
uv add websockets
# pip install websockets
```
```
export SERVICE_URL=<ENTER-SERVICE-URL-HERE>
```

Verify it is set before running any test:
```bash
: "${SERVICE_URL:?Set SERVICE_URL first}"
```

---

## 1. Origin validation

If `WS_ALLOWED_ORIGINS` is set, connections with a bad or missing `Origin` header are rejected with HTTP 403.

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

## 2. Connection cap

When the cap is reached, new connections are rejected with HTTP 503.

To test without opening 100 connections, temporarily lower the cap:
```bash
gcloud run services update blackjack-trainer \
  --region us-central1 \
  --set-env-vars WS_MAX_CONNECTIONS=3
```

Then open 4 connections:

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

**Expected:** First 3 connections accepted, 4th rejected at handshake: `HTTP 503`.

Restore after:
```bash
gcloud run services update blackjack-trainer \
  --region us-central1 \
  --set-env-vars WS_MAX_CONNECTIONS=100
```

---

## 3. Oversized message

Messages larger than `WS_MAX_MESSAGE_BYTES` (default 16 bytes) cause the server to close the connection with code `1009`. The limit is set low because the UI only ever sends single keystrokes or short line inputs (deck count, y/n, etc.) — 16 bytes covers any legitimate xterm.js keypress, including multi-byte escape sequences.

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

**Expected:** Connection closed with code `1009` after sending the oversized message.

---

## 4. Idle timeout

The server closes sessions that send no messages for `WS_IDLE_TIMEOUT` seconds (default 300).

To avoid waiting 5 minutes, temporarily lower the timeout:
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

**Expected:** Server closes the connection after ~10 seconds.

Restore after:
```bash
gcloud run services update blackjack-trainer \
  --region us-central1 \
  --set-env-vars WS_IDLE_TIMEOUT=300
```

---

## 5. SRI hashes on CDN assets

All xterm.js CDN assets should have `integrity` attributes with `sha384` hashes.

```bash
curl -s https://$SERVICE_URL/ | grep -o 'integrity="[^"]*"'
```

**Expected:** Four lines of output, each showing `integrity="sha384-..."` — one per CDN asset (xterm CSS, xterm JS, xterm-addon-fit, xterm-addon-attach).

---

## 6. Security headers

All five security headers should be present on every HTTP response.

```bash
curl -sI https://$SERVICE_URL/ | grep -Ei "strict-transport|x-frame|x-content-type|referrer-policy|content-security-policy"
```

**Expected** — five lines, one per header:
```
strict-transport-security: max-age=31536000; includeSubDomains
x-frame-options: DENY
x-content-type-options: nosniff
referrer-policy: strict-origin-when-cross-origin
content-security-policy: default-src 'none'; script-src 'self' https://cdn.jsdelivr.net; ...
```

---

## 7. Cloud Run logs

After running the above tests, verify the server logged the rejection events:

```bash
gcloud logging read 'resource.type="cloud_run_revision" severity>=WARNING' \
  --limit=50 \
  --format="table(timestamp,textPayload)"
```

**Expected log lines:**
- `Rejected WS — bad origin: https://evil.example.com`
- `Rejected WS — cap reached (3/3)`
- `Oversized message (20 bytes) — closing`
- `Idle timeout — closing session`

---

## Not yet implemented

These two items from the security checklist are open and cannot be tested yet:

- **Authentication** — WebSocket endpoint is unauthenticated; any client can connect
- **HTTPS redirect** — HTTP connections are not redirected to HTTPS at the platform level
