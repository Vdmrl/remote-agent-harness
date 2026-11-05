import json
import os
import httpx
from fastapi import HTTPException
from rah.common import DIAGNOSTIC_CODES, MAX_BODY, app_for, error
from rah.protocol import DECISION_SCHEMA, decision

app = app_for("llm-proxy")


@app.post("/v0/decision")
def infer(body: dict):
    provider = os.environ.get("LLM_PROVIDER", "mock")
    model = os.environ.get("LLM_MODEL", "gpt-6-luna")
    if provider == "mock":
        replay = body.get("replay")
        step = body.get("step", 0)
        value = replay[step] if replay and step < len(replay) else {"kind": "tool", "tool": "list", "args": "{}", "text": ""} if step == 0 else {"kind": "final", "tool": "none", "args": "{}", "text": "Mock run complete (synthetic; no quality evidence)."}
        decision(value)
        return {"decision": value, "model": "offline-replay" if replay else "offline-mock", "provider": "mock", "synthetic": True, "usage": {}}
    if body.get("replay") is not None:
        raise HTTPException(400, error("model", "replay is forbidden for real providers"))
    if provider not in {"http", "bridge"}:
        raise ValueError("LLM_PROVIDER must be mock, http, or bridge")
    url = os.environ.get("LLM_PROVIDER_URL", "")
    if not url.startswith(("http://", "https://")):
        raise ValueError("configure LLM_PROVIDER_URL")
    payload = {"messages": body["messages"]} if provider == "bridge" else {
        "model": model, "messages": body["messages"],
        "response_format": {"type": "json_schema", "json_schema": {"name": "next_decision", "strict": True, "schema": DECISION_SCHEMA}},
    }
    auth = {"Authorization": "Bearer " + os.environ.get("LLM_API_KEY", ""), "X-Schema-Version": "0"}
    try:
        with httpx.stream("POST", url, headers=auth, json=payload, timeout=120) as response:
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > MAX_BODY:
                    raise HTTPException(502, error("model", "provider response too large", "provider_response_limit"))
            if response.is_error:
                code = "provider_http_error"
                if provider == "bridge":
                    try:
                        detail = json.loads(data)
                        while isinstance(detail, dict) and "detail" in detail:
                            detail = detail["detail"]
                        supplied = detail.get("error", {}).get("code") if isinstance(detail, dict) else None
                        if isinstance(supplied, str) and supplied in DIAGNOSTIC_CODES:
                            code = supplied
                    except (ValueError, TypeError, AttributeError):
                        pass
                raise HTTPException(502, error("model", "provider inference failed", code))
            result = json.loads(data)
        value = result["decision"] if provider == "bridge" else json.loads(result["choices"][0]["message"]["content"])
        decision(value)
        return {"decision": value, "model": result.get("model", model), "provider": provider, "synthetic": False, "usage": result.get("usage", {})}
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(502, error("model", "provider transport failed", "provider_transport")) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(502, error("model", "provider returned invalid JSON", "provider_response_json")) from exc
    except Exception as exc:
        raise HTTPException(502, error("model", "provider structured decision failed", "provider_decision_invalid")) from exc
