# RUNBOOK

Developer runbook: lint, format, tests, CI, and troubleshooting. For install and run, see [README.md](../README.md#getting-started).

## Requirements
- Python 3.13
- pip
- Optional: virtualenv (recommended)

## Lint / Format
```bash
ruff format --check .
ruff check .
```

## Tests
```bash
pytest -q
```

Run from repo root so `tests/conftest.py` can add `server/` to `sys.path`.

## Build
No build step (static client + Python runtime).

## Security checks (CI)
- **Secret scan**: GitHub Actions workflow "Secret Scan" (gitleaks).
- **SAST**: GitHub Actions workflow "CodeQL".
- **Dependency scan**: GitHub Actions "Dependency Scan" (pip-audit). Local: `pip install pip-audit && pip-audit -r requirements.txt -r requirements-dev.txt`.

## Fast loop
```bash
ruff check .
pytest -q
```

## Full loop
```bash
ruff format --check .
ruff check .
pytest -q
```

## Troubleshooting
- Tests cannot import `config` or `ws_server`: run from repo root so `tests/conftest.py` adds `server/` to `sys.path`.
- No `.dem` files detected: place demo files in `demos/` or pass `--demo-dir`.
- Map metadata: files under `maps/` are gitignored (licensing). For custom bounds or overlays, add them locally.
