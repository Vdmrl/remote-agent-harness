"""Optional trusted local Codex inference adapter. Never exports Codex credentials."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from fastapi import HTTPException
import uvicorn

from rah.common import MAX_BODY, app_for, error
from rah.protocol import DECISION_SCHEMA, decision

DISABLED = ["shell_tool", "apps", "plugins", "multi_agent", "browser_use", "browser_use_external", "computer_use", "image_generation", "view_image", "skill_search"]


def parse_events(output, model):
    final, usage = None, {}
    for line in output.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        item = event.get("item", {})
        if item and item.get("type") not in {"agent_message", "reasoning"}:
            raise ValueError("Codex attempted a built-in tool or unknown item")
        if event.get("type") in {"error", "turn.failed"}:
            raise ValueError("Codex inference failed")
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            # CLI may emit plain-text progress before its schema-constrained final message.
            final = item["text"]
        if event.get("type") == "turn.completed":
            usage = event.get("usage", {})
    if final is None:
        raise ValueError("Codex returned no structured decision")
    final = json.loads(final)
    decision(final)
    return {"decision": final, "model": model, "provider": "codex-bridge", "usage": usage, "synthetic": False}


def infer(messages):
    model = os.environ.get("CODEX_MODEL", "gpt-6-luna")
    executable = shutil.which(os.environ.get("CODEX_BIN", "codex"))
    if executable is None:
        raise ValueError("Codex CLI is not installed")
    # Only this empty directory is the cwd; no project, task fixture, checker, or auth copy.
    with tempfile.TemporaryDirectory(prefix="rah-inference-") as temporary:
        root = Path(temporary)
        cwd = root / "empty"
        cwd.mkdir()
        schema = root / "schema.json"
        schema.write_text(json.dumps(DECISION_SCHEMA), encoding="utf-8")
        command = [executable, "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only", "-m", model, "--json", "--output-schema", str(schema)]
        for feature in DISABLED:
            command.extend(["--disable", feature])
        command.extend(["-c", "web_search=disabled"])
        command.append("-")
        prompt = ("You are an inference-only adapter. Return only the next structured decision based on the supplied conversation. "
                  "Never inspect your cwd or execute the task. Never use built-in tools, apps, plugins, shell, network, subagents, or skills. "
                  "A tool decision is data for the separate Python harness to execute in Docker. Conversation:\n" + json.dumps(messages, ensure_ascii=True))
        if len(prompt.encode()) > MAX_BODY:
            raise ValueError("conversation too large")
        with (root / "input").open("wb") as source:
            source.write(prompt.encode())
        with (root / "input").open("rb") as source, (root / "events").open("wb") as output, (root / "errors").open("wb") as errors:
            process = subprocess.Popen(command, cwd=cwd, stdin=source, stdout=output, stderr=errors,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            deadline = time.monotonic() + 110
            while process.poll() is None:
                if time.monotonic() > deadline or (root / "events").stat().st_size + (root / "errors").stat().st_size > MAX_BODY:
                    process.kill()
                    process.wait(timeout=5)
                    raise ValueError("Codex inference exceeded time/output limit")
                time.sleep(.1)
            if process.returncode:
                raise ValueError("Codex inference failed (check local login and model access)")
        if (root / "events").stat().st_size + (root / "errors").stat().st_size > MAX_BODY:
            raise ValueError("Codex inference output limit exceeded")
        return parse_events((root / "events").read_text(encoding="utf-8"), model)


def create_app():
    app = app_for("codex-bridge")
    @app.post("/v0/decision")
    def endpoint(body: dict):
        if not isinstance(body.get("messages"), list) or "replay" in body:
            raise ValueError("only messages are accepted")
        try:
            return infer(body["messages"])
        except Exception as exc:
            raise HTTPException(502, error("model", str(exc)[:200])) from exc
    return app


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Trusted local inference only; ChatGPT Codex login remains local")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    args = parser.parse_args()
    token = os.environ.get("BRIDGE_TOKEN", "")
    if len(token) < 24:
        parser.error("set BRIDGE_TOKEN to a random token of at least 24 characters")
    os.environ["RAH_TOKEN"] = token
    uvicorn.run(create_app(), host=args.host, port=args.port, access_log=False)


if __name__ == "__main__":
    main()
