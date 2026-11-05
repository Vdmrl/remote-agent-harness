# Checkpoint-one verification report

Development environment: Windows host, Docker Desktop Linux Engine (`desktop-linux`), Python 3.13.13 locally and pinned Python 3.12.12 in containers. Date: 2026-11-05. Linux-clone instructions are provided; the development run is not a fresh external Linux-clone demonstration.

Executed verification:

| Check | Observed result |
|---|---|
| `uv sync --locked` | passed |
| `uv run --locked pytest -q` | 33 passed, 3 opt-in Docker cases deselected |
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

The final suite includes regressions for a lost provision response, retry after a failed fixture seed, SSE termination during event delivery, equivalent Python formatting in B4.2 and trace capture after artifact collection fails.

Initial boot attempts exposed and corrected a Compose tmpfs quoting error and Docker archive upload rejection on a read-only rootfs; bounded nonroot worker seeding now handles fixtures. Docker acceptance exposed an exec/cancel completion race; terminal-result arbitration and a regression check address it. One earlier replay attempt passed 14/15 but hit a five-second Docker create response timeout under load; a created orphan was reaped on restart. The manager now allows a bounded 30-second daemon call and cleans ambiguous creates by name, with an added regression test. That failed history remains in `results/replay-all.jsonl`; the final run uses a distinct output file.

The final synthetic run passed 15/15. Its metadata records the revisions, command, provider and duration. The initial 14/15 result is also preserved. The runner writes per-task traces and artifacts under `results/` on the machine that executes it. [Final replay](../results/replay-final.jsonl), [metadata](../results/replay-final.metadata.json), [initial replay](../results/replay-all.jsonl).

The first full run with `gpt-6-luna` through the Codex bridge passed **13/15**. B1.2 ended before the first model decision and reported no usage. B4.3 changed the price but replaced one CRLF separator with CR followed by a tab. The checker detected the byte difference. The run took 691.716 seconds across all tasks. [Real run](../results/luna-real.jsonl), [metadata](../results/luna-real.metadata.json).

Both cases passed on a targeted rerun with the same model, runtime and fixtures. The initial full-run score remains 13/15. [Targeted rerun](../results/luna-retest.jsonl).

Luna was used for development as requested. On Artificial Analysis v5.0.1, Luna Max scored 28 and DeepSeek V4.1 Flash 1017 Max scored 33. Model eligibility under the course threshold remains open. [Luna](https://artificialanalysis.ai/models/gpt-6-luna), [DeepSeek Flash](https://artificialanalysis.ai/models/deepseek-v4-1-flash-1017), [course requirements](https://github.com/deeppavlov/agentic-course-itmo/blob/main/projects/README.md#0-1-модели).

Limitations: no real folder mount, no persistent sessions or restart recovery, trusted development Docker socket manager, no hostile-tenant isolation claim, no TLS inside the stack, and no manual desktop interaction/visual acceptance recorded yet. Native launch succeeded, but screenshot capture timed out; automated coverage is the shared HTTP client. The manager limits and file constraints are baseline safeguards. Cancellation destroys tmpfs artifacts. Run collection before release. Wider B6–B8/custom/composite and filesystem performance work is outside checkpoint one.
