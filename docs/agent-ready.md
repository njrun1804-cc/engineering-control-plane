# Agent-ready execution contract

- **Bootstrap:** stock Python 3 for deterministic validators and `uvx zizmor==1.28.0` for workflow
  security analysis. No application dependency environment exists.
- **Targeted verification:** `python3 -m unittest discover -s tests -v` and
  `python3 scripts/embed_pr_validator.py`.
- **PR-body preflight:** ordinary CC fleet callers use
  `zion pr send --repo OWNER/REPO --pr NUMBER --body-file BODY.md --worktree "$PWD"`;
  `--create --title TITLE` creates a ready PR. Zion resolves this repository's validator and
  sender from the exact commit pinned in workspace policy. Within ECP development or bootstrap,
  the backend command remains `python3 scripts/update_pr_body.py --repo OWNER/REPO --pr NUMBER
  --body-file BODY.md --candidate-worktree "$PWD" --push-candidate`. Both paths keep the PR draft
  until exact verification, accept exact open or merged dependency heads, bind rebased replacement
  to the canonical repository and exact expected-remote lease, restore the prior body after push
  failure, and atomically persist plus emit `pr_brief_preflight.v2` under
  `${XDG_STATE_HOME:-$HOME/.local/state}/pr-brief-preflight/`. Cross-repository PR heads are
  rejected; never use a raw edit path.
- **Full gate:** the `control-plane` profile validates unit tests, generated mirrors, JSON/YAML,
  action pins, and zizmor in `.github/workflows/repo-check.yml`.
- **Safe exercise:** `python3 -m unittest discover -s tests -v`, generated-file checks, JSON/YAML
  parsing, and `uvx zizmor==1.28.0 .github/workflows` are the complete local runtime surface.
- **Fixtures and state:** unit-test strings and policy JSON are immutable repository evidence; no
  protected sentinel or application fixture belongs here.
- **Environment and services:** the `control-plane` profile needs no service or credential. Private
  profiles exchange GitHub OIDC for a read-only CodeArtifact token and require package-network
  access; they never receive the token from caller input.
- **Safety and resources:** repository content is public and credential-free; callers cannot
  provide commands, runners, permissions, or secrets. Repository profiles never deploy or mutate
  application/provider state. CodeQL alone has `security-events: write` to upload SARIF to GitHub.
- **Architecture and invariants:** `README.md`, `AGENTS.md`, reusable workflows, and
  `policies/default-branch-ruleset.json` are the control surface.
- **Latency sequence:** after focused proof and PR-body preflight, push the candidate head so CI
  and external AI review start together, then run the repository's authoritative local gate while
  those remote checks are in flight. Callers include `edited` and `ready_for_review` in their
  pull-request triggers so body-only repair cannot reuse a stale validation event. Merge still
  requires every proof on the unchanged exact SHA.
