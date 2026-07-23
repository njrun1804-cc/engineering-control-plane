from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "update_pr_body", ROOT / "scripts" / "update_pr_body.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class UpdatePullRequestBodyTests(unittest.TestCase):
    @mock.patch.object(MODULE, "_gh_json")
    def test_dependency_may_be_open_or_merged_at_the_exact_head(
        self,
        gh_json: mock.Mock,
    ) -> None:
        dependency = {
            "repository": "o/upstream",
            "pull_request": 7,
            "head_sha": "a" * 40,
        }
        for state in ("OPEN", "MERGED"):
            gh_json.return_value = {"state": state, "headRefOid": "a" * 40}
            MODULE._verify_dependencies([dependency])

        gh_json.return_value = {"state": "CLOSED", "headRefOid": "a" * 40}
        with self.assertRaisesRegex(
            MODULE.BriefValidationError, "neither open nor merged"
        ):
            MODULE._verify_dependencies([dependency])
        gh_json.return_value = {"state": "MERGED", "headRefOid": "b" * 40}
        with self.assertRaisesRegex(MODULE.BriefValidationError, "head drifted"):
            MODULE._verify_dependencies([dependency])

    @mock.patch.object(MODULE.subprocess, "run")
    @mock.patch.object(MODULE, "validate", return_value=[])
    def test_validated_body_is_sent_in_memory(
        self, validate: mock.Mock, run: mock.Mock
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text("valid")
            MODULE.update(repo="njrun1804-cc/Zion", pull_request=38, body_file=body)

        validate.assert_called_once_with("valid")
        self.assertEqual(
            run.call_args.args[0],
            [
                "gh",
                "pr",
                "edit",
                "38",
                "--repo",
                "njrun1804-cc/Zion",
                "--body",
                "valid",
            ],
        )

    @mock.patch.object(MODULE.subprocess, "run")
    @mock.patch.object(MODULE, "validate", return_value=["invalid"])
    def test_failed_preflight_prevents_github_edit(
        self, validate: mock.Mock, run: mock.Mock
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text("invalid")
            with self.assertRaises(MODULE.BriefValidationError):
                MODULE.update(repo="njrun1804-cc/Zion", pull_request=38, body_file=body)

        validate.assert_called_once_with("invalid")
        run.assert_not_called()

    @mock.patch.object(MODULE.subprocess, "run")
    def test_original_replacement_cannot_change_sent_bytes(
        self, run: mock.Mock
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text("validated")

            def mutate_original(value: str) -> list[str]:
                body.write_text("replaced after validation")
                return [] if value == "validated" else ["unexpected"]

            with mock.patch.object(MODULE, "validate", side_effect=mutate_original):
                MODULE.update(repo="njrun1804-cc/Zion", pull_request=38, body_file=body)

        self.assertEqual(run.call_args.args[0][-1], "validated")

    @mock.patch.object(MODULE, "_verify_dependencies")
    @mock.patch.object(MODULE, "_git")
    @mock.patch.object(MODULE, "_gh_json")
    @mock.patch.object(MODULE, "_gh")
    @mock.patch.object(MODULE, "parse_dependencies", return_value=[])
    @mock.patch.object(MODULE, "validate", return_value=[])
    def test_push_candidate_verifies_identity_and_emits_receipt(
        self,
        validate: mock.Mock,
        parse_dependencies: mock.Mock,
        gh: mock.Mock,
        gh_json: mock.Mock,
        git: mock.Mock,
        verify_dependencies: mock.Mock,
    ) -> None:
        gh_json.side_effect = [
            {
                "body": "old",
                "headRefName": "codex/change",
                "headRefOid": "a" * 40,
                "isDraft": False,
                "state": "OPEN",
                "url": "https://github.com/o/r/pull/1",
            },
            {
                "body": "valid",
                "headRefName": "codex/change",
                "headRefOid": "b" * 40,
                "isDraft": True,
                "state": "OPEN",
                "url": "https://github.com/o/r/pull/1",
            },
            {
                "body": "valid",
                "headRefName": "codex/change",
                "headRefOid": "b" * 40,
                "isDraft": True,
                "state": "OPEN",
                "url": "https://github.com/o/r/pull/1",
            },
            {
                "body": "valid",
                "headRefName": "codex/change",
                "headRefOid": "b" * 40,
                "isDraft": False,
                "state": "OPEN",
                "url": "https://github.com/o/r/pull/1",
            },
        ]
        git.side_effect = [
            "b" * 40,
            "codex/change",
            "src/main.py",
            None,
            "a" * 40,
            None,
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = root / "body.md"
            body.write_text("valid")
            (root / "docs").mkdir()
            (root / "docs" / "agent-ready.md").write_text("safe")
            receipt = MODULE.update(
                repo="o/r",
                pull_request=1,
                body_file=body,
                candidate_worktree=root,
                push_candidate=True,
            )

        self.assertEqual(receipt["schema_version"], "pr_brief_preflight.v2")
        self.assertEqual(receipt["head_sha"], "b" * 40)
        self.assertEqual(receipt["risk_result_count"], 0)
        self.assertEqual(
            gh.call_args_list[-1].args,
            ("pr", "ready", "1", "--repo", "o/r"),
        )
        self.assertEqual(
            git.call_args_list[-1].args[1:],
            (
                "push",
                "origin",
                "HEAD:refs/heads/codex/change",
            ),
        )

    @mock.patch.object(MODULE, "_verify_dependencies")
    @mock.patch.object(MODULE, "_git")
    @mock.patch.object(MODULE, "_gh_json")
    @mock.patch.object(MODULE, "_gh")
    @mock.patch.object(MODULE, "parse_dependencies", return_value=[])
    @mock.patch.object(MODULE, "validate", return_value=[])
    def test_push_candidate_waits_for_github_head_propagation(
        self,
        validate: mock.Mock,
        parse_dependencies: mock.Mock,
        gh: mock.Mock,
        gh_json: mock.Mock,
        git: mock.Mock,
        verify_dependencies: mock.Mock,
    ) -> None:
        initial = {
            "body": "old",
            "headRefName": "codex/change",
            "headRefOid": "a" * 40,
            "isDraft": False,
            "state": "OPEN",
            "url": "https://github.com/o/r/pull/1",
        }
        propagated = {
            **initial,
            "body": "valid",
            "headRefOid": "b" * 40,
            "isDraft": True,
        }
        gh_json.side_effect = [
            initial,
            {**initial, "body": "valid", "isDraft": True},
            propagated,
            propagated,
            {**propagated, "isDraft": False},
        ]
        git.side_effect = [
            "b" * 40,
            "codex/change",
            "src/main.py",
            None,
            "a" * 40,
            None,
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = root / "body.md"
            body.write_text("valid")
            (root / "docs").mkdir()
            (root / "docs" / "agent-ready.md").write_text("safe")
            with mock.patch.object(MODULE.time, "sleep") as sleep:
                receipt = MODULE.update(
                    repo="o/r",
                    pull_request=1,
                    body_file=body,
                    candidate_worktree=root,
                    push_candidate=True,
                )
        self.assertEqual(receipt["head_sha"], "b" * 40)
        sleep.assert_called_once_with(1)

    @mock.patch.object(MODULE, "_verify_dependencies")
    @mock.patch.object(MODULE, "_git")
    @mock.patch.object(MODULE, "_gh_json")
    @mock.patch.object(MODULE, "_gh")
    @mock.patch.object(MODULE, "parse_dependencies", return_value=[])
    @mock.patch.object(MODULE, "validate", return_value=[])
    def test_push_failure_quarantines_ready_pr_without_overwriting_body(
        self,
        validate: mock.Mock,
        parse_dependencies: mock.Mock,
        gh: mock.Mock,
        gh_json: mock.Mock,
        git: mock.Mock,
        verify_dependencies: mock.Mock,
    ) -> None:
        gh_json.return_value = {
            "body": "old",
            "headRefName": "codex/change",
            "headRefOid": "a" * 40,
            "state": "OPEN",
            "url": "https://github.com/o/r/pull/1",
        }
        git.side_effect = [
            "b" * 40,
            "codex/change",
            "src/main.py",
            None,
            "a" * 40,
            MODULE.CommandError("push failed"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = root / "body.md"
            body.write_text("valid")
            (root / "docs").mkdir()
            (root / "docs" / "agent-ready.md").write_text("safe")
            with self.assertRaises(MODULE.CommandError):
                MODULE.update(
                    repo="o/r",
                    pull_request=1,
                    body_file=body,
                    candidate_worktree=root,
                    push_candidate=True,
                )
        self.assertEqual(
            gh.call_args_list[-1].args,
            ("pr", "ready", "1", "--repo", "o/r", "--undo"),
        )

    @mock.patch.object(MODULE, "_verify_dependencies")
    @mock.patch.object(MODULE, "_git")
    @mock.patch.object(MODULE, "_gh_json")
    @mock.patch.object(MODULE, "_gh")
    @mock.patch.object(MODULE, "parse_dependencies", return_value=[])
    @mock.patch.object(MODULE, "validate", return_value=[])
    def test_remote_head_drift_blocks_body_update(
        self,
        validate: mock.Mock,
        parse_dependencies: mock.Mock,
        gh: mock.Mock,
        gh_json: mock.Mock,
        git: mock.Mock,
        verify_dependencies: mock.Mock,
    ) -> None:
        gh_json.return_value = {
            "body": "old",
            "headRefName": "codex/change",
            "headRefOid": "a" * 40,
            "state": "OPEN",
            "url": "https://github.com/o/r/pull/1",
        }
        git.side_effect = [
            "b" * 40,
            "codex/change",
            "src/main.py",
            None,
            "d" * 40,
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = root / "body.md"
            body.write_text("valid")
            (root / "docs").mkdir()
            (root / "docs" / "agent-ready.md").write_text("safe")
            with self.assertRaises(MODULE.BriefValidationError):
                MODULE.update(
                    repo="o/r",
                    pull_request=1,
                    body_file=body,
                    candidate_worktree=root,
                    push_candidate=True,
                )
        gh.assert_not_called()

    @mock.patch.object(MODULE, "_verify_dependencies")
    @mock.patch.object(MODULE, "_git")
    @mock.patch.object(MODULE, "_gh_json")
    @mock.patch.object(MODULE, "_gh")
    @mock.patch.object(MODULE, "parse_dependencies", return_value=[])
    @mock.patch.object(MODULE, "validate", return_value=[])
    def test_unpushed_candidate_blocks_body_update_without_push_flag(
        self,
        validate: mock.Mock,
        parse_dependencies: mock.Mock,
        gh: mock.Mock,
        gh_json: mock.Mock,
        git: mock.Mock,
        verify_dependencies: mock.Mock,
    ) -> None:
        gh_json.return_value = {
            "body": "old",
            "headRefName": "codex/change",
            "headRefOid": "a" * 40,
            "state": "OPEN",
            "url": "https://github.com/o/r/pull/1",
        }
        git.side_effect = [
            "b" * 40,
            "codex/change",
            "src/main.py",
            None,
            "a" * 40,
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = root / "body.md"
            body.write_text("valid")
            (root / "docs").mkdir()
            (root / "docs" / "agent-ready.md").write_text("safe")
            with self.assertRaisesRegex(
                MODULE.BriefValidationError, "use --push-candidate"
            ):
                MODULE.update(
                    repo="o/r",
                    pull_request=1,
                    body_file=body,
                    candidate_worktree=root,
                )
        gh.assert_not_called()

    @mock.patch.object(MODULE.time, "sleep")
    @mock.patch.object(MODULE, "_verify_dependencies")
    @mock.patch.object(MODULE, "_git")
    @mock.patch.object(MODULE, "_gh_json")
    @mock.patch.object(MODULE, "_gh")
    @mock.patch.object(MODULE, "parse_dependencies", return_value=[])
    @mock.patch.object(MODULE, "validate", return_value=[])
    def test_post_push_head_divergence_quarantines_without_overwriting_body(
        self,
        validate: mock.Mock,
        parse_dependencies: mock.Mock,
        gh: mock.Mock,
        gh_json: mock.Mock,
        git: mock.Mock,
        verify_dependencies: mock.Mock,
        sleep: mock.Mock,
    ) -> None:
        initial = {
            "body": "old",
            "headRefName": "codex/change",
            "headRefOid": "a" * 40,
            "state": "OPEN",
            "url": "https://github.com/o/r/pull/1",
        }
        divergent = {
            **initial,
            "body": "valid",
            "headRefOid": "c" * 40,
        }
        gh_json.side_effect = [initial, *([divergent] * 6)]
        git.side_effect = [
            "b" * 40,
            "codex/change",
            "src/main.py",
            None,
            "a" * 40,
            None,
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = root / "body.md"
            body.write_text("valid")
            (root / "docs").mkdir()
            (root / "docs" / "agent-ready.md").write_text("safe")
            with self.assertRaisesRegex(MODULE.CommandError, "pushed candidate"):
                MODULE.update(
                    repo="o/r",
                    pull_request=1,
                    body_file=body,
                    candidate_worktree=root,
                    push_candidate=True,
                )
        self.assertEqual(
            gh.call_args_list[-1].args,
            ("pr", "ready", "1", "--repo", "o/r", "--undo"),
        )
        self.assertEqual(sleep.call_count, 5)

    def test_main_prints_json_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text("valid")
            receipt = {"schema_version": "pr_brief_preflight.v2"}
            with (
                mock.patch.object(MODULE, "update", return_value=receipt),
                mock.patch.object(MODULE, "_write_receipt") as write_receipt,
                mock.patch("builtins.print") as output,
            ):
                self.assertEqual(
                    MODULE.main(
                        [
                            "--repo",
                            "o/r",
                            "--pr",
                            "1",
                            "--body-file",
                            str(body),
                        ]
                    ),
                    0,
                )
        write_receipt.assert_called_once_with(receipt, receipt_root=None)
        self.assertEqual(json.loads(output.call_args.args[0]), receipt)

    def test_receipt_is_atomically_persisted_at_the_fleet_path(self) -> None:
        receipt = {
            "schema_version": "pr_brief_preflight.v2",
            "repository": "njrun1804-cc/Zion",
            "pull_request": 43,
            "head_sha": "a" * 40,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = MODULE._write_receipt(receipt, receipt_root=root)
            self.assertEqual(path, root / "njrun1804-cc" / "Zion" / "43.json")
            self.assertEqual(json.loads(path.read_text()), receipt)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    @mock.patch.object(MODULE, "_verify_dependencies")
    @mock.patch.object(MODULE, "_git")
    @mock.patch.object(MODULE, "_gh_json")
    @mock.patch.object(MODULE, "_gh")
    @mock.patch.object(MODULE, "parse_dependencies", return_value=[])
    @mock.patch.object(MODULE, "validate", return_value=[])
    def test_create_pushes_then_opens_ready_pr_with_exact_body(
        self,
        validate: mock.Mock,
        parse_dependencies: mock.Mock,
        gh: mock.Mock,
        gh_json: mock.Mock,
        git: mock.Mock,
        verify_dependencies: mock.Mock,
    ) -> None:
        git.side_effect = ["c" * 40, "codex/new", "docs/guide.md", None]
        gh.side_effect = ["[]", "https://github.com/o/r/pull/7", ""]
        draft = {
            "body": "valid",
            "headRefName": "codex/new",
            "headRefOid": "c" * 40,
            "isDraft": True,
            "state": "OPEN",
            "url": "https://github.com/o/r/pull/7",
        }
        gh_json.side_effect = [draft, {**draft, "isDraft": False}]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = root / "body.md"
            body.write_text("valid")
            (root / "docs").mkdir()
            (root / "docs" / "agent-ready.md").write_text("safe")
            receipt = MODULE.create(
                repo="o/r",
                title="Ready candidate",
                body_file=body,
                candidate_worktree=root,
            )
        self.assertEqual(receipt["pull_request"], 7)
        self.assertEqual(
            gh.call_args_list[1].args,
            (
                "pr",
                "create",
                "--repo",
                "o/r",
                "--title",
                "Ready candidate",
                "--body",
                "valid",
                "--draft",
                "--head",
                "codex/new",
                "--base",
                "main",
            ),
        )
        self.assertEqual(
            gh.call_args_list[-1].args,
            ("pr", "ready", "7", "--repo", "o/r"),
        )

    @mock.patch.object(MODULE, "_verify_dependencies")
    @mock.patch.object(MODULE, "_git")
    @mock.patch.object(MODULE, "_gh_json")
    @mock.patch.object(MODULE, "_gh")
    @mock.patch.object(MODULE, "parse_dependencies", return_value=[])
    @mock.patch.object(MODULE, "validate", return_value=[])
    def test_create_mismatch_quarantines_new_pr_without_receipt(
        self,
        validate: mock.Mock,
        parse_dependencies: mock.Mock,
        gh: mock.Mock,
        gh_json: mock.Mock,
        git: mock.Mock,
        verify_dependencies: mock.Mock,
    ) -> None:
        git.side_effect = ["c" * 40, "codex/new", "src/main.py", None]
        gh.side_effect = ["[]", "https://github.com/o/r/pull/7", ""]
        gh_json.return_value = {
            "body": "concurrent body",
            "headRefName": "codex/new",
            "headRefOid": "d" * 40,
            "state": "OPEN",
            "url": "https://github.com/o/r/pull/7",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = root / "body.md"
            body.write_text("valid")
            (root / "docs").mkdir()
            (root / "docs" / "agent-ready.md").write_text("safe")
            with self.assertRaisesRegex(MODULE.CommandError, "does not match"):
                MODULE.create(
                    repo="o/r",
                    title="Ready candidate",
                    body_file=body,
                    candidate_worktree=root,
                )
        self.assertEqual(
            gh.call_args_list[-1].args,
            ("pr", "ready", "7", "--repo", "o/r", "--undo"),
        )

    @mock.patch.object(MODULE, "_verify_dependencies")
    @mock.patch.object(MODULE, "_git")
    @mock.patch.object(MODULE, "_gh")
    @mock.patch.object(MODULE, "parse_dependencies", return_value=[])
    @mock.patch.object(MODULE, "validate", return_value=[])
    def test_create_rejects_existing_open_pr_before_push(
        self,
        validate: mock.Mock,
        parse_dependencies: mock.Mock,
        gh: mock.Mock,
        git: mock.Mock,
        verify_dependencies: mock.Mock,
    ) -> None:
        git.side_effect = ["c" * 40, "codex/new", "src/main.py"]
        gh.return_value = json.dumps(
            [{"number": 7, "isDraft": False, "headRefOid": "b" * 40}]
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = root / "body.md"
            body.write_text("valid")
            (root / "docs").mkdir()
            (root / "docs" / "agent-ready.md").write_text("safe")
            with self.assertRaisesRegex(MODULE.CommandError, "already has open pull request"):
                MODULE.create(
                    repo="o/r",
                    title="Ready candidate",
                    body_file=body,
                    candidate_worktree=root,
                )
        self.assertNotIn(
            ("push", "origin", "HEAD:refs/heads/codex/new"),
            [call.args[1:] for call in git.call_args_list],
        )


if __name__ == "__main__":
    unittest.main()
