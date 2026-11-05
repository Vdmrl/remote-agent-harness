import pytest
from jsonschema import ValidationError
from rah.common import validate_payload, wire_schema


def test_contract_entrypoints_reject_invalid_before_effects():
    validate_payload("client-server", "provision", {"files": {}})
    validate_payload("harness-sandbox", "exec", {"request_id": "one", "tool": "exec", "args": {"command": "true"}})
    for name, kind, body in [
        ("client-server", "provision", {"files": [], "secret": "value"}),
        ("client-server", "run", {"request_id": "one", "prompt": ""}),
        ("harness-sandbox", "provision", {"session_id": "../host", "files": {}}),
        ("harness-sandbox", "exec", {"request_id": "one", "tool": "host-shell"}),
        ("harness-sandbox", "exec", {"request_id": "one", "tool": "list", "timeout": 121}),
        ("harness-sandbox", "collect", {}),
    ]:
        with pytest.raises(ValidationError):
            validate_payload(name, kind, body)
    for name in ["client-server", "harness-sandbox"]:
        assert wire_schema(name)["$id"].endswith(":0")
