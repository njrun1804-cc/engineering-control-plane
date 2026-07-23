#!/usr/bin/env python3
"""Fail closed when a pull request execution brief is missing or empty."""

from __future__ import annotations

import os
import re
import sys


REQUIRED_HEADINGS = (
    "## Intent",
    "## Behavioral contract",
    "## Impact surface",
    "## Risk hypotheses",
    "## Validation path",
    "## Evidence",
    "## Operational changes",
)

SCAFFOLD_LINES = {
    "## Behavioral contract": {"Before:", "After:", "Must remain unchanged:"},
    "## Impact surface": {"Primary:", "Adjacent:"},
    "## Validation path": {"Setup:", "Exercise:", "Expected:"},
    "## Evidence": {
        "- Tests added or updated:",
        "- Commands run:",
        "- Existing validation intentionally not run:",
        "- Screenshots or traces:",
    },
}

PLACEHOLDER_LINES = {"-", "*", "+", "1.", "1)"}


def _visible_body(body: str) -> str:
    return re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)


def _sections(body: str) -> tuple[dict[str, list[str]], list[str]]:
    visible = _visible_body(body)
    lines = visible.splitlines()
    positions: dict[str, int] = {}
    errors: list[str] = []

    for heading in REQUIRED_HEADINGS:
        matches = [index for index, line in enumerate(lines) if line.strip() == heading]
        if len(matches) != 1:
            qualifier = "missing" if not matches else "duplicated"
            errors.append(f"{qualifier} required heading: {heading}")
        else:
            positions[heading] = matches[0]

    if errors:
        return {}, errors

    observed_order = sorted(REQUIRED_HEADINGS, key=positions.__getitem__)
    if tuple(observed_order) != REQUIRED_HEADINGS:
        return {}, ["required headings are out of order"]

    sections: dict[str, list[str]] = {}
    for heading in REQUIRED_HEADINGS:
        start = positions[heading] + 1
        end = next(
            (index for index in range(start, len(lines)) if lines[index].startswith("## ")),
            len(lines),
        )
        sections[heading] = lines[start:end]
    return sections, []


def validate(body: str) -> list[str]:
    sections, errors = _sections(body)
    if errors:
        return errors

    for heading, lines in sections.items():
        scaffold = SCAFFOLD_LINES.get(heading, set())
        substantive = [
            line.strip()
            for line in lines
            if line.strip()
            and line.strip() not in scaffold
            and line.strip() not in PLACEHOLDER_LINES
        ]
        if not substantive:
            errors.append(f"empty required section: {heading}")
    return errors


def main() -> int:
    errors = validate(os.environ.get("PR_BODY", ""))
    if not errors:
        print("Agent-ready PR execution brief: PASS")
        return 0
    for error in errors:
        print(error, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
