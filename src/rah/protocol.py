"""Model decisions are data; the Python harness owns all execution."""
import json
from jsonschema import validate

DECISION_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["kind", "tool", "args", "text"],
    "properties": {"kind": {"enum": ["tool", "final"]}, "tool": {"enum": ["list", "read", "write", "exec", "none"]}, "args": {"type": "string"}, "text": {"type": "string"}},
}
SYSTEM = """You are a remote coding agent. Decide only the NEXT tool call or final answer.
All task files live in /work inside an isolated Linux Python container. You cannot use any other tools.
Return a JSON object with kind (tool or final), tool (list/read/write/exec/none), args (a JSON-encoded object), text (final response, otherwise empty).
Tools: list {} lists files; read {path,encoding?} reads a file; write {path,content,encoding?} writes a file; exec {command} runs /bin/sh in /work.
Use relative paths below /work. encodings include utf-8, cp1251, base64 (binary safe).
Inspect fixture files and command exit_code and stderr. Finish only when the requested output files exist.
Do not claim execution; request a tool and wait for its result. No network. No tools run on the host.
"""


def decision(value):
    validate(value, DECISION_SCHEMA)
    args = json.loads(value["args"])
    if not isinstance(args, dict):
        raise ValueError("tool args must be a JSON object")
    if value["kind"] == "tool" and value["tool"] == "none":
        raise ValueError("tool decision requires a tool")
    if len(value["args"]) > 90000 or len(value["text"]) > 20000:
        raise ValueError("decision too large")
    return args
