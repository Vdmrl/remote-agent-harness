# Desktop and command-line clients

Install with `uv sync --locked`. Set `RAH_CLIENT_TOKEN` and optionally `RAH_SERVER`.
`uv run rah gui` opens the Python Tkinter desktop client (install python3-tk on Linux).
Connect creates an authenticated session. Upload fixture creates a new session with bounded file input.
Send streams event metadata and shows the terminal result; Cancel removes the container; Download collects artifacts.

CLI: `uv run rah provision --fixture ./fixture`, then `uv run rah send SESSION "task" --wait`.
Use `events SESSION --after CURSOR`, `status SESSION REQUEST_ID`, `result SESSION`, `trace SESSION`,
`download SESSION ./artifacts`, `cancel SESSION`, `release SESSION`.
`connect` checks health; provision validates authentication and creates a sandbox.
Token environment variables avoid putting secrets into shell history.
Fixture upload is not mounting a local folder. Real remote mounting is checkpoint two.
