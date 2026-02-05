# RUNBOOK

## Scope
This runbook covers local setup, lint/format, tests, and runtime commands for the CS2 live demo parser + WebSocket broadcaster.

## Requirements
- Python 3.13
- pip
- Optional: virtualenv (recommended)

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Windows PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
```

## Run (Server)
```bash
python server/main.py
```

Optional flags:
- `--demo-dir <path>`
- `--poll-interval <seconds>`
- `--no-msgpack`
- `--parser-executor <none|thread|process>`
- `--metrics-port <port>`
- `--bind-host <ip>` (default `127.0.0.1`)
- `--metrics-host <ip>` (default `127.0.0.1`)

## Run (Client)
Open `client/index.html` in a browser. By default it connects to `ws://localhost:8765`.

## Lint / Format
```bash
ruff format --check .
ruff check .
```

## Tests
```bash
pytest -q
```

## Build
No build step (static client + Python runtime).

## Typecheck / Static Analysis
Not configured yet.

## Security Checks
### Secret Scan (CI)
- GitHub Actions workflow: `Secret Scan` (gitleaks).

### SAST (CI)
- GitHub Actions workflow: `CodeQL`.

### SCA / Dependency Scan
Local (optional):
```bash
python -m pip install pip-audit
pip-audit -r requirements.txt -r requirements-dev.txt
```
CI:
- GitHub Actions workflow: `Dependency Scan` (pip-audit).

## Fast Loop
```bash
ruff check .
pytest -q
```

## Full Loop
```bash
ruff format --check .
ruff check .
pytest -q
```

## Troubleshooting
- If tests cannot import `config` or `ws_server`, ensure you run from the repo root so `tests/conftest.py` can add `server/` to `sys.path`.
- If no `.dem` files are detected, place demo files in `demos/` or pass `--demo-dir`.
- Map metadata files live under `maps/` and are gitignored for licensing. If you need custom bounds or overlays, place the files locally.
