# Engineering control plane

Maintainer-owned reusable CI and policy for active `njrun1804-cc` repositories.

This execution repository is public because GitHub permits a public repository such as Bambu to
call reusable workflows only from another public repository. It contains no application secrets
or protected sentinel tests. Any held-out acceptance oracle belongs in a separate private
repository.

The common contract is evidence, not identical toolchains. Each repository selects a closed,
maintainer-owned profile; callers cannot supply shell commands, runner labels, credentials, or
permissions. The control plane supplies a hardened, consistently named execution envelope.
Security analysis remains a separate orthogonal job because it has different GitHub permissions
and availability.

## Reusable workflows

- `repo-check.yml`: one Linux deterministic gate with a closed set of active repository profiles.
- `codeql.yml`: high-precision CodeQL analysis where GitHub Code Security is enabled.
- `dependency-review.yml`: pull-request dependency diff gate where GitHub Code Security is enabled.

Consumers pin reusable workflows to a full commit SHA. Updates are deliberate fleet migrations,
not mutable-tag changes.

Every non-Dependabot pull request must carry the agent-ready execution brief represented by
`.github/PULL_REQUEST_TEMPLATE.md`: intent, behavioral contract, impact surface, risk hypotheses,
validation path, evidence, and operational changes. The reusable workflows enforce those stable
section names so Codex, CI, Greptile, and T-Rex receive the same change contract. Repository-native
setup, fixtures, targeted commands, and the canonical gate remain in each repository rather than
being replaced with a second generic command layer. Validation rejects missing, duplicated, and
empty sections after stripping template comments and label-only scaffolding.

Before editing a PR, use the fail-closed local send path:

```bash
python3 scripts/update_pr_body.py \
  --repo OWNER/REPOSITORY --pr NUMBER --body-file /path/to/body.md \
  --candidate-worktree "$PWD" --push-candidate
```

The same validator is embedded in CI. The helper closes each declared risk hypothesis, verifies
exact open or merged dependency heads, keeps the PR draft while it sends and verifies the body and
candidate, and safely replaces a rebased head only under an exact expected-remote lease. It then
publishes ready and atomically persists plus emits a `pr_brief_preflight.v2`
receipt under the XDG state tree. Repository CI and
external AI review then run in parallel with the authoritative local gate. Merge remains bound to
the unchanged exact SHA, current dependency heads, and all required terminal checks.
Candidate pushes are limited to same-repository PR heads. A rejected lease restores the prior body
and leaves the PR quarantined as a draft; rollback failure is explicit and never emits a receipt.

The fleet standard is capability-based: each repository documents its real bootstrap, targeted
verification, full gate, safe smoke or exercise path, fixtures/state, environment/services,
resource and mutation boundaries, and architecture invariants. A repository may explicitly mark a
capability unsupported or live-only; it must not invent a generic `make` target that hides its real
toolchain.

`policies/default-branch-ruleset.json` is the applied organization ruleset source. Retired
repositories are explicitly excluded. For active repositories it requires a
pull request, the common `repo-check / repo-check` status, current-base testing, resolved
conversations, squash merging, linear history, and no force-push or deletion on each default
branch.

macOS is not a default matrix dimension. A repository may add a targeted macOS job only when it
tests an Apple-specific runtime, framework, filesystem behavior, or packaging artifact that Linux
cannot exercise.
