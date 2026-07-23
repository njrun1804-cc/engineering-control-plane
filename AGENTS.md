<!-- GENERATED from CLAUDE.md by scripts/mirror_agents.py — edit CLAUDE.md, never this file. -->
# Engineering control plane

This public, credential-free repository owns reusable CI execution and policy for
`njrun1804-cc`. It contains checks and policy only, never application code, protected acceptance
tests, or secrets. Protected acceptance tests belong in a separate private repository.

ECP is the independent public protocol backend. Zion is the CC workspace's local operator
frontend and resolves ECP validator/sender bytes from the exact commit pinned in workspace policy.
Ordinary fleet work uses `zion pr validate/send`; direct script invocation here is for bootstrap,
recovery, and control-plane development.

## Agent verification loop

- Each implementation task names and runs its exact targeted checks.
- Subagents run only those commands and never invoke a repository-wide gate.
- Before delivery, root runs the control-plane validation once; GitHub independently repeats it.

- Keep third-party Actions pinned to full commit SHAs.
- Default `GITHUB_TOKEN` permissions are read-only.
- Keep deterministic repository checks authoritative; AI review is additional evidence.
- Do not put application secrets or application implementation in this repository.
- Changes to workflows, policies, and sentinels require maintainer review and must not be judged
  solely by the gate they change.
- Prefer one Linux job. Add targeted macOS evidence only for a named platform-specific contract.
