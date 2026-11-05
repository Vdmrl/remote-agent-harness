"""The only service allowed to access Docker. No host execution fallback."""
import base64
import hashlib
import io
import json
import os
import re
import tarfile
import threading
import time
import uuid

import docker
from fastapi import HTTPException

from rah.common import MAX_BYTES, MAX_FILES, MAX_OUTPUT, app_for, path_ok, validate_payload

app = app_for("sandbox-manager")
sessions = {}
lock = threading.RLock()


def engine():
    return docker.from_env(timeout=5)


def fixtures(files):
    if not isinstance(files, dict) or len(files) > MAX_FILES:
        raise ValueError("fixtures must be a bounded mapping of paths to base64")
    archive, size = io.BytesIO(), 0
    with tarfile.open(fileobj=archive, mode="w") as tar:
        for name, content in sorted(files.items()):
            path_ok(name)
            if not isinstance(content, str):
                raise ValueError("file content must be base64")
            try:
                data = base64.b64decode(content, validate=True)
            except Exception as exc:
                raise ValueError("invalid base64") from exc
            size += len(data)
            if len(data) > 65536 or size > MAX_BYTES:
                raise ValueError("fixture too large")
            member = tarfile.TarInfo(name)
            member.size, member.uid, member.gid, member.mode = len(data), 10001, 10001, 0o600
            tar.addfile(member, io.BytesIO(data))
    return archive.getvalue()


def session(sid):
    if sid not in sessions:
        raise HTTPException(404, "unknown sandbox")
    return sessions[sid]


def destroy(s):
    if not s.get("removed"):
        try:
            s["container"].remove(force=True)
        except docker.errors.NotFound:
            pass
        s["removed"] = True


@app.on_event("startup")
def reap():
    # Manager restart loses in-memory operations: remove only this project's labeled sandboxes.
    for container in engine().containers.list(all=True, filters={"label": "rah.sandbox=checkpoint-one"}):
        container.remove(force=True)


@app.on_event("shutdown")
def cleanup():
    for value in list(sessions.values()):
        destroy(value)


@app.post("/v0/sessions")
def provision(body: dict):
    validate_payload("harness-sandbox", "provision", body)
    archive = fixtures(body.get("files", {}))
    sid = body.get("session_id", "")
    if not re.fullmatch(r"[a-f0-9]{32}", sid):
        raise ValueError("invalid session id")
    fingerprint = hashlib.sha256(archive).hexdigest()
    with lock:
        if sid in sessions:
            if sessions[sid]["fingerprint"] != fingerprint:
                raise HTTPException(409, "session id reused with different fixtures")
            return {"version": "0", "session_id": sid}
        container = engine().containers.run(os.environ.get("SANDBOX_IMAGE", "remote-agent-harness-sandbox:0.1.0"), detach=True, name="rah-" + sid,
            user="10001:10001", network_mode="none", read_only=True, cap_drop=["ALL"], security_opt=["no-new-privileges:true"],
            mem_limit="256m", memswap_limit="256m", nano_cpus=1_000_000_000, pids_limit=64,
            tmpfs={"/work": "rw,noexec,nosuid,nodev,size=16m,uid=10001,gid=10001,mode=0700", "/tmp": "rw,noexec,nosuid,nodev,size=8m,uid=10001,gid=10001,mode=0700"},
            labels={"rah.sandbox": "checkpoint-one"}, environment={"PYTHONDONTWRITEBYTECODE": "1"})
        value = {"container": container, "operations": {}, "fingerprint": fingerprint, "removed": False, "busy": False}
        sessions[sid] = value
        try:
            container.put_archive("/work", archive)
        except Exception:
            destroy(value)
            raise
    return {"version": "0", "session_id": sid}


def execute(s, body):
    timeout = body.get("timeout", 30)
    if not isinstance(timeout, (int, float)) or not 0.1 <= timeout <= 120:
        raise ValueError("timeout must be 0.1..120 seconds")
    tool = body.get("tool")
    if tool not in {"list", "read", "write", "exec", "collect"}:
        raise ValueError("unknown tool")
    payload = base64.b64encode(json.dumps({"tool": tool, "args": body.get("args", {})}).encode()).decode()
    if len(payload) > 120000:
        raise ValueError("tool arguments too large")
    data, failure, done = bytearray(), [], threading.Event()
    api = engine().api
    eid = api.exec_create(s["container"].id, ["python", "-m", "rah.worker", payload], user="10001:10001", workdir="/work")["Id"]

    def consume():
        try:
            for chunk in api.exec_start(eid, stream=True):
                data.extend(chunk)
                if len(data) > (4 * MAX_BYTES if tool == "collect" else MAX_OUTPUT * 2):
                    failure.append("output_limit")
                    destroy(s)
                    break
        except Exception:
            failure.append("sandbox")
        finally:
            done.set()
    threading.Thread(target=consume, daemon=True).start()
    if not done.wait(timeout):
        destroy(s)
        return {"error": {"type": "timeout", "message": "sandbox removed; tmpfs artifacts lost"}}
    if failure:
        return {"error": {"type": failure[0], "message": "sandbox stopped or output exceeded bound"}}
    try:
        return json.loads(data)
    except (ValueError, UnicodeError):
        return {"error": {"type": "sandbox", "message": "tool worker failed"}}


@app.post("/v0/sessions/{sid}/exec")
def exec_tool(sid: str, body: dict):
    validate_payload("harness-sandbox", "exec", body)
    s = session(sid)
    rid = body.get("request_id", "")
    if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", rid):
        raise ValueError("invalid request_id")
    fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    with lock:
        if rid in s["operations"]:
            op = s["operations"][rid]
            if op["fingerprint"] != fingerprint:
                raise HTTPException(409, "request_id reused with different arguments")
            return {k: v for k, v in op.items() if k != "fingerprint"}
        if s["removed"] or s["busy"]:
            raise HTTPException(409, "sandbox removed or busy")
        op = {"version": "0", "request_id": rid, "state": "running", "fingerprint": fingerprint}
        s["operations"][rid] = op
        s["busy"] = True
    try:
        result = execute(s, body)
    except ValueError as exc:
        result = {"error": {"type": "tool", "message": str(exc)}}
    except Exception:
        result = {"error": {"type": "sandbox", "message": "Docker execution failed"}}
    with lock:
        op.update(state="finished", result=result)
        s["busy"] = False
    return {k: v for k, v in op.items() if k != "fingerprint"}


@app.get("/v0/sessions/{sid}/operations/{rid}")
def operation(sid: str, rid: str):
    op = session(sid)["operations"].get(rid)
    if op is None:
        raise HTTPException(404, "unknown operation")
    return {k: v for k, v in op.items() if k != "fingerprint"}


@app.post("/v0/sessions/{sid}/collect")
def collect(sid: str, body: dict):
    validate_payload("harness-sandbox", "collect", body)
    return exec_tool(sid, {"request_id": body["request_id"], "tool": "collect", "timeout": 15})


@app.post("/v0/sessions/{sid}/cancel")
@app.post("/v0/sessions/{sid}/release")
def release(sid: str):
    destroy(session(sid))
    return {"version": "0", "state": "released", "artifacts_lost": True}
