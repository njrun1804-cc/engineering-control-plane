from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_pr_brief", ROOT / "scripts" / "validate_pr_brief.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


VALID_BODY = """\
## Intent

Reject execution briefs that contain only the template scaffold.

## Behavioral contract

Before: Empty headings passed.
After: Every section contains a concrete answer.
Must remain unchanged: Dependabot remains exempt.

## Impact surface

Primary:
- Reusable PR validation.
Adjacent:
- Public and private profiles.

## Risk hypotheses

- HTML comments could be mistaken for an answer.

## Validation path

Setup:
- Python 3.
Exercise:
1. Run the unit tests.
Expected:
- Empty templates fail and completed briefs pass.

## Evidence

- Tests added or updated: validator unit tests.
- Commands run: python3 -m unittest discover -s tests
- Existing validation intentionally not run: none.
- Screenshots or traces: none.

## Operational changes

- Config or environment variables: none
- Schema or data migration: none
- Permissions or secrets: none
- Rollout or rollback considerations: callers pin the corrected release.
"""


class ValidatePullRequestBriefTests(unittest.TestCase):
    def test_completed_execution_brief_passes(self) -> None:
        self.assertEqual(MODULE.validate(VALID_BODY), [])

    def test_unedited_template_fails_empty_sections(self) -> None:
        template = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text()
        errors = MODULE.validate(template)
        self.assertIn("empty required section: ## Intent", errors)
        self.assertIn("empty required section: ## Evidence", errors)

    def test_html_comment_is_not_substantive_content(self) -> None:
        body = VALID_BODY.replace(
            "Reject execution briefs that contain only the template scaffold.",
            "<!-- hidden placeholder -->",
        )
        self.assertIn("empty required section: ## Intent", MODULE.validate(body))

    def test_missing_heading_fails(self) -> None:
        body = VALID_BODY.replace("## Risk hypotheses\n", "")
        self.assertIn("missing required heading: ## Risk hypotheses", MODULE.validate(body))

    def test_duplicate_heading_fails(self) -> None:
        body = VALID_BODY + "\n## Intent\nA second intent.\n"
        self.assertIn("duplicated required heading: ## Intent", MODULE.validate(body))

    def test_reordered_headings_fail(self) -> None:
        body = VALID_BODY.replace("## Intent", "## TEMP", 1).replace(
            "## Behavioral contract", "## Intent", 1
        ).replace("## TEMP", "## Behavioral contract", 1)
        self.assertEqual(MODULE.validate(body), ["required headings are out of order"])


if __name__ == "__main__":
    unittest.main()
