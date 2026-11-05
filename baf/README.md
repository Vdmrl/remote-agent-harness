# Course BAF tasks

`catalog.yaml` remains the imported course catalog. Checkpoint one materializes B1–B5 in `tasks/`: fifteen fixture/prompt/hidden-checker cases. The original B1-read example remains preserved. `materialize.py` regenerates the checkpoint cases.

Run `uv run rah-baf --tasks all --replay` against the default-mock stack for synthetic infrastructure evidence, or omit --replay with a real provider for quality evidence. Real providers never receive replays/checkers/expected outputs. See docs/baf.md for protocols, limits, outcomes and artifact evidence.
