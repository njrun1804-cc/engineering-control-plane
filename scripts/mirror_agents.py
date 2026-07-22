"""Generate AGENTS.md deterministically from CLAUDE.md."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANNER = (
    "<!-- GENERATED from CLAUDE.md by scripts/mirror_agents.py — edit CLAUDE.md, "
    "never this file. -->\n"
)


def render() -> str:
    source = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    return BANNER + source.replace("CLAUDE.md", "AGENTS.md").replace("Claude", "Codex")


def main(argv: list[str] | None = None) -> int:
    check = "--check" in (sys.argv[1:] if argv is None else argv)
    rendered = render()
    destination = ROOT / "AGENTS.md"
    if check:
        if not destination.exists() or destination.read_text(encoding="utf-8") != rendered:
            print("AGENTS.md is stale; run scripts/mirror_agents.py", file=sys.stderr)
            return 1
    else:
        destination.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
