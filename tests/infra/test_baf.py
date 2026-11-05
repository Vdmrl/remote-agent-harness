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
