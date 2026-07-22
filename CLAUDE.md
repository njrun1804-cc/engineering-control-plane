# Engineering control plane

This public repository owns shared CI execution and policy for `njrun1804-cc`. It is public so
public repositories can call its reusable workflows. Protected acceptance tests belong in a
separate private repository.

- Keep third-party Actions pinned to full commit SHAs.
- Default `GITHUB_TOKEN` permissions are read-only.
- Keep deterministic repository checks authoritative; AI review is additional evidence.
- Do not put application secrets or application implementation in this repository.
- Changes to workflows, policies, and sentinels require maintainer review and must not be judged
  solely by the gate they change.
- Prefer one Linux job. Add targeted macOS evidence only for a named platform-specific contract.
