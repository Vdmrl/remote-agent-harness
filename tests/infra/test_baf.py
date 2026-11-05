import base64
import json
from pathlib import Path

from rah.baf import run_one, tasks
from rah.baf_checks import check


class ReplayClient:
    """Synthetic protocol smoke; executes no commands on the host."""
    def __init__(self):
        self.files = {}
        self.released = False
    def provision(self, files):
        self.files = {k: base64.b64decode(v) for k, v in files.items()}
        return "synthetic-session"
    def send(self, sid, prompt, request_id, replay):
        assert replay is not None
        for step in replay:
            if step["tool"] == "write":
                args = json.loads(step["args"])
                self.files[args["path"]] = base64.b64decode(args["content"])
        return {"request_id": request_id}
    def wait(self, *args, **kwargs):
        return {"outcome": "completed", "model": "offline-replay", "provider": "mock", "synthetic": True, "usage": {}}
    def collect(self, sid):
        return self.files
    def release(self, sid):
        self.released = True


def test_fifteen_synthetic_runner_cases_and_checker_failures():
    cases = tasks(Path("baf"))
    assert len(cases) == 15
    for spec, directory in cases:
        client = ReplayClient()
        record = run_one(client, spec, directory, 1, replay=True)
        assert record["pass"], (spec["id"], record)
        assert record["synthetic"] and client.released
        expected = json.loads((directory / "expected.json").read_text())
        name = next(iter(expected["outputs"]))
        client.files[name] = b"WRONG"
        assert not check(directory, client.files)[0], spec["id"]


def test_no_hidden_checker_or_replay_in_seed():
    for spec, directory in tasks("baf"):
        assert not (directory / "fixture/replay.json").exists()
        assert not (directory / "fixture/check.py").exists()


def test_rename_accepts_formatting_and_rejects_changed_logic():
    directory = Path("baf/tasks/B4.2")
    expected = json.loads((directory / "expected.json").read_text())
    fixture = directory / "fixture"
    files = {path.relative_to(fixture).as_posix(): path.read_bytes() for path in fixture.rglob("*") if path.is_file()}
    files.update({name: base64.b64decode(value) for name, value in expected["outputs"].items()})
    files["app.py"] = b"# Renamed call\n\n" + files["app.py"]
    assert check(directory, files)[0]
    files["app.py"] = files["app.py"].replace(b"[1, 2, 3]", b"[1, 2]")
    assert not check(directory, files)[0]


def test_failed_collection_preserves_terminal_trace(tmp_path):
    class TimedOutClient(ReplayClient):
        def wait(self, *args, **kwargs):
            return {"outcome": "failed", "error": {"type": "timeout"}}

        def collect(self, sid):
            raise RuntimeError("sandbox removed")

        def request(self, method, path):
            assert method == "GET" and path.endswith("/trace")
            return {"events": [{"type": "result", "data": {"error_type": "timeout"}}]}

    client = TimedOutClient()
    spec, directory = tasks("baf")[0]
    record = run_one(client, spec, directory, 1, replay=True, evidence=tmp_path)
    trace_path = tmp_path / f"{spec['id']}-1-synthetic-session" / "trace.json"
    assert json.loads(trace_path.read_text())["events"][0]["data"]["error_type"] == "timeout"
    assert not record["pass"] and record["error_type"] == "timeout"
    assert "sandbox removed" in record["reason"] and client.released
