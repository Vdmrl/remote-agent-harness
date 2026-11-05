import base64
import io
import tarfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rah import sandbox, worker
from rah.common import path_ok


def test_fixture_archive_only_bounded_relative_regular_files():
    payload = sandbox.fixtures({"nested/binary": base64.b64encode(b"\x00\xff").decode()})
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        member = archive.getmembers()[0]
        assert member.isfile() and member.uid == 10001
        assert archive.extractfile(member).read() == b"\x00\xff"
    for path in ["../escape", "/etc/passwd", "a/../../b", "a\\b", ".", ""]:
        with pytest.raises(ValueError):
            sandbox.fixtures({path: ""})
    with pytest.raises(ValueError):
        sandbox.fixtures({"large": base64.b64encode(b"x" * 65537).decode()})
    with pytest.raises(ValueError):
        sandbox.fixtures({"bad": "%%%"})


def test_binary_tools_and_symlink_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    if not hasattr(worker.os, "O_NOFOLLOW"):
        monkeypatch.setattr(worker.os, "O_NOFOLLOW", 0, raising=False)
    data = "Товар X;990\r\n".encode("cp1251")
    worker.perform("write", {"path": "prices.csv", "content": base64.b64encode(data).decode(), "encoding": "base64"})
    assert worker.perform("read", {"path": "prices.csv", "encoding": "cp1251"})["content"] == "Товар X;990\r\n"
    assert base64.b64decode(worker.perform("collect", {})["files"]["prices.csv"]) == data
    try:
        (tmp_path / "escape").symlink_to(tmp_path.parent, target_is_directory=True)
    except OSError:
        pytest.skip("Windows symlink privilege unavailable; Linux CI exercises symlink validation")
    with pytest.raises(ValueError):
        worker.perform("read", {"path": "escape/secret"})
    with pytest.raises(ValueError):
        worker.perform("collect", {})


def test_auth_version_rejected_before_operation():
    client = TestClient(sandbox.app)
    assert client.post("/v0/sessions", json={}).status_code == 401
    assert client.post("/v0/sessions", json={}, headers={"Authorization": "Bearer test-internal-token", "X-Schema-Version": "99"}).status_code == 400


def test_manager_idempotency_and_error_result(monkeypatch):
    sandbox.sessions.clear()
    sandbox.sessions["s"] = {"operations": {}, "removed": False, "busy": False}
    calls = []
    monkeypatch.setattr(sandbox, "execute", lambda s, b: calls.append(b) or {"exit_code": 1, "error": {"type": "command", "message": "failed"}})
    body = {"request_id": "same", "tool": "exec", "args": {"command": "exit 1"}}
    one = sandbox.exec_tool("s", body)
    assert sandbox.exec_tool("s", body) == one
    assert len(calls) == 1 and one["result"]["error"]["type"] == "command"
    with pytest.raises(Exception) as caught:
        sandbox.exec_tool("s", {**body, "tool": "list"})
    assert caught.value.status_code == 409
