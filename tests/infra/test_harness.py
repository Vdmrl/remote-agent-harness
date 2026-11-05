import json
import asyncio
import threading
import time

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from rah import harness, llm_proxy
from rah.protocol import decision


def test_loop_events_idempotency_and_owner(monkeypatch):
    harness.sessions.clear()
    script = [
        {"kind": "tool", "tool": "write", "args": '{"path":"answer.txt","content":"42"}', "text": ""},
        {"kind": "final", "tool": "none", "args": "{}", "text": "done"},
    ]
    calls = []
    def upstream(url, method="GET", body=None, **kwargs):
        calls.append((url, body))
        if url.endswith("/decision"):
            return {"decision": script[body["step"]], "model": "test", "provider": "mock", "synthetic": True, "usage": {"input_tokens": 3}}
        if url.endswith("/exec"):
            return {"state": "finished", "result": {"bytes": 2}}
        return {"version": "0"}
    monkeypatch.setattr(harness, "remote", upstream)
    sid = harness.provision({"files": {}}, "alice")["session_id"]
    body = {"request_id": "one", "prompt": "write answer"}
    harness.run(sid, body, "alice")
    deadline = time.monotonic() + 2
    while harness.operation(sid, "one", "alice")["state"] != "finished" and time.monotonic() < deadline:
        time.sleep(.01)
    assert harness.result(sid, "alice")["usage"]["input_tokens"] == 6
    assert harness.run(sid, body, "alice")["state"] == "finished"
    assert sum(url.endswith("/exec") for url, _ in calls) == 1
    events = harness.trace(sid, "alice")["events"]
    assert sum(e["type"] == "result" for e in events) == 1
    assert "answer.txt" not in json.dumps(events) and "write answer" not in json.dumps(events)
    with pytest.raises(Exception) as caught:
        harness.result(sid, "bob")
    assert caught.value.status_code == 404
    client = TestClient(harness.app)
    headers = {"Authorization": "Bearer test-internal-token", "X-Schema-Version": "0", "X-Owner": "alice", "Last-Event-ID": "2"}
    replay = client.get(f"/v0/sessions/{sid}/events", headers=headers)
    assert "id: 1\n" not in replay.text and "id: 3\n" in replay.text


def test_cancel_race_has_one_result(monkeypatch):
    harness.sessions.clear()
    entered, resume = threading.Event(), threading.Event()
    def upstream(url, method="GET", body=None, **kwargs):
        if url.endswith("/decision"):
            entered.set()
            resume.wait(2)
            return {"decision": {"kind": "final", "tool": "none", "args": "{}", "text": "late"}, "usage": {}}
        return {"state": "released"}
    monkeypatch.setattr(harness, "remote", upstream)
    sid = harness.provision({"files": {}}, "owner")["session_id"]
    harness.run(sid, {"request_id": "race", "prompt": "wait"}, "owner")
    assert entered.wait(1)
    harness.cancel(sid, "owner")
    resume.set()
    time.sleep(.05)
    assert harness.result(sid, "owner")["outcome"] == "cancelled"
    assert sum(e["type"] == "result" for e in harness.trace(sid, "owner")["events"]) == 1


def test_real_provider_rejects_synthetic_replay(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "http")
    with pytest.raises(Exception) as caught:
        llm_proxy.infer({"messages": [], "replay": []})
    assert caught.value.status_code == 400


def test_decision_args_must_be_object():
    with pytest.raises(ValueError):
        decision({"kind": "tool", "tool": "exec", "args": "[]", "text": ""})


def test_exec_completion_cannot_win_after_cancel_requested():
    s = {"cancelled": True, "events": [], "result": None}
    op = {"request_id": "race", "state": "running"}
    harness.finish(s, op, {"outcome": "failed", "error": {"type": "sandbox", "message": "container removed"}})
    assert op["state"] == "running"
    harness.finish(s, op, {"outcome": "cancelled", "error": {"type": "cancelled", "message": "removed"}})
    assert op["result"]["outcome"] == "cancelled"
    assert len(s["events"]) == 1


def test_provision_retry_recovers_reserved_identity_after_lost_response(monkeypatch):
    monkeypatch.setattr(harness, "sessions", {})
    monkeypatch.setattr(harness, "provisions", {})
    containers, calls = {}, []
    def upstream(url, method, body):
        sid = body["session_id"]
        assert harness.provisions[("owner", "seed")] == sid
        assert sid in harness.sessions
        containers.setdefault(sid, body["files"])
        calls.append(body)
        if len(calls) == 1:
            raise HTTPException(502, "successful manager response lost")
        return {"session_id": sid}
    monkeypatch.setattr(harness, "remote", upstream)
    body = {"request_id": "seed", "files": {"input": "aGVsbG8="}}
    with pytest.raises(HTTPException):
        harness.provision(body, "owner")
    sid = next(iter(containers))
    assert not harness.sessions[sid]["provisioned"]
    assert harness.provision(body, "owner")["session_id"] == sid
    assert harness.provision(body, "owner")["session_id"] == sid
    assert len(calls) == 2 and calls[0] == calls[1]
    assert list(containers) == list(harness.sessions) == [sid]
    assert harness.sessions[sid]["provisioned"]
    with pytest.raises(HTTPException) as caught:
        harness.provision({**body, "files": {}}, "owner")
    assert caught.value.status_code == 409 and len(calls) == 2


def test_sse_drains_terminal_event_when_finish_occurs_during_yield(monkeypatch):
    op = {"request_id": "one", "state": "running"}
    s = {"owner": "owner", "events": [], "operations": {"one": op}, "cancelled": False, "result": None}
    monkeypatch.setattr(harness, "sessions", {"session": s})
    harness.emit(s, "started", {"request_id": "one"})
    response = harness.events("session", after=0, last_event_id="", x_owner="owner")
    async def consume():
        chunks = [await anext(response.body_iterator)]
        # The stream has copied its pending events and is paused while sending one.
        harness.finish(s, op, {"outcome": "completed"})
        chunks.extend([chunk async for chunk in response.body_iterator])
        return "".join(chunks)
    output = asyncio.run(consume())
    assert "event: started" in output
    assert "event: result" in output and "id: 2\n" in output
