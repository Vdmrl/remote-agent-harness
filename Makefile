.PHONY: up down test-ci test-ui test-infra test-docker baf-smoke baf
up:
	docker compose up --build -d --wait
down:
	docker compose down -v --remove-orphans
test-ci:
	uv sync --locked
	uv run pytest -m "not docker"
test-ui:
	uv run pytest tests/ui
test-infra:
	uv run pytest tests/infra -m "not docker"
test-docker:
	uv run pytest -m docker
baf-smoke:
	uv run rah-baf --tasks smoke --replay --output results/replay-smoke.jsonl
baf:
	uv run rah-baf --tasks all --repeat 3 --output results/baf.jsonl
