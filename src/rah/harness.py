"""Owned agent loop: messages -> model decision -> container tool -> observation."""
import hashlib
import json
import os
import re
import threading
import time
import uuid

from fastapi import Header, HTTPException
from fastapi.responses import StreamingResponse

from rah.common import app_for, remote
from rah.protocol import SYSTEM, decision

app = app_for("harness")
sessions = {}
provisions = {}
lock = threading.RLock()
SANDBOX = os.environ.get("SANDBOX_URL", "http://sandbox-manager:8000")
LLM = os.environ.get("LLM_URL", "http://llm-proxy:8000")


def owned(sid, owner):
    s = sessions.get(sid)
    if not s or not owner or s["owner"] != owner:
        raise HTTPException(404, "unknown session")
    return s


def emit(s, kind, data):
    with lock:
        event = {"version": "0", "id": len(s["events"]) + 1, "type": kind, "data": data}
        s["events"].append(event)
        return event


def finish(s, op, result):
    with lock:
        if op["state"] == "finished":
            return
        op.update(state="finished", result={"version": "0", **result})
        s["result"] = op["result"]
        emit(s, "result", {"request_id": op["request_id"], "outcome": result["outcome"], "error_type": (result.get("error") or {}).get("type"), "model": result.get("model"), "provider": result.get("provider"), "usage": result.get("usage", {}), "seconds": result.get("seconds", 0)})


@app.post("/v0/sessions")
def provision(body: dict, x_owner: str = Header(default="")):
    if not x_owner:
        raise HTTPException(403, "missing owner")
    rid = body.get("request_id")
    fingerprint = hashlib.sha256(json.dumps(body.get("files", {}), sort_keys=True).encode()).hexdigest()
    with lock:
        key = (x_owner, rid)
        if rid and key in provisions:
            sid = provisions[key]
            if sessions[sid]["fingerprint"] != fingerprint:
                raise HTTPException(409, "provision request_id conflict")
            return {"version": "0", "session_id": sid}
        if len(sessions) >= 128:
            raise HTTPException(429, "checkpoint session capacity reached; restart after releasing sessions")
        sid = uuid.uuid4().hex
        remote(SANDBOX + "/v0/sessions", "POST", {"session_id": sid, "files": body.get("files", {})})
        sessions[sid] = {"owner": x_owner, "fingerprint": fingerprint, "events": [], "operations": {}, "result": None, "cancelled": False, "released": False}
        if rid:
            provisions[key] = sid
    return {"version": "0", "session_id": sid}


def agent_loop(sid, s, op, body):
    started = time.monotonic()
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": body["prompt"]}]
    usage, info = {}, {"model": None, "provider": None, "synthetic": False}
    outcome, failure, text = "failed", None, ""
    try:
        for step in range(40):
            if s["cancelled"]:
                return
            if time.monotonic() - started > 300:
                failure = {"type": "timeout", "message": "run exceeded 300 seconds"}
                remote(SANDBOX + f"/v0/sessions/{sid}/cancel", "POST", {})
                break
            request = {"messages": messages, "step": step}
            if "replay" in body:
                request["replay"] = body["replay"]
            response = remote(LLM + "/v0/decision", "POST", request)
            if s["cancelled"]:
                return
            value = response["decision"]
            args = decision(value)
            info = {k: response.get(k) for k in ("model", "provider", "synthetic")}
            for key, count in response.get("usage", {}).items():
                if isinstance(count, (int, float)):
                    usage[key] = usage.get(key, 0) + count
            emit(s, "model", {"step": step, **info})
            messages.append({"role": "assistant", "content": json.dumps(value)})
            if value["kind"] == "final":
                text, outcome = value["text"], "completed"
                break
            result = remote(SANDBOX + f"/v0/sessions/{sid}/exec", "POST", {"request_id": f"{op['request_id']}-{step}", "tool": value["tool"], "args": args, "timeout": 30})
            observation = result.get("result", {})
            emit(s, "tool", {"step": step, "tool": value["tool"], "error_type": (observation.get("error") or {}).get("type"), "exit_code": observation.get("exit_code")})
            messages.append({"role": "user", "content": "Tool observation: " + json.dumps(observation)})
            if (observation.get("error") or {}).get("type") in {"timeout", "sandbox", "output_limit"}:
                failure = observation["error"]
                break
        else:
            failure = {"type": "step_limit", "message": "40 tool decisions exhausted"}
    except HTTPException as exc:
        failure = {"type": "transport" if exc.status_code == 502 else "sandbox", "message": "upstream operation failed; inspect status before retry"}
    except Exception:
        failure = {"type": "model", "message": "invalid model decision"}
    finish(s, op, {"outcome": outcome, "text": text, "error": failure, "usage": usage, "seconds": round(time.monotonic() - started, 3), **info})


@app.post("/v0/sessions/{sid}/runs")
def run(sid: str, body: dict, x_owner: str = Header(default="")):
    s = owned(sid, x_owner)
    rid, prompt = body.get("request_id", ""), body.get("prompt", "")
    if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", rid) or not isinstance(prompt, str) or not 1 <= len(prompt) <= 20000:
        raise ValueError("valid request_id and bounded prompt required")
    if "replay" in body:
        if not isinstance(body["replay"], list) or len(body["replay"]) > 40:
            raise ValueError("replay must contain at most 40 decisions")
        for value in body["replay"]:
            decision(value)
    fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    with lock:
        if rid in s["operations"]:
            op = s["operations"][rid]
            if op["fingerprint"] != fingerprint:
                raise HTTPException(409, "request_id conflict")
            return {k: v for k, v in op.items() if k != "fingerprint"}
        if s["released"] or s["cancelled"] or any(o["state"] == "running" for o in s["operations"].values()):
            raise HTTPException(409, "session released, cancelled or busy")
        op = {"version": "0", "request_id": rid, "state": "running", "fingerprint": fingerprint}
        s["operations"][rid] = op
        emit(s, "started", {"request_id": rid})
        threading.Thread(target=agent_loop, args=(sid, s, op, body), daemon=True).start()
    return {k: v for k, v in op.items() if k != "fingerprint"}


@app.get("/v0/sessions/{sid}/operations/{rid}")
def operation(sid: str, rid: str, x_owner: str = Header(default="")):
    op = owned(sid, x_owner)["operations"].get(rid)
    if not op:
        raise HTTPException(404, "unknown operation")
    return {k: v for k, v in op.items() if k != "fingerprint"}


@app.get("/v0/sessions/{sid}/result")
def result(sid: str, x_owner: str = Header(default="")):
    s = owned(sid, x_owner)
    return s["result"] or {"version": "0", "outcome": "running"}


@app.get("/v0/sessions/{sid}/trace")
def trace(sid: str, x_owner: str = Header(default="")):
    return {"version": "0", "events": list(owned(sid, x_owner)["events"])}


@app.get("/v0/sessions/{sid}/events")
def events(sid: str, after: int = 0, last_event_id: str = Header(default=""), x_owner: str = Header(default="")):
    s = owned(sid, x_owner)
    cursor = int(last_event_id) if last_event_id else after
    if cursor < 0 or cursor > len(s["events"]):
        raise ValueError("invalid event cursor")
    def stream():
        nonlocal cursor
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            pending = list(s["events"][cursor:])
            for event in pending:
                cursor = event["id"]
                yield f"id: {cursor}\nevent: {event['type']}\ndata: {json.dumps(event)}\n\n"
            if not any(op["state"] == "running" for op in s["operations"].values()):
                return
            time.sleep(0.1)
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/v0/sessions/{sid}/collect")
def collect(sid: str, body: dict, x_owner: str = Header(default="")):
    owned(sid, x_owner)
    return remote(SANDBOX + f"/v0/sessions/{sid}/collect", "POST", body)


@app.post("/v0/sessions/{sid}/cancel")
def cancel(sid: str, x_owner: str = Header(default="")):
    s = owned(sid, x_owner)
    s["cancelled"] = True
    result = remote(SANDBOX + f"/v0/sessions/{sid}/cancel", "POST", {})
    for op in s["operations"].values():
        finish(s, op, {"outcome": "cancelled", "error": {"type": "cancelled", "message": "sandbox removed; tmpfs artifacts lost"}, "usage": {}})
    return result


@app.post("/v0/sessions/{sid}/release")
def release(sid: str, x_owner: str = Header(default="")):
    s = owned(sid, x_owner)
    if any(op["state"] == "running" for op in s["operations"].values()):
        cancel(sid, x_owner)
    result = remote(SANDBOX + f"/v0/sessions/{sid}/release", "POST", {})
    s["released"] = True
    return result
