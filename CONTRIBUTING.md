# Contributing

## Development
- Requirements: Python 3.13 (see README).
- Install dependencies with `python -m pip install -r requirements.txt -r requirements-dev.txt`.
- Run checks: `ruff format --check .`, `ruff check .`, `pytest -q`.

## Guidelines
- Keep changes minimal and focused.
- For audit and inspection history, see [docs/development/CODE_INSPECTION_FINDINGS.md](docs/development/CODE_INSPECTION_FINDINGS.md).
- Do not include secrets, tokens, or private data in code or logs.
- Update documentation when behavior changes.
