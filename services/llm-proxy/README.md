# Model proxy

`src/rah/llm_proxy.py` supports default offline mock/replay, configurable OpenAI-compatible HTTP JSON-schema inference, and an optional external local Codex bridge. Provider credentials are passed only to this service. It returns next decisions as data; it never executes task tools. Real providers reject synthetic replay input. The optional bridge remains outside Compose on the authenticated host. See docs/harness.md for exact setup. Built from the root Dockerfile `runtime` target.
