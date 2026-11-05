# Checkpoint one

Implemented: installable pinned Python package; four long-running Compose services plus a sandbox-image build job; own agent loop; Docker tool worker; auth and session ownership; HTTP/JSON/SSE v0; bounded file input/output, binary encodings and tool errors; idempotency/status/cursors; cancellation and container teardown; desktop and CLI clients; optional local Codex inference bridge; fifteen B1–B5 fixtures with hidden checkers and synthetic replay; offline CI and opt-in Docker checks; architecture decisions and runnable documentation.

Default inference is mock. Real development inference uses the user-selected gpt-6-luna via existing authenticated Codex CLI, with all task execution kept in the harness's Docker tools. No API key is invented or exported from Codex. Course model eligibility is not claimed.

The [verification report](report.md) records the offline and Docker checks, the authenticated CLI handshake, fixture-byte preservation and shutdown cleanup. The final synthetic replay passed 15/15 and the first real Luna run passed 13/15. The desktop client launched on Windows and its shared HTTP logic has automated coverage. Manual interaction remains unverified.

Remaining: real cross-machine mounting (checkpoint two), durable state/recovery and production isolation, course-compliant comparison provider and repeatable real quality measurements. Compose uses a privileged Docker-control manager as a trusted development component. Cancellation can lose temporary artifacts; collect before release.
