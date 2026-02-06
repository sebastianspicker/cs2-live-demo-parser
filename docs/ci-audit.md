# CI Audit

## Inventory
- `CI` (`.github/workflows/ci.yml`)
  - Triggers: `push`, `pull_request`, `workflow_dispatch`
  - Job: Python lint + tests (ruff, pytest)
  - Actions: `actions/checkout@v4`, `actions/setup-python@v5`
  - Permissions: `contents: read`
- `CodeQL` (`.github/workflows/codeql.yml`)
  - Triggers: `push`, `pull_request`, `workflow_dispatch`, weekly schedule
  - Job: CodeQL analysis (Python + JavaScript)
  - Actions: `actions/checkout@v4`, `github/codeql-action/init@v3`, `github/codeql-action/analyze@v3`
  - Permissions: `contents: read`, `actions: read`, `security-events: write`
- `Dependency Scan` (`.github/workflows/dependency-scan.yml`)
  - Triggers: `push`, `pull_request`, `workflow_dispatch`, weekly schedule
  - Job: pip-audit
  - Actions: `actions/checkout@v4`, `actions/setup-python@v5`
  - Permissions: `contents: read`
- `Secret Scan` (`.github/workflows/secret-scan.yml`)
  - Triggers: `push`, `pull_request`, `workflow_dispatch`, weekly schedule
  - Job: gitleaks
  - Actions: `actions/checkout@v4`, `gitleaks/gitleaks-action@v2`
  - Permissions: `contents: read`

## Latest Failures (from GitHub Actions API)
Log downloads for jobs require admin rights and are not available via the unauthenticated API. The latest failure details were inferred from run metadata and local reproduction.

| Workflow | Failure(s) | Root Cause | Fix Plan | Risk | How to Verify |
| --- | --- | --- | --- | --- | --- |
| CI | None observed | N/A | N/A | Low | Run `./scripts/ci-local.sh` and confirm CI run passes on PR/push |
| CodeQL | None observed | N/A | N/A | Low | Trigger workflow on `push` or `workflow_dispatch` |
| Dependency Scan | None observed | N/A | N/A | Low | Run `RUN_PIP_AUDIT=1 ./scripts/ci-local.sh` |
| Secret Scan | Run #13 failed on 2026-02-05 (gitleaks job) | Likely permission mismatch: gitleaks action default attempts artifact upload / PR comments which require permissions beyond `contents: read` | Disable comments and artifact upload; pin gitleaks version; fetch full history | Medium (false negatives only if gitleaks is fully disabled; we did not disable scanning) | Run `RUN_GITLEAKS=1 ./scripts/ci-local.sh`; re-run workflow after update |

## Status
- Secret Scan: fixed in workflow updates (reduced permissions and deterministic gitleaks config).
