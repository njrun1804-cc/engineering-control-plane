#!/usr/bin/env python3
"""Validate an execution brief locally, then update the pull request."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_pr_brief.py"


def update(*, repo: str, pull_request: int, body_file: Path, gh: str = "gh") -> None:
    subprocess.run(
        [sys.executable, str(VALIDATOR), "--body-file", str(body_file)],
        check=True,
    )
    subprocess.run(
        [
            gh,
            "pr",
            "edit",
            str(pull_request),
            "--repo",
            repo,
            "--body-file",
            str(body_file),
        ],
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--body-file", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        update(repo=args.repo, pull_request=args.pr, body_file=args.body_file)
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
