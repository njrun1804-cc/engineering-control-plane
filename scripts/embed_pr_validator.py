#!/usr/bin/env python3
"""Keep the caller-independent PR validator embedded in both reusable workflows."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "validate_pr_brief.py"
WORKFLOWS = (
    ROOT / ".github" / "workflows" / "repo-check.yml",
    ROOT / ".github" / "workflows" / "private-repo-check.yml",
)
BEGIN = "# BEGIN GENERATED PR BRIEF VALIDATOR"
END = "# END GENERATED PR BRIEF VALIDATOR"


def _replacement(indent: str) -> str:
    source = SOURCE.read_text(encoding="utf-8").rstrip("\n")
    lines = [BEGIN, "python3 - <<'PY'", *source.splitlines(), "PY", END]
    return "\n".join(f"{indent}{line}" if line else "" for line in lines)


def render(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if line.strip() == BEGIN]
    ends = [index for index, line in enumerate(lines) if line.strip() == END]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ValueError(f"{path}: expected one ordered generated validator block")
    indent = lines[starts[0]][: -len(lines[starts[0]].lstrip())]
    replacement = _replacement(indent).splitlines()
    return "\n".join(lines[: starts[0]] + replacement + lines[ends[0] + 1 :]) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    stale = []
    for path in WORKFLOWS:
        expected = render(path)
        if expected == path.read_text(encoding="utf-8"):
            continue
        stale.append(path)
        if args.write:
            path.write_text(expected, encoding="utf-8")
    if stale and not args.write:
        for path in stale:
            print(f"stale embedded PR validator: {path.relative_to(ROOT)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
