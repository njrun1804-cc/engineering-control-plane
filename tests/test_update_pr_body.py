from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
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
    def test_validator_runs_before_github_edit(self, run: mock.Mock) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text("valid")
            MODULE.update(
                repo="njrun1804-cc/Zion",
                pull_request=38,
                body_file=body,
            )

        self.assertEqual(run.call_count, 2)
        validator, github = run.call_args_list
        validator_command = validator.args[0]
        github_command = github.args[0]
        self.assertEqual(validator_command[:3], [MODULE.sys.executable, str(MODULE.VALIDATOR), "--body-file"])
        self.assertEqual(
            github_command[:-1],
            ["gh", "pr", "edit", "38", "--repo", "njrun1804-cc/Zion", "--body-file"],
        )
        self.assertEqual(validator_command[-1], github_command[-1])
        self.assertNotEqual(github_command[-1], str(body))
        self.assertFalse(Path(github_command[-1]).exists())

    @mock.patch.object(MODULE.subprocess, "run")
    def test_failed_preflight_prevents_github_edit(self, run: mock.Mock) -> None:
        run.side_effect = subprocess.CalledProcessError(2, ["validator"])
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text("invalid")
            with self.assertRaises(subprocess.CalledProcessError):
                MODULE.update(
                    repo="njrun1804-cc/Zion",
                    pull_request=38,
                    body_file=body,
                )

        self.assertEqual(run.call_count, 1)

    @mock.patch.object(MODULE.subprocess, "run")
    def test_original_replacement_cannot_change_sent_bytes(self, run: mock.Mock) -> None:
        sent: list[bytes] = []
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_bytes(b"validated")

            def observe(command: list[str], *, check: bool) -> None:
                del check
                if command[1:3] == ["pr", "edit"]:
                    sent.append(Path(command[-1]).read_bytes())
                else:
                    body.write_bytes(b"replaced after validation")

            run.side_effect = observe
            MODULE.update(
                repo="njrun1804-cc/Zion",
                pull_request=38,
                body_file=body,
            )

        self.assertEqual(sent, [b"validated"])


if __name__ == "__main__":
    unittest.main()
