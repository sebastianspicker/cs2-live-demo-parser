# CI Overview

This repository uses GitHub Actions for a fast, deterministic, and low-maintenance CI pipeline.

## Workflows
- `CI` (`.github/workflows/ci.yml`)
  - Triggers: `push`, `pull_request`, `workflow_dispatch`
  - Steps: ruff format check, ruff lint, pytest
- `Dependency Scan` (`.github/workflows/dependency-scan.yml`)
  - Triggers: `push`, `pull_request`, `workflow_dispatch`, weekly schedule
  - Steps: pip-audit against `requirements.txt` and `requirements-dev.txt`
- `Secret Scan` (`.github/workflows/secret-scan.yml`)
  - Triggers: `push`, `pull_request`, `workflow_dispatch`, weekly schedule
  - Steps: gitleaks scan with redaction
- `CodeQL` (`.github/workflows/codeql.yml`)
  - Triggers: `push`, `pull_request`, `workflow_dispatch`, weekly schedule
  - Notes: skipped for fork PRs to avoid permission errors on security-event upload

## Local Reproduction
Use the provided script to run the same checks locally.

```bash
./scripts/ci-local.sh
```

Optional extras (match scheduled jobs):

```bash
RUN_PIP_AUDIT=1 ./scripts/ci-local.sh
RUN_GITLEAKS=1 ./scripts/ci-local.sh
```

Environment overrides:
- `VENV_PATH`: path to the virtual environment (default: `.venv`)
- `PYTHON_BIN`: Python executable to use (default: `python`)

### Gitleaks Local Setup
If you want to run `RUN_GITLEAKS=1`, install gitleaks first:

```bash
brew install gitleaks
# or
GOBIN=$HOME/.local/bin go install github.com/zricethezav/gitleaks/v8@v8.18.4
```

## Secrets and Repo Settings
- No repository secrets are required for CI.
- `GITHUB_TOKEN` is used with minimal permissions (`contents: read`) for most jobs.
- If this repo moves to an organization account, `GITLEAKS_LICENSE` may be required.

## Extending CI
- Keep PR checks fast; schedule or manual triggers for heavy or integration tests.
- Use pinned tool versions and lockfiles when adding new languages.
- Add caching for language package managers and avoid downloading large assets on every run.

## Optional: Act
If you use `act`, run workflows locally like this:

```bash
act -W .github/workflows/ci.yml
```
