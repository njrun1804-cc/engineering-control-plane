#!/usr/bin/env python3
"""Validate an execution brief locally, then update the pull request."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_pr_brief.py"


def update(*, repo: str, pull_request: int, body_file: Path, gh: str = "gh") -> None:
    body = body_file.read_bytes()
    with tempfile.NamedTemporaryFile(prefix="pr-body-", suffix=".md", delete=False) as handle:
        handle.write(body)
        snapshot = Path(handle.name)
    os.chmod(snapshot, 0o600)
    try:
        subprocess.run(
            [sys.executable, str(VALIDATOR), "--body-file", str(snapshot)],
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
                str(snapshot),
            ],
            check=True,
        )
    finally:
        snapshot.unlink(missing_ok=True)


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
