# Infrastructure checks

`uv run pytest -m 'not docker'` is offline and covers version/auth boundaries, schemas, file validation, binary encodings, idempotency, event replay, cancellation races, bridge event parsing and all fifteen synthetic BAF checker cases.

`uv run pytest -m docker` explicitly selects live tests against an already running default-mock Compose stack. Set RAH_CLIENT_TOKEN and optionally RAH_SERVER first. It checks actual container settings, path/symlink errors, nonzero exit, binary collect, deduplication, timeout and child-process cancellation/removal. Docker Desktop tests use its Linux Engine pipe on Windows; Linux uses /var/run/docker.sock.
