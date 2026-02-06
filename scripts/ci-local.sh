#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="${VENV_PATH:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python}"

if [[ ! -d "$VENV_PATH" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_PATH"
fi

# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "$ROOT_DIR/requirements.txt" -r "$ROOT_DIR/requirements-dev.txt"

python -m ruff format --check "$ROOT_DIR"
python -m ruff check "$ROOT_DIR"
python -m pytest -q

if [[ "${RUN_PIP_AUDIT:-0}" == "1" ]]; then
  python -m pip install pip-audit
  python -m pip_audit -r "$ROOT_DIR/requirements.txt" -r "$ROOT_DIR/requirements-dev.txt"
fi

if [[ "${RUN_GITLEAKS:-0}" == "1" ]]; then
  if ! command -v gitleaks >/dev/null 2>&1; then
    echo "gitleaks not found. Install with 'brew install gitleaks' or" >&2
    echo "'go install github.com/zricethezav/gitleaks/v8@v8.18.4'" >&2
    exit 1
  fi
  gitleaks detect --redact --no-banner --source "$ROOT_DIR"
fi
