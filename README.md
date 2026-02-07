# QAMax Adversary Site

A purpose-built hostile web page for testing the security hardening of the QualityMax demo crawl pipeline. Deployed on Railway and used in automated security tests.

**This is authorized security testing infrastructure. Do not use against systems you do not own.**

## How It Works

The site looks like an innocent "Demo Store" page, but on page load it silently executes 22 attack vectors against the visiting browser. Results are sent to an `/exfil` endpoint so the test suite can verify which attacks were blocked.

## Attack Vectors

### Basic Attacks (1-8)

| # | Category | Technique |
|---|----------|-----------|
| 1 | **Network Probing** | `fetch()` with `no-cors` to internal Docker hostnames (`db:5432`, `redis:6379`, `app:8000`), localhost, AWS/GCP metadata endpoints, and private IP ranges |
| 2 | **File Access** | `fetch()` to `file:///etc/passwd`, `file:///app/.env`, `file:///app/docker-compose.yml` |
| 3 | **Dialog Flood** | Staggered `alert()`, `confirm()`, `prompt()` calls to block automation |
| 4 | **Popup Flood** | 5x `window.open('about:blank')` to overwhelm popup handling |
| 5 | **Resource Bombs** | Infinite-loop Web Worker (CPU) + 100x100MB ArrayBuffer allocation (memory) |
| 6 | **CSRF** | Auto-submitting hidden form to `http://app:8000/api/projects` |
| 7 | **Redirect Chain** | `?redirect=true` triggers JS redirect to AWS metadata IP |
| 8 | **Exfiltration Beacon** | Collects `navigator.*` info and POSTs all results to `/exfil` |

### Advanced Attacks (9-22)

| # | Category | Technique |
|---|----------|-----------|
| 9 | **WebSocket Probing** | `new WebSocket('ws://db:5432')` — bypasses CORS, TCP handshake reaches target |
| 10 | **WebRTC IP Disclosure** | `RTCPeerConnection` + STUN server to leak Docker bridge IPs (172.17.x.x) |
| 11 | **Service Worker Registration** | `navigator.serviceWorker.register('/evil-sw.js')` for persistent MitM |
| 12 | **Prototype Pollution** | Override `JSON.parse`, `fetch`, `console.log` to intercept crawler's own data |
| 13 | **DOM Clobbering** | Named `<form id="document">` / `<img name="currentScript">` to shadow globals |
| 14 | **Performance Timing Oracle** | `performance.getEntriesByType('resource')` — connection timing reveals host existence |
| 15 | **EventSource/SSE Probing** | `new EventSource('http://db:5432')` — persistent reconnecting connections |
| 16 | **Beacon API Exfil** | `sendBeacon` + `fetch({keepalive:true})` + tracking pixel — survives page unload |
| 17 | **History API Manipulation** | Flood 50 `pushState` entries + `replaceState` URL spoofing |
| 18 | **Canvas/WebGL Fingerprinting** | Detect headless mode, GPU info, browser build fingerprint |
| 19 | **Clipboard Hijacking** | `navigator.clipboard.writeText()` + copy/cut event override |
| 20 | **Forced Downloads** | Auto-download `.env`, `.npmrc`, `docker-compose.override.yml` via Blob URLs |

Additionally, the HTML itself includes:
- Hidden `<iframe>` elements targeting internal services
- `<link rel="preload/prefetch/preconnect">` to internal hosts
- Malicious links disguised as "Database Status", "Cache Status", etc.

## Server Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serves the attack page |
| `/evil-sw.js` | GET | Malicious Service Worker script |
| `/redirect/{path}` | GET | HTTP 302 redirect to any URL |
| `/meta-redirect` | GET | HTML meta-refresh redirect to AWS metadata |
| `/exfil` | POST | Receives and stores exfiltration beacons |
| `/exfil-log` | GET | Returns all collected exfiltration data |
| `/reset` | POST | Clears the exfiltration log |
| `/health` | GET | Health check |

## Deployment

### Railway (Production)

The site auto-deploys to Railway on push to `main`. Current URL:
```
https://web-production-42cbf.up.railway.app/
```

### Local Development

```bash
pip install -r requirements.txt
uvicorn server:app --host 127.0.0.1 --port 9999
```

## Running Security Tests

From the QA RAG App repo:

```bash
# Against Railway deployment
ATTACKER_SITE_URL=https://web-production-42cbf.up.railway.app pytest tests/security/test_attacker_simulation.py -v

# Against local server (auto-clones and starts)
pytest tests/security/test_attacker_simulation.py -v

# Skip URL validation tests (need running QA RAG App)
pytest tests/security/test_attacker_simulation.py -v -k "not TestURLValidation"
```

## Checking Results

After a test run, inspect what the adversary site captured:

```bash
# View exfil log
curl https://web-production-42cbf.up.railway.app/exfil-log | python -m json.tool

# Reset log
curl -X POST https://web-production-42cbf.up.railway.app/reset
```

## Expected Results (Hardened Pipeline)

All attack vectors should show `blocked` or `error` status. Specifically:
- Network probes: `status: "blocked"` or `type: "opaque"` (no-cors)
- File access: `status: "blocked"`
- WebSocket/SSE probes: `status: "error"` or `status: "timeout"`
- WebRTC: no real Docker IPs leaked (no 172.17.x.x addresses)
- Service Worker: `status: "blocked"` (registration fails)
- Prototype pollution: overrides may install but shouldn't capture real data
- Canvas fingerprint: detects headless (informational, expected)
- Clipboard: `status: "blocked"` (no permission in headless)
- Dialogs/popups: handled without blocking execution
- Resource bombs: contained, browser stays functional
