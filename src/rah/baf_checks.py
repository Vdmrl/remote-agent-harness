"""Trusted host-side artifact checks. Never execute collected code on the host."""
import ast
import base64
import json
from pathlib import Path

from jsonschema import validate
import yaml


def check(task_dir, files):
    try:
        spec = json.loads((Path(task_dir) / "expected.json").read_text(encoding="utf-8"))
        expected = {name: base64.b64decode(value) for name, value in spec["outputs"].items()}
        kind = spec["kind"]
        for name, data in expected.items():
            if name not in files:
                return False, f"missing {name}"
            actual = files[name]
            if kind == "json":
                validate(json.loads(actual), spec["schema"])
            elif kind == "yaml":
                value = yaml.safe_load(actual)
                if value != yaml.safe_load(data) or any(not isinstance(x, str) for x in value.values()):
                    return False, f"YAML string values changed in {name}"
            elif kind == "set":
                if set(actual.decode().strip().splitlines()) != set(data.decode().strip().splitlines()):
                    return False, f"wrong set in {name}"
            elif kind == "answer":
                if actual.decode().strip() != data.decode().strip():
                    return False, f"wrong answer in {name}"
            elif kind == "build":
                text = actual.decode().lower()
                if not text.startswith("no") or "dependency missing" not in text:
                    return False, "must report no and actual stderr reason"
            elif actual != data:
                return False, f"bytes differ in {name}"
            if kind == "rename" and name.endswith(".py"):
                ast.parse(actual)
                if "calc_total" in actual.decode():
                    return False, "old Python symbol remains"
        if spec.get("preserve_fixture"):
            original = Path(task_dir) / "fixture"
            for source in original.rglob("*"):
                if source.is_file():
                    name = source.relative_to(original).as_posix()
                    if name not in expected and files.get(name) != source.read_bytes():
                        return False, f"unrelated file changed: {name}"
        return True, "ok"
    except Exception as exc:
        return False, f"checker rejected artifacts: {type(exc).__name__}"
