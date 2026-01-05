import os
import sys

import python_minifier


def should_skip(path: str) -> bool:
    parts = path.split(os.sep)
    if "__pycache__" in parts:
        return True
    if "wheels" in parts:
        return True
    return False


def minify_file(path: str) -> None:
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    out = python_minifier.minify(src)
    if out != src:
        with open(path, "w", encoding="utf-8") as f:
            f.write(out)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: minify-python.py <root>")
        return 2
    root = sys.argv[1]
    for dirpath, dirnames, filenames in os.walk(root):
        if should_skip(dirpath):
            continue
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            if should_skip(path):
                continue
            minify_file(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
