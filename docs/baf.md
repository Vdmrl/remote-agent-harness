# B1–B5 evaluation

`baf/catalog.yaml` is the preserved course catalog. Checkpoint materializations are in `baf/tasks/B1.1` through `B5.3`, each containing a public prompt, `fixture/`, hidden `expected.json`, standalone `check.py`, and synthetic `replay.json`. `baf/materialize.py` reproduces them. The original imported B1.1 example remains available.

The runner reads only fixture files into provision, sends only the prompt to real inference, waits for the terminal operation, collects before release, then invokes the host-side checker. No expected answer, checker, replay or task metadata is sent to a real provider. The sandbox image contains only tool worker code. All artifacts are untrusted data; checkers do not execute collected Python or shell on the host.

| Group | Simple | Medium | Trap |
|---|---|---|---|
| B1 reading | configured port, decoy old port | payment deadline in 15-section contract | missing penalty value |
| B2 search | function definition | twelve environment reads among 200 files | timezone-aware implementation among namesakes |
| B3 create | hidden JSON schema | sorted CSV | YAML boolean-like codes and leading zero strings |
| B4 edit | one installation line | symbol rename with exact expected Python source and AST validation | cp1251 with CRLF preserved byte-for-byte |
| B5 tools | actual statistics script | three failures among twenty unittest cases | stdout OK but exit 1 and stderr failure |

B4.2 uses exact source/AST comparisons and unrelated-file preservation, not arbitrary collected-code execution. B5 replay executes the fixture scripts in Docker before writing synthetic expected outputs; offline smoke uses an in-memory protocol fake and executes no commands. Replay solutions are infrastructure tests and must never be presented as model capability results.

```bash
uv run rah-baf --tasks smoke --replay --output results/replay-smoke.jsonl
uv run rah-baf --tasks all --replay --output results/replay-all.jsonl
uv run rah-baf --tasks B4.3,B5.3 --output results/real-traps.jsonl
uv run rah-baf --tasks all --repeat 3 --output results/real-all.jsonl
```

Set `RAH_CLIENT_TOKEN` and optional `RAH_SERVER` first. Use the default-mock stack for replay; select an actual provider for quality measurement. Each task gets a fresh session. JSONL records include task, repeat, pass, reason, usage, seconds, outcome, provider, actual configured/reported model, synthetic flag and session ID. `--evidence results/evidence` saves sanitized traces and base64 artifact mappings. These directories are ignored because artifacts may contain user data. Output is appended, preserving failed runs. A checker or cleanup failure makes the run fail; no successful-looking result replaces a failure.

Model eligibility is separate from successful access or infrastructure correctness. The user-selected gpt-6-luna provides development evidence; course qualification and a compliant comparison pair remain to be established. No B6–B8, composite task, custom BAF or filesystem mounting benchmark is claimed for checkpoint one.
