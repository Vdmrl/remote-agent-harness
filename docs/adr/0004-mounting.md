# 0004: Compare remote folder mounting

Status: proposed; no mounting implemented in checkpoint one, 2026-11-05.

Checkpoint fixtures are copied into a container-local tmpfs and collected before release. This provides no live synchronization with a client folder. A real cross-machine mount needs a two-machine demonstration, consistency policy and cancellation behavior that protects the client's files.

| Candidate | Benefit | Cost / uncertainty |
|---|---|---|
| SSHFS/SFTP | mature authenticated transport, ordinary server filesystem | FUSE/platform setup, latency and cache semantics |
| WebDAV | broad client support and HTTP infrastructure | filesystem semantics, locking and metadata behavior vary |
| custom RPC-backed filesystem | explicit tool-level authorization and observability | most implementation/consistency work |
| sync/upload-download | straightforward offline fixture path | not a mount and cannot satisfy live folder semantics |

Prototype SSHFS/SFTP and a narrow RPC option against the same rename, symlink, concurrent edit, disconnect and cancellation tests. Record read/write latency and durability before accepting a choice. Neither a host bind mount nor checkpoint fixture upload proves cross-machine mounting.
