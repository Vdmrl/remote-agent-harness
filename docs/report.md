# Checkpoint-one verification report

Development environment: Windows host, Docker Desktop Linux Engine (`desktop-linux`), Python 3.13.13 locally and pinned Python 3.12.12 in containers. Date: 2026-11-05. Linux-clone instructions are provided; the development run is not a fresh external Linux-clone demonstration.

Executed verification:

| Check | Observed result |
|---|---|
| `uv sync --locked` | passed |
| `uv run pytest -q` | 19 passed, 3 opt-in Docker cases deselected |
| independent committed clone, Linux Python 3.12 container | revision `9a83c3a3a217a5b71c3f21bcb54cb0a7739d946b`: 18 passed, 3 Docker deselected; tests/fixtures mounted read-only |
| `docker --context desktop-linux compose config --quiet` | passed |
| `docker --context desktop-linux compose up --build -d --wait` | all four long-running services healthy; sandbox-image build job exited successfully |
| `uv run pytest -m docker -q` | 3 passed: isolation/tools/idempotency, cancel with descendants, timeout removal |
| live client handshake | correct token connected; wrong token 401; unsupported schema version 400 |
| `uv run rah-baf --replay --tasks all --output results/replay-final.jsonl` | 15/15 passed; provider mock, model offline-replay, synthetic true; sum of task durations 83.658 seconds |
| graceful `docker compose down -v --remove-orphans` | removed an active session sandbox; zero project-labeled containers remained |
| configured-secret scan | no configured internal/client/bridge tokens in tracked files or 29 saved trace metadata files |
| committed binary fixture | B4.3 Git blob equals working file, cp1251 and three CRLF lines preserved; `.gitattributes` disables fixture conversion |
| local Codex bridge HTTP structured greeting | parent workflow verified actual gpt-6-luna inference, synthetic:false and returned usage |
| native Tk launch | one window titled Remote Agent Harness appeared; no session created; screenshot capture unavailable |

The offline suite exercises auth/version rejection, explicit operation schema validation, traversal and symlink rejection, binary/cp1251 data, operation deduplication, session ownership, event cursor replay, exactly-one-result cancellation races, structured bridge parsing, protected client connect, artifact download safety and all fifteen B1–B5 synthetic checker cases including negative mutations. It runs no model calls and no task commands on the host. FastAPI lifecycle and upstream Starlette compatibility emit deprecation warnings; no check failure is hidden by them.

Initial boot attempts exposed and corrected a Compose tmpfs quoting error and Docker archive upload rejection on a read-only rootfs; bounded nonroot worker seeding now handles fixtures. Docker acceptance exposed an exec/cancel completion race; terminal-result arbitration and a regression check address it. One earlier replay attempt passed 14/15 but hit a five-second Docker create response timeout under load; a created orphan was reaped on restart. The manager now allows a bounded 30-second daemon call and cleans ambiguous creates by name, with an added regression test. That failed history remains in `results/replay-all.jsonl`; the final run uses a distinct output file.

Final replay runtime/runner revision: `a69161e`; the subsequent `5311fe5` commit only tightens flags for the external Codex bridge. `results/replay-final.metadata.json` records both revisions, command, provider/synthetic status and totals. Per-task sanitized traces and base64 artifacts are in ignored `results/evidence/`. These are local artifacts; no failed result was replaced. Passing replay proves infrastructure behavior only. Real bridge probes exposed and corrected unused empty final arguments. Actual quality results are appended separately after real BAF execution; no unexecuted check is counted as passed.

Real quality results are pending the parent workflow's BAF runs. The configured development model is gpt-6-luna through existing Codex access. Its successful login and inference do not establish course eligibility. The parent checked Artificial Analysis v5.0.1 and reported Luna Max 28 ([model page](https://artificialanalysis.ai/models/gpt-6-luna)); course-compliant comparison remains separate work. No model switch or invented score is used to make a passing claim.

Limitations: no real folder mount, no persistent sessions or restart recovery, trusted development Docker socket manager, no hostile-tenant isolation claim, no TLS inside the stack, and no manual desktop interaction/visual acceptance recorded yet. Native launch succeeded, but screenshot capture timed out; automated coverage is the shared HTTP client. The manager limits and file constraints are baseline safeguards. Cancellation destroys tmpfs artifacts. Run collection before release. Wider B6–B8/custom/composite and filesystem performance work is outside checkpoint one.
