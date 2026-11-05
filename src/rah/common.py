"""Shared wire validation, authentication, and bounded HTTP transport."""
import hashlib
import json
import os
import secrets
from pathlib import PurePosixPath

import httpx
from fastapi import FastAPI, HTTPException, Request

VERSION = "0"
MAX_FILES = 512
MAX_BYTES = 2 * 1024 * 1024
MAX_BODY = 6 * 1024 * 1024
MAX_OUTPUT = 128 * 1024


def error(kind, message):
    return {"version": VERSION, "error": {"type": kind, "message": message}}


def path_ok(value):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("path must be relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value == "." or len(value) > 240:
        raise ValueError("path escapes /work or is too long")
    return value


def app_for(role):
    app = FastAPI(title=f"remote-agent-harness {role}", version="0.1.0")
    token = os.environ.get("RAH_TOKEN", "")
    if not token:
        raise RuntimeError("RAH_TOKEN must be set")

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
        allowed = os.environ.get("CLIENT_TOKENS", token).split(",") if role == "gateway" else [token]
        if not any(secrets.compare_digest(supplied, x.strip()) for x in allowed if x.strip()):
            from fastapi.responses import JSONResponse
            return JSONResponse(error("auth", "unauthorized"), status_code=401)
        if request.headers.get("x-schema-version") != VERSION:
            from fastapi.responses import JSONResponse
            return JSONResponse(error("version", "X-Schema-Version must be 0"), status_code=400)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY:
                from fastapi.responses import JSONResponse
                return JSONResponse(error("validation", "request too large"), status_code=413)
        request._body = bytes(body)
        request.state.owner = hashlib.sha256(supplied.encode()).hexdigest()
        return await call_next(request)

    @app.get("/health")
    def health():
        return {"version": VERSION, "status": "ok", "service": role}

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(error("validation", str(exc)), status_code=400)

    return app


def headers(owner=None):
    result = {"Authorization": "Bearer " + os.environ["RAH_TOKEN"], "X-Schema-Version": VERSION}
    if owner:
        result["X-Owner"] = owner
    return result


def remote(url, method="GET", body=None, owner=None, timeout=130):
    """Never retry a mutation: its outcome may be unknown after transport loss."""
    try:
        with httpx.stream(method, url, json=body, headers=headers(owner), timeout=timeout) as response:
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > MAX_BODY:
                    raise ValueError("upstream response too large")
            result = json.loads(data)
            if response.is_error:
                raise HTTPException(response.status_code, result)
            return result
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise HTTPException(502, error("transport", "upstream unavailable; query operation status before retry")) from exc
