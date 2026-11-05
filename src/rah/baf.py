"""B1–B5 runner; hidden checkers/replays never enter a real model conversation."""
import argparse
import base64
import json
import os
from pathlib import Path
import time
import uuid

import yaml
from rah.baf_checks import check
from rah.client import Client, seed


def tasks(root):
    result = []
    for path in Path(root).glob("tasks/*/task.yaml"):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        result.append((spec, path.parent))
    return sorted(result, key=lambda pair: pair[0]["id"])


def run_one(client, task, directory, repeat, replay=False, evidence=None):
    sid, files, outcome, result, reason, passed = None, {}, "error", {}, "run did not complete", False
    started = time.monotonic()
    try:
        # Only the fixture directory crosses the trust boundary.
        sid = client.provision(seed(directory / "fixture"))
        script = json.loads((directory / "replay.json").read_text(encoding="utf-8")) if replay else None
        op = client.send(sid, task["prompt"], request_id="baf-" + uuid.uuid4().hex, replay=script)
        result = client.wait(sid, op["request_id"], timeout=450)
        outcome = result["outcome"]
        files = client.collect(sid)
        passed, reason = check(directory, files)
        if outcome != "completed":
            passed = False
            reason = "non-completed outcome: " + outcome + "; " + reason
        if evidence:
            target = Path(evidence) / f"{task['id']}-{repeat}-{sid}"
            target.mkdir(parents=True, exist_ok=True)
            trace = client.request("GET", f"/v0/sessions/{sid}/trace")
            (target / "trace.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
            (target / "artifacts.json").write_text(json.dumps({k: base64.b64encode(v).decode() for k, v in files.items()}, indent=2), encoding="utf-8")
    except Exception as exc:
        reason = f"{type(exc).__name__}: {str(exc)[:240]}"
    finally:
        if sid:
            try:
                client.release(sid)
            except Exception:
                passed, reason = False, reason + "; release failed"
    return {"version": "0", "task": task["id"], "repeat": repeat, "pass": passed, "reason": reason,
            "usage": result.get("usage", {}), "seconds": round(time.monotonic() - started, 3), "outcome": outcome,
            "provider": result.get("provider", "unknown"), "model": result.get("model", "unknown"),
            "synthetic": bool(replay or result.get("synthetic")), "session_id": sid}


def main():
    parser = argparse.ArgumentParser(description="B1–B5 runner (replay is synthetic infrastructure evidence)")
    parser.add_argument("--server", default=os.environ.get("RAH_SERVER", "http://localhost:8080"))
    parser.add_argument("--token", default=os.environ.get("RAH_CLIENT_TOKEN", ""))
    parser.add_argument("--root", type=Path, default=Path("baf"))
    parser.add_argument("--tasks", default="all", help="all, smoke (simple B1–B5), or comma-separated IDs")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("results/baf.jsonl"))
    parser.add_argument("--evidence", type=Path, default=Path("results/evidence"))
    args = parser.parse_args()
    selected = tasks(args.root)
    if args.tasks == "smoke":
        selected = [item for item in selected if item[0]["id"].endswith(".1")]
    elif args.tasks != "all":
        selected = [item for item in selected if item[0]["id"] in args.tasks.split(",")]
    if not selected or args.repeat < 1:
        parser.error("select at least one task and positive repeat")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    client = Client(args.server, args.token)
    failed = 0
    try:
        with args.output.open("a", encoding="utf-8") as log:
            for repeat in range(1, args.repeat + 1):
                for spec, directory in selected:
                    record = run_one(client, spec, directory, repeat, args.replay, args.evidence)
                    log.write(json.dumps(record, ensure_ascii=True) + "\n")
                    log.flush()
                    print(json.dumps(record, ensure_ascii=True), flush=True)
                    failed += not record["pass"]
    finally:
        client.close()
    raise SystemExit(bool(failed))


if __name__ == "__main__":
    main()
