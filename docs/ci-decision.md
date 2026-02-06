# CI Decision

## Decision
**FULL CI** for this repository.

## Rationale
- The repo contains executable Python code with a test suite; fast, deterministic checks add real value on every change.
- No tests require live infrastructure, proprietary data, or secrets; everything can run on GitHub-hosted runners.
- The suite is small and completes quickly, so the CI cost is low and reliability is high.
- Security posture benefits from ongoing SAST, dependency scanning, and secret scanning.

## What Runs Where
- Pull requests (including forks):
  - `CI` (ruff format check, ruff lint, pytest)
  - `Dependency Scan` (pip-audit)
  - `Secret Scan` (gitleaks; comments/artifact upload disabled)
- Push to default branch:
  - All PR checks above
  - `CodeQL` analysis
- Scheduled (weekly):
  - `Secret Scan`
  - `Dependency Scan`
  - `CodeQL`

## CI Threat Model (Fork PRs)
- Untrusted code runs on PRs, so **no secrets** are used.
- `pull_request_target` is **not** used to avoid token abuse.
- Token permissions are minimal (`contents: read` for most workflows).
- gitleaks PR comments and artifact uploads are disabled to avoid requiring elevated permissions.
- CodeQL is skipped for fork PRs to prevent permission errors on security-event uploads.

## If We Later Want “More Than Full”
We already run full static + unit CI. If we later add heavier checks (e.g., end-to-end demo parsing or performance/regression tests), we would need:
- Test demo fixtures or generated artifacts checked into a dedicated test data bucket.
- Optional self-hosted runners if compute or data access becomes heavy.
- Clear separation between fast PR checks and heavy scheduled/manual jobs.
