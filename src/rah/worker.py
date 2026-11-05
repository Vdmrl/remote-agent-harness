"""Container-only tools. Never invoke this module on the server or client host."""
import base64
import json
import os
from pathlib import Path, PurePosixPath
import stat
import selectors
import signal
import subprocess
import sys

ROOT = Path("/work")
FILE_LIMIT = 64 * 1024
TOTAL_LIMIT = 2 * 1024 * 1024


def safe_path(name):
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise ValueError("invalid path")
    rel = PurePosixPath(name)
    if rel.is_absolute() or ".." in rel.parts or name == "." or len(name) > 240:
        raise ValueError("path must be below /work")
    path = ROOT / name
    if not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("symlink escapes /work")
    return path


def regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > FILE_LIMIT:
        raise ValueError("only bounded regular files are supported")
    return path.read_bytes()


def perform(tool, args):
    if tool == "list":
        entries = []
        for path in ROOT.rglob("*"):
            if len(entries) >= 512:
                raise ValueError("too many files")
            entries.append({"path": str(path.relative_to(ROOT)), "type": "symlink" if path.is_symlink() else "directory" if path.is_dir() else "file"})
        return {"files": entries}
    if tool == "read":
        data = regular(safe_path(args["path"]))
        encoding = args.get("encoding", "utf-8")
        return {"content": base64.b64encode(data).decode() if encoding == "base64" else data.decode(encoding), "encoding": encoding}
    if tool == "write":
        path = safe_path(args["path"])
        encoding = args.get("encoding", "utf-8")
        data = base64.b64decode(args["content"], validate=True) if encoding == "base64" else args["content"].encode(encoding)
        if len(data) > FILE_LIMIT:
            raise ValueError("file too large")
        path.parent.mkdir(parents=True, exist_ok=True)
        # O_NOFOLLOW also prevents replacing the final component through a symlink.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
        return {"bytes": len(data)}
    if tool == "exec":
        command = args["command"]
        if not isinstance(command, str) or len(command) > 8192:
            raise ValueError("invalid command")
        process = subprocess.Popen(["/bin/sh", "-c", command], cwd=ROOT, env={"PATH": os.environ["PATH"], "HOME": "/tmp", "LANG": "C.UTF-8"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        output = {"stdout": bytearray(), "stderr": bytearray()}
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                for key, _ in selector.select(timeout=0.2):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    output[key.data].extend(chunk)
                    if sum(map(len, output.values())) > 120000:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        return {"error": {"type": "output_limit", "message": "command output exceeds 120000 bytes"}}
        code = process.wait()
        return {"exit_code": code, **{k: v.decode("utf-8", "replace") for k, v in output.items()}, "error": None if code == 0 else {"type": "command", "message": "nonzero exit status"}}
    if tool == "collect":
        files, size = {}, 0
        for path in ROOT.rglob("*"):
            if path.is_symlink():
                raise ValueError("collect rejects symlinks")
            if path.is_dir():
                continue
            data = regular(path)
            size += len(data)
            if size > TOTAL_LIMIT or len(files) >= 512:
                raise ValueError("collection too large")
            files[str(path.relative_to(ROOT))] = base64.b64encode(data).decode()
        return {"files": files}
    raise ValueError("unknown tool")


def main():
    try:
        request = json.loads(base64.b64decode(sys.argv[1], validate=True))
        result = perform(request["tool"], request.get("args", {}))
    except (ValueError, OSError, KeyError, LookupError, TypeError) as exc:
        result = {"error": {"type": "tool", "message": str(exc)[:300]}}
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
