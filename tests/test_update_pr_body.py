from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
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
        body = Path("/tmp/body.md")

        MODULE.update(
            repo="njrun1804-cc/Zion",
            pull_request=38,
            body_file=body,
        )

        self.assertEqual(run.call_count, 2)
        validator, github = run.call_args_list
        self.assertEqual(
            validator.args[0],
            [
                MODULE.sys.executable,
                str(MODULE.VALIDATOR),
                "--body-file",
                str(body),
            ],
        )
        self.assertEqual(
            github.args[0],
            [
                "gh",
                "pr",
                "edit",
                "38",
                "--repo",
                "njrun1804-cc/Zion",
                "--body-file",
                str(body),
            ],
        )

    @mock.patch.object(MODULE.subprocess, "run")
    def test_failed_preflight_prevents_github_edit(self, run: mock.Mock) -> None:
        run.side_effect = subprocess.CalledProcessError(2, ["validator"])

        with self.assertRaises(subprocess.CalledProcessError):
            MODULE.update(
                repo="njrun1804-cc/Zion",
                pull_request=38,
                body_file=Path("/tmp/body.md"),
            )

        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
