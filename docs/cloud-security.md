# Cloud Deployment Security Plan

Security findings for deploying the FastAPI/WebSocket/xterm.js trainer to GCP Cloud Run or AWS App Runner, ordered by severity.

---

## 1. HIGH — CDN Supply Chain Risk (SRI missing)

**File:** `web/index.html:9,20-22`

xterm.js and its addons are loaded from `cdn.jsdelivr.net` with no integrity verification:

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.min.css" />
<script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xterm-addon-attach@0.9.0/lib/xterm-addon-attach.min.js"></script>
```

If jsdelivr is compromised or the package version is tampered with, a malicious script runs in every user's browser with full WebSocket access — allowing arbitrary keystrokes to be injected into sessions.

**Fix:** Add [Subresource Integrity (SRI)](https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity) hashes and `crossorigin="anonymous"` to each external asset. Generate hashes with:

```bash
curl -s https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.min.js | openssl dgst -sha384 -binary | openssl base64 -A
```

Example:
```html
<script
  src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.min.js"
  integrity="sha384-<hash>"
  crossorigin="anonymous"
></script>
```

---

## 2. HIGH — No Authentication on WebSocket Endpoint

**File:** `web/server.py:24`

```python
await websocket.accept()  # unconditional — no auth check
```

Any client that can reach the service URL can open a session. On Cloud Run with `--allow-unauthenticated`, this means the entire internet.

**Options (pick one based on use case):**

- **Cloud Run IAM** (easiest for personal/team use): Remove `--allow-unauthenticated` and require a Google Identity token. Zero app-code changes needed.
- **Shared secret**: Require a token in the WebSocket URL (`/ws?token=...`) or as the first message, reject connections that fail.
- **Reverse proxy auth**: Sit behind Cloud Endpoints, API Gateway, or an nginx sidecar that enforces auth before the WebSocket upgrade.

---

## 3. HIGH — Resource Exhaustion (no connection limit)

**File:** `web/server.py:53-54`

Each WebSocket connection creates two asyncio tasks and a `Trainer` instance that persists for the life of the session. There is no cap on concurrent connections.

An attacker can open thousands of connections, exhausting memory and asyncio task slots, which would degrade or crash the service.

**Fix:**

- Set a global connection counter with a hard limit (e.g., 100 concurrent sessions), rejecting new connections over the limit with a `1013 Try Again Later` close code.
- Configure Cloud Run `--concurrency` and `--max-instances` as a secondary guardrail, not a primary one.
- Consider a platform-level rate limiter (Cloud Armor on GCP, WAF on AWS) to throttle connection attempts per IP.

---

## 4. MEDIUM — WebSocket Origin Not Validated

**File:** `web/server.py:24`

`websocket.accept()` does not check the `Origin` header. Any page on the web can instruct a logged-in user's browser to open a WebSocket to your service (cross-site WebSocket hijacking). This is lower severity if auth is added (item 2), but still worth closing independently.

**Fix:** Read the `Origin` header from the WebSocket handshake request and reject connections from unexpected origins:

```python
origin = websocket.headers.get("origin", "")
if origin not in ALLOWED_ORIGINS:
    await websocket.close(code=1008)
    return
await websocket.accept()
```

Define `ALLOWED_ORIGINS` as an environment variable so it can be set per deployment without code changes.

---

## 5. MEDIUM — No TLS Enforcement in Application

Both Cloud Run and App Runner terminate TLS at the load balancer, so `wss://` connections work. However, if HTTP is reachable at all, clients can connect unencrypted.

The frontend handles this correctly (`index.html:40-41`):
```js
const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
```
But if a user navigates to `http://`, they will use an unencrypted WebSocket.

**Fix:** Enforce HTTPS at the platform level:
- **Cloud Run:** Enable HTTP-to-HTTPS redirect in the load balancer or Cloud Armor policy.
- **App Runner:** Configure the service to reject HTTP; App Runner serves only HTTPS by default on the managed domain, but check custom domain settings.

---

## 6. LOW — Silent Exception Handling Hides Errors

**File:** `web/server.py:61`

```python
except Exception:
    pass
```

All session errors are swallowed silently. In production this makes it impossible to detect abuse patterns, unexpected crashes, or errors caused by malformed input.

**Fix:** Replace bare `pass` with structured logging:

```python
import logging
logger = logging.getLogger(__name__)

except Exception:
    logger.exception("Unhandled error in WebSocket session")
```

Cloud Run and App Runner both forward stdout/stderr to their respective logging services (Cloud Logging, CloudWatch) automatically — no extra configuration needed.

---

## Platform Comparison

| Concern | Cloud Run | App Runner |
|---|---|---|
| Public by default | Yes (if `--allow-unauthenticated`) | Yes |
| IAM auth at request level | Yes — easy to enable | No built-in option |
| WebSocket support | Yes (HTTP/2) | Yes (HTTP/1.1 upgrade) |
| HTTPS only by default | No — must configure | Yes on managed domain |
| Auto-scaling to zero | Yes | Optional |
| Rate limiting / WAF | Cloud Armor (paid) | AWS WAF (paid) |

**Recommendation:** Cloud Run is the better fit for this app. The IAM-based authentication eliminates items 2 and 4 with zero code changes, and Cloud Armor can handle item 3 at the network layer.

---

## Remediation Checklist

- [ ] Add SRI hashes to all CDN assets in `web/index.html`
- [ ] Require authentication on the WebSocket endpoint (IAM or token-based)
- [ ] Implement a concurrent connection cap with a `1013` close code for excess connections
- [ ] Validate `Origin` header before `websocket.accept()`
- [ ] Enforce HTTPS redirect at the platform or load balancer level
- [ ] Replace `except Exception: pass` with structured logging
