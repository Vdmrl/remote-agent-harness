# Gateway

`src/rah/gateway.py` authenticates client tokens, derives session ownership, and forwards HTTP/SSE to the harness. It is the only published service. Client-supplied ownership headers are replaced. `/health` is public; `/v0/connect` and all operations require authentication. Built from the root Dockerfile `runtime` target.
