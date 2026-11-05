import json, sys
from pathlib import Path
from rah.baf_checks import check
if __name__ == "__main__":
    root = Path(sys.argv[1])
    files = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file() and not p.is_symlink()}
    passed, reason = check(Path(__file__).parent, files)
    print(json.dumps({"pass": passed, "reason": reason}))
