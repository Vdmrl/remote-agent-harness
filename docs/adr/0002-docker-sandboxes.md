# 0002: Disposable Docker tool containers

Status: accepted for trusted development, 2026-11-05.

Only sandbox-manager mounts the Docker socket. It provisions containers with nonroot UID 10001, no network, read-only root, dropped capabilities, no-new-privileges, CPU/RAM/PID limits and bounded /work and /tmp tmpfs. No host directory, model credential or Docker socket enters a task container. Fixture provisioning uses validated files; this is not remote mounting. Tools never fall back to host execution.

Timeout and cancellation forcibly remove the container, terminating its whole process tree; tmpfs artifacts are lost. Successful artifacts must be collected before release. The manager reaps this project's labeled orphan sandboxes on restart and cleans known sessions during graceful shutdown.

Docker socket access is effectively host administrative privilege for the manager. Standard Docker shares the host kernel and is not a hostile multi-tenant security boundary. API/auth bugs or kernel escapes remain risks. Rootless Docker, gVisor or a dedicated VM/host are future hardening options; no claim of complete isolation is made by these baseline checks.
