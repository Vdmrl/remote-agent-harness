# Remote Agent Harness

A Python agent loop with a desktop/CLI client and disposable Docker tool sandboxes, implementing checkpoint one of course track A. The harness owns model messages, next-tool decisions, execution, observations and terminal results. Task commands execute exclusively inside containers.

`client → gateway → harness → llm-proxy → model` and `harness → sandbox-manager → Docker sandbox`.
Only the manager sees the Docker socket. Only the gateway publishes a port. See [ADRs](docs/adr/README.md) and [contracts](contracts/README.md).

On Linux, install Docker Engine with Compose v2, Python 3.12+, uv 0.11.13, and optionally python3-tk for the desktop client:

```bash
cp .env.example .env
# Set distinct random RAH_TOKEN and CLIENT_TOKENS values in .env.
docker compose up --build -d --wait
uv sync --locked
set -a; . ./.env; set +a
export RAH_CLIENT_TOKEN="${CLIENT_TOKENS%%,*}"
uv run rah connect
uv run rah gui
```

The default provider is offline mock; no API key is required. Services have real HTTP healthchecks and pinned image/dependency versions. Authentication is mandatory for operations. The default port binds localhost; use a trusted tunnel or terminate TLS before exposing it to another machine.

CLI demonstration (replace SESSION with the ID returned by provision):

```bash
uv run rah provision --fixture baf/tasks/B1.1/fixture
uv run rah send SESSION "Find the service port and write only its number to answer.txt" --wait
uv run rah events SESSION --after 0
uv run rah trace SESSION
uv run rah download SESSION ./artifacts
uv run rah release SESSION
```

The mock lists files and finishes; use synthetic replay or a real provider to solve the task. The GUI supports authenticated connection, fixture upload, sending, event display, cancellation and artifact download. File upload seeds bounded temporary `/work` storage. It does **not** mount a local folder. Cancellation destroys the container and its descendants; temporary artifacts may be lost. Download before release.

```bash
make test-ci                         # offline; no Docker/model/network
make test-docker                     # opt-in; running default-mock stack required
uv run rah-baf --replay --tasks all --output results/replay.jsonl
uv run rah-baf --tasks all --repeat 3 --output results/real.jsonl
```

The runner covers fifteen B1–B5 tasks with clean fixtures, hidden checkers, JSONL outcomes and sanitized trace metadata. Replay is explicitly synthetic infrastructure evidence. It does not measure model quality. [BAF details](docs/baf.md), [verification report](docs/report.md).

For an OpenAI-compatible provider, set `LLM_PROVIDER=http`, `LLM_PROVIDER_URL` to the full chat-completions endpoint, `LLM_API_KEY` and `LLM_MODEL` in `.env`, then recreate llm-proxy. Credentials remain in llm-proxy; no sandbox receives them. For existing local Codex ChatGPT access, follow the [optional Luna bridge setup](docs/harness.md#optional-local-codex-bridge). Luna is the chosen development model; course eligibility is not established by these runs.

```bash
docker compose down -v --remove-orphans
```

Compose shutdown calls manager cleanup. Manager startup reaps only this project's labeled orphan sandboxes after an interrupted shutdown. Service state is in memory: restart invalidates sessions and idempotency history. Cross-machine mounting, durable session recovery, network allowlists and stronger tenant isolation remain later work.

The imported layout and upstream revision are recorded in [template-source.md](docs/template-source.md). [Checkpoint status](docs/checkpoint-1.md) and [course roadmap](docs/project-plan.md) distinguish implemented behavior from remaining work.
