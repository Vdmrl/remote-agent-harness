# 0003: HTTP/JSON, SSE and explicit operation IDs

Status: accepted, 2026-11-05.

Use HTTP/JSON for client/gateway/harness and harness/manager operations, with `X-Schema-Version: 0`, explicit request IDs and machine-readable schemas. SSE carries sanitized events with monotonic cursors, so reconnect does not execute another command. Clients poll operation status after an ambiguous transport failure. Exec is never blindly retried.

Each run has exactly one result event and one terminal operation result; command/tool failures are observations while timeout, infrastructure failure and cancellation terminate the run. Reusing an ID with different arguments returns conflict. Client session ownership derives from its authenticated token; internal calls use a separate service credential. Health is public, but connect and all operations require authentication. TLS terminates outside the stack for remote use.

State and idempotency history live in memory. Restart invalidates sessions; manager startup cleans labeled containers. This limits recovery and throughput but keeps checkpoint behavior explicit. Durable journals, per-user quotas and retention are later work. File contents and prompts are omitted from traces; owning clients receive artifacts and final text separately.
