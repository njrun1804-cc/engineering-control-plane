#!/usr/bin/env python3
"""Validate, send, and optionally push one exact pull-request candidate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import time
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
parse_dependencies = _load_validator().parse_dependencies
risk_result_count = _load_validator().risk_result_count


class BriefValidationError(ValueError):
    """The body failed the deterministic execution-brief contract."""


class CommandError(RuntimeError):
    """A required Git or GitHub operation failed."""


def _command(
    args: list[str], *, cwd: Path | None = None, capture: bool = True
) -> str | None:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            check=True,
            text=True,
            capture_output=capture,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise CommandError(detail) from exc
    return result.stdout.strip() if capture else None


def _gh(*args: str) -> str:
    return str(_command(["gh", *args]) or "")


def _gh_json(*args: str) -> dict[str, object]:
    value = json.loads(_gh(*args))
    if not isinstance(value, dict):
        raise CommandError("GitHub command did not return an object")
    return value


def _open_pull_requests(
    *, repo: str, branch: str, attempts: int = 1
) -> list[dict[str, object]]:
    value: object = []
    for attempt in range(attempts):
        try:
            value = json.loads(
                _gh(
                    "pr",
                    "list",
                    "--repo",
                    repo,
                    "--head",
                    branch,
                    "--state",
                    "open",
                    "--json",
                    "number,isDraft,headRefOid",
                )
            )
        except json.JSONDecodeError as exc:
            raise CommandError(
                "could not inspect existing pull requests for candidate branch"
            ) from exc
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise CommandError("GitHub pull request list did not return an array of objects")
        if value or attempt + 1 == attempts:
            break
        time.sleep(1)
    return value


def _git(worktree: Path, *args: str) -> str | None:
    return _command(["git", "-C", str(worktree), *args], capture=args[0] != "push")


def _verify_dependencies(dependencies: list[dict[str, object]]) -> None:
    for item in dependencies:
        repository = str(item["repository"])
        number = str(item["pull_request"])
        expected = str(item["head_sha"])
        observed = _gh_json(
            "pr",
            "view",
            number,
            "--repo",
            repository,
            "--json",
            "headRefOid,state",
        )
        if observed.get("state") not in {"OPEN", "MERGED"}:
            raise BriefValidationError(
                f"dependency {repository}#{number} is neither open nor merged"
            )
        if observed.get("headRefOid") != expected:
            raise BriefValidationError(f"dependency {repository}#{number} head drifted")


def _observe_pushed_candidate(
    *,
    repo: str,
    pull_request: int,
    head_sha: str,
    attempts: int = 6,
) -> dict[str, object]:
    observed: dict[str, object] = {}
    for attempt in range(attempts):
        observed = _gh_json(
            "pr",
            "view",
            str(pull_request),
            "--repo",
            repo,
            "--json",
            "body,headRefName,headRefOid,isDraft,state,url",
        )
        if observed.get("headRefOid") == head_sha:
            return observed
        if attempt + 1 < attempts:
            time.sleep(1)
    return observed


def _quarantine_pull_request(*, repo: str, pull_request: int) -> None:
    _gh(
        "pr",
        "ready",
        str(pull_request),
        "--repo",
        repo,
        "--undo",
    )


def _publish_ready_pull_request(*, repo: str, pull_request: int) -> None:
    _gh("pr", "ready", str(pull_request), "--repo", repo)


def _receipt(
    *,
    repo: str,
    pull_request: int,
    head_sha: str | None,
    body: str,
    dependencies: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": "pr_brief_preflight.v2",
        "repository": repo,
        "pull_request": pull_request,
        "head_sha": head_sha,
        "visible_body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "dependencies": dependencies,
        "validator_sha256": hashlib.sha256(VALIDATOR.read_bytes()).hexdigest(),
        "risk_result_count": risk_result_count(body),
    }


def _write_receipt(
    receipt: dict[str, object],
    *,
    receipt_root: Path | None = None,
) -> Path:
    repository = str(receipt["repository"])
    owner, name = repository.split("/", maxsplit=1)
    root = receipt_root or (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "pr-brief-preflight"
    )
    target = root / owner / name / f"{int(receipt['pull_request'])}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(receipt, stream, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def _candidate(
    *,
    body: str,
    candidate_worktree: Path,
) -> tuple[Path, str, str, list[str], list[dict[str, object]]]:
    candidate_worktree = candidate_worktree.resolve()
    agent_ready = candidate_worktree / "docs" / "agent-ready.md"
    agent_ready_text = agent_ready.read_text(encoding="utf-8")
    head_sha = str(_git(candidate_worktree, "rev-parse", "HEAD"))
    branch = str(_git(candidate_worktree, "branch", "--show-current"))
    changed = str(
        _git(candidate_worktree, "diff", "--name-only", "origin/main...HEAD") or ""
    ).splitlines()
    errors = validate(
        body,
        agent_ready_text=agent_ready_text,
        changed_files=changed,
    )
    if errors:
        raise BriefValidationError("\n".join(errors))
    dependencies = parse_dependencies(body)
    _verify_dependencies(dependencies)
    return candidate_worktree, head_sha, branch, changed, dependencies


def update(
    *,
    repo: str,
    pull_request: int,
    body_file: Path,
    candidate_worktree: Path | None = None,
    push_candidate: bool = False,
    gh: str = "gh",
) -> dict[str, object]:
    body = body_file.read_text(encoding="utf-8")
    if candidate_worktree is None:
        errors = validate(body)
        if errors:
            raise BriefValidationError("\n".join(errors))
        dependencies = parse_dependencies(body)
        _verify_dependencies(dependencies)
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
        return _receipt(
            repo=repo,
            pull_request=pull_request,
            head_sha=None,
            body=body,
            dependencies=dependencies,
        )

    candidate_worktree, head_sha, branch, _, dependencies = _candidate(
        body=body,
        candidate_worktree=candidate_worktree,
    )
    pull = _gh_json(
        "pr",
        "view",
        str(pull_request),
        "--repo",
        repo,
        "--json",
        "body,headRefName,headRefOid,headRepository,isCrossRepository,isDraft,state,url",
    )
    if pull.get("state") != "OPEN":
        raise BriefValidationError(f"pull request {pull_request} is not open")
    if pull.get("headRefName") != branch:
        raise BriefValidationError(
            f"candidate branch {branch!r} does not match PR head {pull.get('headRefName')!r}"
        )
    head_repository = pull.get("headRepository")
    if pull.get("isCrossRepository") is True or (
        isinstance(head_repository, dict)
        and head_repository.get("nameWithOwner") != repo
    ):
        raise BriefValidationError(
            "cross-repository PR heads are not supported by --push-candidate"
        )
    prior_body = pull.get("body")
    if not isinstance(prior_body, str):
        raise BriefValidationError("GitHub PR body is not a string")
    _git(candidate_worktree, "fetch", "origin", branch)
    remote_head = str(_git(candidate_worktree, "rev-parse", f"origin/{branch}"))
    if remote_head != pull.get("headRefOid"):
        raise BriefValidationError(
            "local remote-tracking head does not match GitHub PR head"
        )
    if not push_candidate and head_sha != pull.get("headRefOid"):
        raise BriefValidationError(
            "candidate HEAD does not match GitHub PR head; use --push-candidate"
        )
    if pull.get("isDraft") is not True:
        _quarantine_pull_request(repo=repo, pull_request=pull_request)
    _gh("pr", "edit", str(pull_request), "--repo", repo, "--body", body)
    if push_candidate:
        try:
            _git(
                candidate_worktree,
                "push",
                f"--force-with-lease=refs/heads/{branch}:{remote_head}",
                "origin",
                f"HEAD:refs/heads/{branch}",
            )
        except CommandError as push_error:
            rollback_error: CommandError | None = None
            try:
                _gh(
                    "pr",
                    "edit",
                    str(pull_request),
                    "--repo",
                    repo,
                    "--body",
                    prior_body,
                )
            except CommandError as exc:
                rollback_error = exc
            _quarantine_pull_request(repo=repo, pull_request=pull_request)
            if rollback_error is not None:
                raise CommandError(
                    f"{push_error}; PR body rollback failed: {rollback_error}"
                ) from push_error
            raise
        observed = _observe_pushed_candidate(
            repo=repo,
            pull_request=pull_request,
            head_sha=head_sha,
        )
        if observed.get("headRefOid") != head_sha:
            _quarantine_pull_request(repo=repo, pull_request=pull_request)
            raise CommandError("GitHub PR head does not match pushed candidate")
    observed = _gh_json(
        "pr",
        "view",
        str(pull_request),
        "--repo",
        repo,
        "--json",
        "body,headRefName,headRefOid,isDraft,state,url",
    )
    if (
        observed.get("headRefOid") != head_sha
        or observed.get("body") != body
        or observed.get("isDraft") is not True
    ):
        _quarantine_pull_request(repo=repo, pull_request=pull_request)
        raise CommandError("draft pull request does not match validated candidate")
    _publish_ready_pull_request(repo=repo, pull_request=pull_request)
    ready = _gh_json(
        "pr",
        "view",
        str(pull_request),
        "--repo",
        repo,
        "--json",
        "body,headRefName,headRefOid,isDraft,state,url",
    )
    if (
        ready.get("headRefOid") != head_sha
        or ready.get("body") != body
        or ready.get("isDraft") is not False
    ):
        _quarantine_pull_request(repo=repo, pull_request=pull_request)
        raise CommandError("ready pull request does not match validated candidate")
    return _receipt(
        repo=repo,
        pull_request=pull_request,
        head_sha=head_sha,
        body=body,
        dependencies=dependencies,
    )


def create(
    *,
    repo: str,
    title: str,
    body_file: Path,
    candidate_worktree: Path,
    base: str = "main",
) -> dict[str, object]:
    body = body_file.read_text(encoding="utf-8")
    candidate_worktree, head_sha, branch, _, dependencies = _candidate(
        body=body,
        candidate_worktree=candidate_worktree,
    )
    existing = _open_pull_requests(repo=repo, branch=branch)
    if existing:
        numbers = ", ".join(str(item.get("number")) for item in existing)
        raise CommandError(
            f"candidate branch already has open pull request(s) {numbers}; use --pr"
        )
    _git(candidate_worktree, "push", "origin", f"HEAD:refs/heads/{branch}")
    try:
        url = _gh(
            "pr",
            "create",
            "--repo",
            repo,
            "--title",
            title,
            "--body",
            body,
            "--draft",
            "--head",
            branch,
            "--base",
            base,
        )
    except CommandError:
        for pull in _open_pull_requests(repo=repo, branch=branch, attempts=5):
            if pull.get("isDraft") is False:
                _quarantine_pull_request(repo=repo, pull_request=int(pull["number"]))
        raise
    observed = _gh_json(
        "pr",
        "view",
        url,
        "--repo",
        repo,
        "--json",
        "body,headRefName,headRefOid,isDraft,state,url",
    )
    if (
        observed.get("headRefOid") != head_sha
        or observed.get("body") != body
        or observed.get("isDraft") is not True
    ):
        try:
            pull_request = int(url.rstrip("/").rsplit("/", maxsplit=1)[-1])
        except ValueError as exc:
            raise CommandError(
                "could not quarantine mismatched created pull request"
            ) from exc
        _quarantine_pull_request(repo=repo, pull_request=pull_request)
        raise CommandError("created pull request does not match validated candidate")
    try:
        pull_request = int(str(observed["url"]).rstrip("/").rsplit("/", maxsplit=1)[-1])
    except (KeyError, ValueError) as exc:
        raise CommandError("could not resolve created pull request number") from exc
    _publish_ready_pull_request(repo=repo, pull_request=pull_request)
    ready = _gh_json(
        "pr",
        "view",
        str(pull_request),
        "--repo",
        repo,
        "--json",
        "body,headRefName,headRefOid,isDraft,state,url",
    )
    if (
        ready.get("headRefOid") != head_sha
        or ready.get("body") != body
        or ready.get("isDraft") is not False
    ):
        _quarantine_pull_request(repo=repo, pull_request=pull_request)
        raise CommandError("ready pull request does not match validated candidate")
    return _receipt(
        repo=repo,
        pull_request=pull_request,
        head_sha=head_sha,
        body=body,
        dependencies=dependencies,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--pr", type=int)
    mode.add_argument("--create", action="store_true")
    parser.add_argument("--title")
    parser.add_argument("--base", default="main")
    parser.add_argument("--body-file", required=True, type=Path)
    parser.add_argument("--candidate-worktree", type=Path)
    parser.add_argument("--push-candidate", action="store_true")
    parser.add_argument("--receipt-root", type=Path)
    args = parser.parse_args(argv)
    if args.push_candidate and args.candidate_worktree is None:
        parser.error("--push-candidate requires --candidate-worktree")
    if args.create and (not args.title or args.candidate_worktree is None):
        parser.error("--create requires --title and --candidate-worktree")
    try:
        if args.create:
            receipt = create(
                repo=args.repo,
                title=args.title,
                body_file=args.body_file,
                candidate_worktree=args.candidate_worktree,
                base=args.base,
            )
        else:
            receipt = update(
                repo=args.repo,
                pull_request=args.pr,
                body_file=args.body_file,
                candidate_worktree=args.candidate_worktree,
                push_candidate=args.push_candidate,
            )
    except BriefValidationError as exc:
        print(exc)
        return 2
    except (CommandError, subprocess.CalledProcessError) as exc:
        print(exc)
        return 1
    _write_receipt(receipt, receipt_root=args.receipt_root)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
