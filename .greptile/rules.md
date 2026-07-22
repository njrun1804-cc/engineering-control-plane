# Review rules

- Report only logic or syntax defects that are reproducible from the pull request.
- Treat this repository as public and credential-free. Reject credentials, private endpoints,
  customer data, production mutation, or arbitrary caller-controlled commands and runner labels.
- Preserve full-SHA external Action pins and the stable `repo-check / repo-check` context.
- Reusable workflows may validate callers but must not deploy, mutate AWS, or cross network trust
  boundaries.
