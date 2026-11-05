"""Shared desktop and CLI HTTP client. File upload is fixture seeding, not mounting."""
import argparse
import base64
import json
import os
from pathlib import Path
import time
import uuid

import httpx
from rah.common import MAX_BODY, MAX_BYTES, MAX_FILES, path_ok


def seed(folder):
    files, total = {}, 0
    root = Path(folder).resolve()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("fixture input rejects symlinks")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("fixture input accepts regular files only")
        with path.open("rb") as source:
            data = source.read(65537)
        total += len(data)
        if len(data) > 65536 or total > MAX_BYTES or len(files) >= MAX_FILES:
            raise ValueError("fixture exceeds file/count/total limits")
        files[path.relative_to(root).as_posix()] = base64.b64encode(data).decode()
    return files


class Client:
    def __init__(self, server, token, transport=None):
        self.http = httpx.Client(base_url=server.rstrip("/"), headers={"Authorization": "Bearer " + token, "X-Schema-Version": "0"}, timeout=140, transport=transport)

    def close(self):
        self.http.close()

    def request(self, method, path, body=None):
        with self.http.stream(method, path, json=body) as response:
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > MAX_BODY:
                    raise ValueError("server response too large")
            response.raise_for_status()
            return json.loads(raw)

    def connect(self):
        return self.request("GET", "/health")

    def provision(self, files=None, request_id=None):
        return self.request("POST", "/v0/sessions", {"files": files or {}, "request_id": request_id or uuid.uuid4().hex})["session_id"]

    def send(self, sid, prompt, request_id=None, replay=None):
        body = {"request_id": request_id or uuid.uuid4().hex, "prompt": prompt}
        if replay is not None:
            body["replay"] = replay
        return self.request("POST", f"/v0/sessions/{sid}/runs", body)

    def wait(self, sid, rid, timeout=450):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.request("GET", f"/v0/sessions/{sid}/operations/{rid}")
            if result["state"] == "finished":
                return result["result"]
            time.sleep(.2)
        raise TimeoutError("run still active; query status or cancel")

    def events(self, sid, after=0):
        with self.http.stream("GET", f"/v0/sessions/{sid}/events", params={"after": after}) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if len(line) > 65536:
                    raise ValueError("event too large")
                if line.startswith("data: "):
                    yield json.loads(line[6:])

    def collect(self, sid):
        envelope = self.request("POST", f"/v0/sessions/{sid}/collect", {"request_id": "collect-" + uuid.uuid4().hex})
        result = envelope.get("result", {})
        if "error" in result:
            raise ValueError("collection failed: " + str(result["error"]))
        files = result["files"]
        if not isinstance(files, dict) or len(files) > MAX_FILES:
            raise ValueError("invalid collection")
        total = 0
        decoded = {}
        for name, value in files.items():
            path_ok(name)
            data = base64.b64decode(value, validate=True)
            total += len(data)
            if len(data) > 65536 or total > MAX_BYTES:
                raise ValueError("collection too large")
            decoded[name] = data
        return decoded

    def download(self, sid, folder):
        files = self.collect(sid)
        root = Path(folder).resolve()
        root.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            target = root / name
            if not target.resolve().is_relative_to(root) or target.is_symlink():
                raise ValueError("download path escapes destination")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return len(files)

    def cancel(self, sid):
        return self.request("POST", f"/v0/sessions/{sid}/cancel", {})

    def release(self, sid):
        return self.request("POST", f"/v0/sessions/{sid}/release", {})


def main():
    parser = argparse.ArgumentParser(description="Remote harness client; --token can be supplied through RAH_CLIENT_TOKEN")
    parser.add_argument("--server", default=os.environ.get("RAH_SERVER", "http://localhost:8080"))
    parser.add_argument("--token", default=os.environ.get("RAH_CLIENT_TOKEN", ""))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("connect")
    sub.add_parser("gui")
    new = sub.add_parser("provision")
    new.add_argument("--fixture")
    send = sub.add_parser("send")
    send.add_argument("session")
    send.add_argument("prompt")
    send.add_argument("--request-id")
    send.add_argument("--wait", action="store_true")
    for name in ("events", "result", "trace", "cancel", "release", "download", "status"):
        item = sub.add_parser(name)
        item.add_argument("session")
        if name == "events":
            item.add_argument("--after", type=int, default=0)
        if name == "download":
            item.add_argument("folder")
        if name == "status":
            item.add_argument("request_id")
    args = parser.parse_args()
    if args.command == "gui":
        from rah.gui import launch
        launch(args.server, args.token)
        return
    client = Client(args.server, args.token)
    try:
        if args.command == "connect":
            # Auth is tested by provisioning separately; health intentionally has no credentials.
            result = client.connect()
        elif args.command == "provision":
            result = {"session_id": client.provision(seed(args.fixture) if args.fixture else {})}
        elif args.command == "send":
            result = client.send(args.session, args.prompt, args.request_id)
            if args.wait:
                result = client.wait(args.session, result["request_id"])
        elif args.command == "events":
            for event in client.events(args.session, args.after):
                print(json.dumps(event, ensure_ascii=True))
            return
        elif args.command == "download":
            result = {"files": client.download(args.session, args.folder)}
        elif args.command in {"cancel", "release"}:
            result = getattr(client, args.command)(args.session)
        else:
            suffix = "operations/" + args.request_id if args.command == "status" else args.command
            result = client.request("GET", f"/v0/sessions/{args.session}/{suffix}")
        print(json.dumps(result, ensure_ascii=True))
    finally:
        client.close()


if __name__ == "__main__":
    main()
