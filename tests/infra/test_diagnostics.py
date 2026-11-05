import contextlib
import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from rah import codex_bridge, harness, llm_proxy
from rah.common import error


@pytest.mark.parametrize("stream,code", [
    ("not JSON", "bridge_event_json"),
    (json.dumps({"type": "item.completed", "item": {"type": "command_execution"}}), "bridge_builtin_tool"),
    (json.dumps({"type": "turn.failed", "error": {"message": "SECRET"}}), "bridge_turn_failed"),
    (json.dumps({"type": "turn.completed"}), "bridge_no_final"),
    (json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "SECRET"}}), "bridge_final_json"),
    (json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps({"kind": "tool", "tool": "read", "args": "", "text": "SECRET"})}}), "bridge_decision_invalid"),
])
def test_bridge_failure_stages_are_content_free(stream, code):
    with pytest.raises(codex_bridge.InferenceFailure) as caught:
        codex_bridge.parse_events(stream, "gpt-6-luna")
    assert caught.value.code == code
    assert "SECRET" not in str(caught.value)


def test_bridge_unexpected_exception_never_exposes_content(monkeypatch):
    def fail(messages):
        raise RuntimeError("SECRET credential or file content")
    monkeypatch.setattr(codex_bridge, "infer", fail)
    client = TestClient(codex_bridge.create_app())
    response = client.post("/v0/decision", json={"messages": []}, headers={"Authorization": "Bearer test-internal-token", "X-Schema-Version": "0"})
    assert response.status_code == 502
    assert response.json()["detail"]["error"]["code"] == "bridge_internal"
    assert "SECRET" not in response.text


def test_proxy_preserves_allowlisted_stage_and_discards_provider_message(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bridge")
    monkeypatch.setenv("LLM_PROVIDER_URL", "http://bridge/v0/decision")
    @contextlib.contextmanager
    def response(*args, **kwargs):
        yield httpx.Response(502, json={"detail": {"error": {"type": "model", "code": "bridge_decision_invalid", "message": "SECRET"}}})
    monkeypatch.setattr(llm_proxy.httpx, "stream", response)
    with pytest.raises(HTTPException) as caught:
        llm_proxy.infer({"messages": []})
    assert caught.value.detail["error"]["code"] == "bridge_decision_invalid"
    assert "SECRET" not in json.dumps(caught.value.detail)


def test_terminal_trace_only_retains_known_diagnostic_codes():
    for supplied, expected in [("bridge_final_json", "bridge_final_json"), ("SECRET", None), ({"SECRET": "value"}, None)]:
        session = {"cancelled": False, "events": [], "result": None}
        operation = {"state": "running", "request_id": "one"}
        harness.finish(session, operation, {"outcome": "failed", "error": {"type": "model", "code": supplied, "message": "SECRET"}})
        assert session["events"][0]["data"]["error_code"] == expected
        assert "SECRET" not in json.dumps(session["events"])
        assert error("model", "safe", supplied)["error"].get("code") == expected
