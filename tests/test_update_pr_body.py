from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "update_pr_body", ROOT / "scripts" / "update_pr_body.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class UpdatePullRequestBodyTests(unittest.TestCase):
    @mock.patch.object(MODULE.subprocess, "run")
    @mock.patch.object(MODULE, "validate", return_value=[])
    def test_validated_body_is_sent_in_memory(self, validate: mock.Mock, run: mock.Mock) -> None:
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
    def test_original_replacement_cannot_change_sent_bytes(self, run: mock.Mock) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text("validated")

            def mutate_original(value: str) -> list[str]:
                body.write_text("replaced after validation")
                return [] if value == "validated" else ["unexpected"]

            with mock.patch.object(MODULE, "validate", side_effect=mutate_original):
                MODULE.update(repo="njrun1804-cc/Zion", pull_request=38, body_file=body)

        self.assertEqual(run.call_args.args[0][-1], "validated")


if __name__ == "__main__":
    unittest.main()
