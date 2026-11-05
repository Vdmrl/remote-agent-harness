# Harness

`src/rah/harness.py` owns messages, next model decisions, Docker tool calls, observations, events and exactly one terminal result per run. It calls only llm-proxy for inference and sandbox-manager for tools. No host commands execute here. State/idempotency history is in memory; see docs/harness.md. Built from the root Dockerfile `runtime` target.
