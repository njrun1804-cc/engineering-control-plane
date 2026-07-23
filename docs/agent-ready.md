# Agent-ready execution contract

- **Bootstrap:** stock Python 3 for deterministic validators; `uvx zizmor==1.28.0` for workflow
  security analysis. No application dependency environment exists.
- **Targeted verification:** `python3 -m unittest discover -s tests -v` and
  `python3 scripts/embed_pr_validator.py`.
- **Full gate:** the `control-plane` profile validates unit tests, generated mirrors, JSON/YAML,
  action pins, and zizmor in `.github/workflows/repo-check.yml`.
- **Safe exercise:** unit tests, `actionlint .github/workflows/*.yml`, and
  `zizmor .github/workflows` are the complete runtime surface.
- **Fixtures and state:** unit-test strings and policy JSON are immutable repository evidence; no
  protected sentinel or application fixture belongs here.
- **Environment and services:** no service, credential, private package, or provider is required.
- **Safety and resources:** public and credential-free; callers cannot provide commands, runners,
  permissions, or secrets. Workflows never deploy or mutate external state.
- **Architecture and invariants:** `README.md`, `AGENTS.md`, reusable workflows, and
  `policies/default-branch-ruleset.json` are the control surface.
