import json
import pytest
from rah.codex_bridge import DISABLED, parse_events


def test_bridge_structured_usage_and_tool_rejection():
    answer = {"kind": "tool", "tool": "list", "args": "{}", "text": ""}
    stream = "\n\n".join(map(json.dumps, [{"type": "item.completed", "item": {"type": "agent_message", "text": "I am checking the supplied conversation."}}, {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(answer)}}, {"type": "turn.completed", "usage": {"input_tokens": 12}}]))
    assert parse_events(stream, "gpt-6-luna")["usage"] == {"input_tokens": 12}
    with pytest.raises(ValueError):
        parse_events(json.dumps({"type": "item.started", "item": {"type": "command_execution", "command": "ls"}}), "gpt-6-luna")
    assert {"shell_tool", "apps", "plugins", "multi_agent"}.issubset(DISABLED)


def test_final_unused_empty_args_are_normalized():
    final = {"kind": "final", "tool": "none", "args": "", "text": "LUNA_BRIDGE_OK"}
    event = {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(final)}}
    assert parse_events(json.dumps(event), "gpt-6-luna")["decision"]["args"] == "{}"
