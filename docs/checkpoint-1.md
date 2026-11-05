# Checkpoint one

Implemented: installable pinned Python package; four long-running Compose services plus a sandbox-image build job; own agent loop; Docker tool worker; auth and session ownership; HTTP/JSON/SSE v0; bounded file input/output, binary encodings and tool errors; idempotency/status/cursors; cancellation and container teardown; desktop and CLI clients; optional local Codex inference bridge; fifteen B1–B5 fixtures with hidden checkers and synthetic replay; offline CI and opt-in Docker checks; architecture decisions and runnable documentation.

Default inference is mock. Real development inference uses the user-selected gpt-6-luna via existing authenticated Codex CLI, with all task execution kept in the harness's Docker tools. No API key is invented or exported from Codex. Course model eligibility is not claimed.

Executed checks in [report.md](report.md): nineteen offline checks, three Docker acceptance cases, fifteen synthetic replay tasks, authenticated CLI connection, fixture-byte preservation and graceful active-sandbox teardown. An independent committed checkout passed eighteen earlier offline checks inside Linux/Python 3.12. Actual Luna evaluation results will be appended after implementation. The desktop client's HTTP logic has automated coverage and native launch passed; manual visual interaction remains unverified.

Remaining: real cross-machine mounting (checkpoint two), durable state/recovery and production isolation, course-compliant comparison provider and repeatable real quality measurements. Compose uses a privileged Docker-control manager as a trusted development component. Cancellation can lose temporary artifacts; collect before release.
