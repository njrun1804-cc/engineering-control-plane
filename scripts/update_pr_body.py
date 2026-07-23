#!/usr/bin/env python3
"""Validate an execution brief in memory, then update the pull request with those exact bytes."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_pr_brief.py"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_pr_brief", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load validator: {VALIDATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate = _load_validator().validate


class BriefValidationError(ValueError):
    """The body failed the deterministic execution-brief contract."""


def update(*, repo: str, pull_request: int, body_file: Path, gh: str = "gh") -> None:
    body = body_file.read_text(encoding="utf-8")
    errors = validate(body)
    if errors:
        raise BriefValidationError("\n".join(errors))
    subprocess.run(
        [
            gh,
            "pr",
            "edit",
            str(pull_request),
            "--repo",
            repo,
            "--body",
            body,
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
    except BriefValidationError as exc:
        print(exc)
        return 2
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
