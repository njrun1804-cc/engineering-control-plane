# Engineering control plane

Maintainer-owned reusable CI and policy for active `njrun1804-cc` repositories.

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

`policies/default-branch-ruleset.json` is the applied organization ruleset source. Archived legacy
repositories are explicitly excluded. For active repositories it requires a
pull request, the common `repo-check / repo-check` status, current-base testing, resolved
conversations, squash merging, linear history, and no force-push or deletion on each default
branch.

macOS is not a default matrix dimension. A repository may add a targeted macOS job only when it
tests an Apple-specific runtime, framework, filesystem behavior, or packaging artifact that Linux
cannot exercise.
