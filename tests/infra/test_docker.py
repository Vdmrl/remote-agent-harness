"""Opt-in against an already running default-mock Compose stack."""
import base64
import json
import os
import time
import uuid

import docker
import httpx
import pytest

from rah.client import Client

pytestmark = pytest.mark.docker


def tool(name, args):
    return {"kind": "tool", "tool": name, "args": json.dumps(args), "text": ""}


def final():
    return {"kind": "final", "tool": "none", "args": "{}", "text": "done"}


@pytest.fixture
def client():
    token = os.environ["RAH_CLIENT_TOKEN"]
    value = Client(os.environ.get("RAH_SERVER", "http://localhost:8080"), token)
    yield value
    value.close()


def engine():
    return docker.DockerClient(base_url="npipe:////./pipe/dockerDesktopLinuxEngine" if os.name == "nt" else "unix:///var/run/docker.sock", timeout=10)


def test_real_tools_typed_errors_isolation_and_release(client):
    sid = client.provision({"binary": base64.b64encode(b"\x00\xff").decode()})
    try:
        script = [tool("exec", {"command": "id -u; cat /proc/self/status | grep CapEff; test ! -e /var/run/docker.sock; test -z \"$RAH_TOKEN$LLM_API_KEY\""}),
                  tool("read", {"path": "../etc/passwd"}), tool("exec", {"command": "ln -s /etc outside"}),
                  tool("read", {"path": "outside/passwd"}), tool("exec", {"command": "rm outside; echo failure >&2; exit 7"}),
                  tool("write", {"path": "answer.txt", "content": "42"}), final()]
        op = client.send(sid, "synthetic Docker isolation check", "isolation", script)
        assert client.wait(sid, op["request_id"])["outcome"] == "completed"
        repeated = client.send(sid, "synthetic Docker isolation check", "isolation", script)
        assert repeated["state"] == "finished"
        trace = client.request("GET", f"/v0/sessions/{sid}/trace")["events"]
        assert sum(event["type"] == "result" for event in trace) == 1
        tools = [event["data"] for event in trace if event["type"] == "tool"]
        assert [event["error_type"] for event in tools].count("tool") == 2
        assert any(event["exit_code"] == 7 and event["error_type"] == "command" for event in tools)
        files = client.collect(sid)
        assert files["binary"] == b"\x00\xff" and files["answer.txt"] == b"42"
        info = engine().containers.get("rah-" + sid).attrs
        host = info["HostConfig"]
        assert info["Config"]["User"] == "10001:10001"
        assert host["NetworkMode"] == "none" and host["ReadonlyRootfs"]
        assert host["CapDrop"] == ["ALL"] and host["PidsLimit"] == 64
        assert host["Memory"] == 256 * 1024 * 1024
        assert not host.get("Binds")
        assert not any(value.startswith(("RAH_TOKEN=", "LLM_API_KEY=")) for value in info["Config"]["Env"])
    finally:
        client.release(sid)
    with pytest.raises(docker.errors.NotFound):
        engine().containers.get("rah-" + sid)


def test_cancel_removes_child_processes_and_one_result(client):
    sid = client.provision()
    script = [tool("exec", {"command": "sleep 100 & wait"}), final()]
    op = client.send(sid, "synthetic cancellation check", "cancel", script)
    time.sleep(1)
    container = engine().containers.get("rah-" + sid)
    assert len(container.top()["Processes"]) >= 2
    client.cancel(sid)
    assert client.wait(sid, op["request_id"])["outcome"] == "cancelled"
    with pytest.raises(docker.errors.NotFound):
        engine().containers.get("rah-" + sid)
    trace = client.request("GET", f"/v0/sessions/{sid}/trace")["events"]
    assert sum(event["type"] == "result" for event in trace) == 1
    client.release(sid)


def test_timeout_removes_container(client):
    sid = client.provision()
    try:
        op = client.send(sid, "synthetic timeout check", "timeout", [tool("exec", {"command": "sleep 100 & wait"}), final()])
        result = client.wait(sid, op["request_id"], timeout=40)
        assert result["error"]["type"] == "timeout"
        with pytest.raises(docker.errors.NotFound):
            engine().containers.get("rah-" + sid)
    finally:
        client.release(sid)
