# Client checks

`uv run pytest tests/ui` verifies the shared CLI/desktop HTTP client against mocked HTTP: authentication handshake, provision/send/events, cancel/release, binary artifact download and invalid output paths. Tk desktop visual interaction is a separate manual check; these tests do not claim screenshot coverage.
