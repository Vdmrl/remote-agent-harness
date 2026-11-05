import base64
import json
import httpx
import pytest
from rah.client import Client, seed


def test_client_full_http_flow(tmp_path):
    seen = []
    def respond(request):
        seen.append(request)
        assert request.headers["X-Schema-Version"] == "0"
        assert request.headers["Authorization"] == "Bearer secret"
        path = request.url.path
        if path == "/v0/sessions":
            return httpx.Response(200, json={"session_id": "s"})
        if path.endswith("/runs"):
            return httpx.Response(200, json={"request_id": "run"})
        if path.endswith("/events"):
            return httpx.Response(200, text='id: 2\nevent: result\ndata: {"id":2,"type":"result"}\n\n')
        if path.endswith("/collect"):
            return httpx.Response(200, json={"result": {"files": {"sub/a": base64.b64encode(b"bytes\x00").decode()}}})
        return httpx.Response(200, json={"state": "released"})
    client = Client("http://server", "secret", httpx.MockTransport(respond))
    assert client.provision() == "s"
    assert client.send("s", "task")["request_id"] == "run"
    assert list(client.events("s", 1)) == [{"id": 2, "type": "result"}]
    assert client.download("s", tmp_path) == 1
    assert (tmp_path / "sub/a").read_bytes() == b"bytes\x00"
    client.cancel("s")
    client.release("s")
    assert len(seen) == 6


def test_client_rejects_collected_escape(tmp_path):
    client = Client("http://server", "secret", httpx.MockTransport(lambda request: httpx.Response(200, json={"result": {"files": {"../escape": ""}}})))
    with pytest.raises(ValueError):
        client.download("s", tmp_path)


def test_fixture_seed_binary_and_limits(tmp_path):
    (tmp_path / "binary").write_bytes(b"\x00\xff")
    assert base64.b64decode(seed(tmp_path)["binary"]) == b"\x00\xff"
    (tmp_path / "large").write_bytes(b"x" * 65537)
    with pytest.raises(ValueError):
        seed(tmp_path)


def test_connect_requires_authenticated_handshake():
    def respond(request):
        assert request.url.path == "/v0/connect"
        return httpx.Response(401, json={"error": {"type": "auth"}})
    client = Client("http://server", "wrong", httpx.MockTransport(respond))
    with pytest.raises(httpx.HTTPStatusError):
        client.connect()
