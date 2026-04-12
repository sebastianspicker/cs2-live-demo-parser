# Maintenance and validation

This document describes what the repository contains and how to validate it (install, run, test). For getting started and configuration, see [README.md](README.md).

## Contents

| Path | Description |
|------|-------------|
| `client/` | Browser client (HTML/CSS/JS). |
| `server/` | Python WebSocket server and demo parser. |
| `tests/` | Pytest suite; required to validate the project. |
| `config.json` | Runtime configuration. |
| `requirements.txt`, `requirements-dev.txt`, `pyproject.toml` | Dependencies and tool config. |
| `.editorconfig`, `.gitignore` | Editor and VCS hygiene. |
| `.github/` | CI workflows (lint, test, CodeQL, dependency/secret scan). |
| `scripts/ci-local.sh` | Local reproduction of CI. |
| `demos/` | Demo files directory (`.gitkeep` in repo; `.dem` files gitignored). |
| `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md` | Legal and contribution docs. |
| `docs/` | User and developer documentation. |
| `README.md` | Getting started, configuration, documentation index. |

## Validation commands

Run from the repository root.

### Install

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt -r requirements-dev.txt
```

### Run

```bash
python server/main.py
```

Optional: `--bind-host 0.0.0.0`, `--demo-dir <path>`, `--metrics-port 8766`. Open `client/index.html` in a browser.

### Test

```bash
ruff format --check .
ruff check .
pytest -q
```

Or run the full local CI:

```bash
./scripts/ci-local.sh
```

Optional: `RUN_PIP_AUDIT=1 ./scripts/ci-local.sh` or `RUN_GITLEAKS=1 ./scripts/ci-local.sh`.
