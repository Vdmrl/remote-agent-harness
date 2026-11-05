# HTTP/JSON and SSE v0

All non-health requests require `Authorization: Bearer TOKEN` and `X-Schema-Version: 0`.
Only the gateway is exposed. Each client token owns its sessions; internal services use a distinct service token.
See `v0.schema.json` for versioned envelopes and the generated service `/openapi.json` for route models (authenticated).

Client API: `POST /v0/sessions` with `{files: {relative/path: base64}, request_id: optional-id}`; `POST /v0/sessions/{sid}/runs` with `{request_id,prompt,replay?}`;
`GET .../operations/{request_id}`; `GET .../events?after=cursor` (or Last-Event-ID); `GET .../result`; `GET .../trace`;
`POST .../collect` with `{request_id}`; `POST .../cancel`; `POST .../release`.

Manager API: `POST /v0/sessions` with `{session_id,files}`; `POST .../exec` with `{request_id,tool,args,timeout}`;
`GET .../operations/{request_id}`; `POST .../collect` with `{request_id}`; `POST .../cancel|release`.
Tools: list; read `{path,encoding: utf-8|cp1251|base64}`; write `{path,content,encoding}`; exec `{command}`.
Paths are relative to /work; fixture input accepts files only, no archives or symlinks.
Limits: 512 files, 64 KiB/file, 2 MiB total, 120 seconds/exec, 120000 output bytes.

IDs are idempotent within a live service process. Reusing an ID with different arguments returns 409.
Query status after transport failure; never blindly repeat exec. Services currently store state in memory.
Restart invalidates sessions; manager startup removes this project's labeled orphan containers.
Exactly one result event per run. Events replay after the cursor and omit prompts, tool contents and credentials.
Cancellation removes the entire container and descendants. Its tmpfs artifacts are lost; collect before release.
Typed error classes distinguish command, tool, timeout, sandbox, transport, cancellation and model failures.
HTTP validation/auth errors reject the request before an operation is started.
