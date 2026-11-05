import json
import threading
import time

import pytest
from fastapi.testclient import TestClient
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
