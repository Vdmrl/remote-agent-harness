import json
import os
import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from rah.common import app_for, headers, remote

app = app_for("gateway")
HARNESS = os.environ.get("HARNESS_URL", "http://harness:8000")


@app.api_route("/v0/{path:path}", methods=["GET", "POST"])
async def forward(path: str, request: Request):
    url = HARNESS + "/v0/" + path
    if request.url.query:
        url += "?" + request.url.query
    owner = request.state.owner
    if request.method == "GET" and path.endswith("/events"):
        outgoing = headers(owner)
        if request.headers.get("last-event-id"):
            outgoing["Last-Event-ID"] = request.headers["last-event-id"]
        def stream():
            try:
                with httpx.stream("GET", url, headers=outgoing, timeout=40) as response:
                    if response.is_error:
                        yield 'event: error\ndata: {"error":"event stream rejected"}\n\n'
                        return
                    yield from response.iter_text()
            except httpx.HTTPError:
                yield 'event: error\ndata: {"error":"transport; reconnect after cursor"}\n\n'
        return StreamingResponse(stream(), media_type="text/event-stream")
    body = await request.json() if request.method == "POST" and await request.body() else None
    # Blocking upstream I/O belongs in a worker thread so cancel can arrive concurrently.
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(remote, url, request.method, body, owner)
