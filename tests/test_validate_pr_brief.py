from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
Direct dependencies:
- none
Downstream consumers:
- Fleet pull requests.

## Risk hypotheses

### Hypothesis 1
Hypothesis: HTML comments could be mistaken for an answer.
Exercise: Run the validator against an HTML-comment-only section.
Expected: The section is rejected as empty.
Pre-push result: pass: the focused unit test rejects the body.

### Hypothesis 2
Hypothesis: An adjacent reusable workflow could retain stale validation.
Exercise: Check both generated workflow copies.
Expected: Both copies match the source validator.
Pre-push result: pass: the embed check reports no drift.

## Validation path

Setup:
- Python 3.
Exercise:
1. Run the unit tests.
Inputs or state:
- In-memory PR bodies.
Edge case:
- HTML-comment-only content.
Expected:
- Empty templates fail and completed briefs pass.
Forbidden effects:
- No GitHub writes during validation.

## Evidence

- Risk closure: both hypotheses passed focused tests.
- Final gate command: python3 -m unittest discover -s tests
- Runtime artifacts: unittest output.
- Unverified behavior: none.

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
        self.assertIn("missing evidence field: Risk closure", errors)

    def test_html_comment_is_not_substantive_content(self) -> None:
        body = VALID_BODY.replace(
            "Reject execution briefs that contain only the template scaffold.",
            "<!-- hidden placeholder -->",
        )
        self.assertIn("empty required section: ## Intent", MODULE.validate(body))

    def test_missing_heading_fails(self) -> None:
        body = VALID_BODY.replace("## Risk hypotheses\n", "")
        self.assertIn(
            "missing required heading: ## Risk hypotheses", MODULE.validate(body)
        )

    def test_duplicate_heading_fails(self) -> None:
        body = VALID_BODY + "\n## Intent\nA second intent.\n"
        self.assertIn("duplicated required heading: ## Intent", MODULE.validate(body))

    def test_heading_inside_fenced_code_block_is_not_a_duplicate(self) -> None:
        body = VALID_BODY.replace(
            "- Runtime artifacts: unittest output.",
            "- Runtime artifacts: unittest output.\n"
            "```\n"
            "## Intent\n"
            "## Evidence\n"
            "```",
        )
        self.assertEqual(MODULE.validate(body), [])

    def test_reordered_headings_fail(self) -> None:
        body = (
            VALID_BODY.replace("## Intent", "## TEMP", 1)
            .replace("## Behavioral contract", "## Intent", 1)
            .replace("## TEMP", "## Behavioral contract", 1)
        )
        self.assertEqual(MODULE.validate(body), ["required headings are out of order"])

    def test_blank_operational_labels_fail(self) -> None:
        body = VALID_BODY.replace(
            "- Config or environment variables: none\n"
            "- Schema or data migration: none\n"
            "- Permissions or secrets: none\n"
            "- Rollout or rollback considerations: callers pin the corrected release.",
            "- Config or environment variables:\n"
            "- Schema or data migration:\n"
            "- Permissions or secrets:\n"
            "- Rollout or rollback considerations:",
        )
        self.assertIn(
            "empty required section: ## Operational changes", MODULE.validate(body)
        )

    def test_risk_hypothesis_requires_all_fields(self) -> None:
        body = VALID_BODY.replace(
            "Exercise: Run the validator against an HTML-comment-only section.\n", ""
        )
        self.assertIn("hypothesis 1 missing field: Exercise", MODULE.validate(body))

    def test_failed_or_pending_risk_result_fails(self) -> None:
        for result in ("fail: reproduced", "pending: not run"):
            with self.subTest(result=result):
                body = VALID_BODY.replace(
                    "pass: the focused unit test rejects the body.", result
                )
                self.assertIn("hypothesis 1 is not closed", MODULE.validate(body))

    def test_one_to_three_hypotheses_are_required(self) -> None:
        one = (
            VALID_BODY.split("### Hypothesis 2", 1)[0]
            + VALID_BODY.split("## Validation path", 1)[1].join(
                ["\n## Validation path", ""]
            )
        ).replace("- Public and private profiles.", "- none", 1)
        self.assertEqual(MODULE.validate(one), [])
        four = VALID_BODY.replace(
            "## Validation path",
            """### Hypothesis 3
Hypothesis: Third.
Exercise: Run third proof.
Expected: Third passes.
Pre-push result: pass: third passed.

### Hypothesis 4
Hypothesis: Fourth.
Exercise: Run fourth proof.
Expected: Fourth passes.
Pre-push result: pass: fourth passed.

## Validation path""",
        )
        self.assertIn(
            "risk hypotheses must contain one to three entries", MODULE.validate(four)
        )

    def test_dependency_reference_requires_full_head(self) -> None:
        body = VALID_BODY.replace("- none", "- njrun1804-cc/Contracts#17 @ deadbeef", 1)
        self.assertIn(
            "invalid direct dependency: njrun1804-cc/Contracts#17 @ deadbeef",
            MODULE.validate(body),
        )

    def test_unavailable_result_requires_documented_boundary(self) -> None:
        body = VALID_BODY.replace(
            "pass: the focused unit test rejects the body.",
            "unavailable: provider mutation",
        )
        self.assertIn(
            "hypothesis 1 unavailable boundary is not documented",
            MODULE.validate(body, agent_ready_text="No runtime boundary."),
        )
        self.assertEqual(
            MODULE.validate(
                body,
                agent_ready_text="Provider mutation is outside pull-request execution.",
            ),
            [],
        )

    def test_unavailable_boundary_rejects_bare_substring_matches(self) -> None:
        body = VALID_BODY.replace(
            "pass: the focused unit test rejects the body.",
            "unavailable: provider mutation",
        )
        self.assertIn(
            "hypothesis 1 unavailable boundary is not documented",
            MODULE.validate(
                body, agent_ready_text="The improvider mutations are unrelated."
            ),
        )

    def test_adjacent_surface_requires_a_second_hypothesis(self) -> None:
        marker = VALID_BODY.index("### Hypothesis 2")
        end = VALID_BODY.index("## Validation path")
        body = VALID_BODY[:marker] + VALID_BODY[end:]
        self.assertIn(
            "an adjacent impact requires a second risk hypothesis",
            MODULE.validate(body),
        )

    def test_docs_only_result_rejects_code_changes(self) -> None:
        body = VALID_BODY.replace(
            "pass: the focused unit test rejects the body.",
            "not applicable: docs-only",
        )
        self.assertIn(
            "hypothesis 1 claims docs-only but code-bearing files changed",
            MODULE.validate(body, changed_files=["src/main.py"]),
        )
        self.assertEqual(
            MODULE.validate(body, changed_files=["docs/guide.md", "README.md"]), []
        )

    def test_docs_only_is_judged_by_suffix_not_directory(self) -> None:
        body = VALID_BODY.replace(
            "pass: the focused unit test rejects the body.",
            "not applicable: docs-only",
        )
        self.assertIn(
            "hypothesis 1 claims docs-only but code-bearing files changed",
            MODULE.validate(body, changed_files=["docs/helper.py"]),
        )
        self.assertEqual(
            MODULE.validate(
                body, changed_files=["notes.txt", "docs/diagram.png", "guide.md"]
            ),
            [],
        )

    def test_body_file_preflight_passes_without_environment_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text(VALID_BODY)
            with mock.patch.dict(os.environ, {"PR_BODY": ""}):
                self.assertEqual(MODULE.main(["--body-file", str(body)]), 0)

    def test_body_file_preflight_fails_before_send(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text("## Intent\n")
            self.assertEqual(MODULE.main(["--body-file", str(body)]), 2)

    def test_environment_agent_ready_contract_supports_ci(self) -> None:
        body_text = VALID_BODY.replace(
            "pass: the focused unit test rejects the body.",
            "unavailable: provider mutation",
        )
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text(body_text)
            contract = Path(directory) / "agent-ready.md"
            contract.write_text("Provider mutation is outside CI.")
            with mock.patch.dict(
                os.environ, {"AGENT_READY_FILE": str(contract)}, clear=False
            ):
                self.assertEqual(MODULE.main(["--body-file", str(body)]), 0)

    def test_environment_changed_files_close_docs_only_ci_bypass(self) -> None:
        body_text = VALID_BODY.replace(
            "pass: the focused unit test rejects the body.",
            "not applicable: docs-only",
        )
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text(body_text)
            with mock.patch.dict(
                os.environ,
                {"PR_CHANGED_FILES_JSON": '["src/main.py"]'},
                clear=False,
            ):
                self.assertEqual(MODULE.main(["--body-file", str(body)]), 2)

    def test_environment_changed_files_must_be_string_array(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text(VALID_BODY)
            with mock.patch.dict(
                os.environ,
                {"PR_CHANGED_FILES_JSON": '{"src/main.py": true}'},
                clear=False,
            ):
                self.assertEqual(MODULE.main(["--body-file", str(body)]), 2)

    def test_workflows_include_previous_paths_for_rename_classification(self) -> None:
        for path in (
            ROOT / ".github" / "workflows" / "repo-check.yml",
            ROOT / ".github" / "workflows" / "private-repo-check.yml",
        ):
            workflow = path.read_text(encoding="utf-8")
            self.assertIn(".previous_filename // empty", workflow)

    def test_ci_revalidates_body_edits_and_ready_transitions(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "types: [opened, synchronize, reopened, edited, ready_for_review]",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
