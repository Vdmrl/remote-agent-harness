# Sandbox manager

`src/rah/sandbox.py` is the only component with Docker socket access. It validates fixture input, creates isolated nonroot sessions, executes `rah.worker` inside them, bounds time/output, collects artifacts and forcibly removes containers on cancel/release. Startup reaps this project's labeled orphans. `/health` checks Docker and the pinned sandbox image. The root Dockerfile builds `runtime` and the minimal `sandbox` target in the same Compose command. Manager socket access is a trusted host-administration boundary, documented in ADR 0002.
