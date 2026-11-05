# 0001: Own the Python agent loop

Status: accepted, 2026-11-05.

The course requires understanding the execution environment and agent loop. We own a short explicit messages/decision/tool/observation loop rather than delegate task execution to a general-purpose agent SDK or Codex CLI. The model returns structured data, and the harness validates and executes it through the sandbox manager. This keeps tracing, cancellation, tool outcomes and BAF evaluation under project control.

Mock/replay and OpenAI-compatible HTTP providers share the same loop. The optional local Codex adapter only produces next decisions; built-in execution features are disabled and unexpected tool events are rejected. This reuses the user's existing ChatGPT login without pretending an API key exists. The selected Luna model remains development evidence pending course qualification.

The consequence is ownership of context, limits, errors and transport behavior. The initial loop has forty decisions and bounded in-memory history; durable recovery and advanced context compaction are deferred.
