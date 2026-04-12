# Archive Notice

This repository has been cleaned for long-term archiving. It contains runnable code and minimal final documentation only.

## Keep / Remove / Move (rationale)

### Kept

| Path | Rationale |
|-----|-----------|
| `client/` | Runnable browser client (HTML/CSS/JS). |
| `server/` | Runnable Python WebSocket server and demo parser. |
| `tests/` | Pytest suite; required to validate the project. |
| `config.json` | Runtime configuration. |
| `requirements.txt`, `requirements-dev.txt`, `pyproject.toml` | Dependencies and tool config. |
| `.editorconfig`, `.gitignore` | Editor and VCS hygiene. |
| `.github/` | CI workflows (lint, test, CodeQL, dependency/secret scan). |
| `scripts/ci-local.sh` | Local reproduction of CI (validation). |
| `demos/.gitkeep` | Keeps `demos/` in version control. |
| `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md` | Legal and contribution docs. |
| `docs/QUICK_START.md`, `docs/INSTALLATION.md` | User-facing quick start and install. |
| `docs/PARSER_DOCUMENTATION.md` | Parser behavior and usage. |
| `docs/SECURITY_AND_ANTICHEAT_FAQ.md` | Security and anticheat FAQ. |
| `docs/VALVE_NOTICE.md` | Valve-related risks and latency notes. |
| `docs/REPO_MAP.md` | Repository layout and entry points. |
| `docs/RUNBOOK.md` | Setup, run, lint, test, and troubleshooting. |
| `docs/issue-audit/` | **Issue Audit preserved**: read-only audit template (PRD, agent instructions). Moved from `.codex/ralph-audit/`; all tool-specific references removed. |

### Removed

| Path | Rationale |
|-----|-----------|
| `.codex/` | Tool-specific directory; contents moved to `docs/issue-audit/` and stripped of tool references. |
| `docs/ci-audit.md` | WIP/process artifact (CI failure log and status). |
| `docs/ci-decision.md` | Process artifact (CI decision record). |
| `docs/ci.md` | Redundant with RUNBOOK and README validation section. |

### Moved / Renamed

| From | To | Rationale |
|------|----|-----------|
| `.codex/ralph-audit/` | `docs/issue-audit/` | Issue Audit must be preserved; moved into `docs/` and generalized (no tool names). |
| (content) `CODEX.md` | `docs/issue-audit/AGENT_INSTRUCTIONS.md` | Same instructions, tool-agnostic; output paths updated to `docs/issue-audit/audit/*.md`. |
| (content) `prd.json` | `docs/issue-audit/prd.json` | Paths in description and acceptance criteria updated to `docs/issue-audit/audit/`. |
| — | (dropped) `ralph.sh`, `progress.txt` | Runner and progress log were tool-specific and WIP; not kept. |

---

## Final folder structure

```
.
├── .editorconfig
├── .github/
│   ├── dependabot.yml
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   ├── pull_request_template.md
│   └── workflows/
│       ├── ci.yml
│       ├── codeql.yml
│       ├── dependency-scan.yml
│       └── secret-scan.yml
├── .gitignore
├── ARCHIVE.md
├── client/
│   ├── css/
│   │   └── main.css
│   ├── index.html
│   └── js/
│       ├── app.js
│       ├── events.js
│       ├── msgpack.js
│       └── render.js
├── config.json
├── CONTRIBUTING.md
├── demos/
│   └── .gitkeep
├── docs/
│   ├── issue-audit/
│   │   ├── AGENT_INSTRUCTIONS.md
│   │   ├── prd.json
│   │   └── README.md
│   ├── INSTALLATION.md
│   ├── PARSER_DOCUMENTATION.md
│   ├── QUICK_START.md
│   ├── REPO_MAP.md
│   ├── RUNBOOK.md
│   ├── SECURITY_AND_ANTICHEAT_FAQ.md
│   ├── VALVE_NOTICE.md
│   └── (no ci*.md)
├── LICENSE
├── pyproject.toml
├── README.md
├── requirements-dev.txt
├── requirements.txt
├── SECURITY.md
├── server/
│   ├── config.py
│   ├── demo_parser.py
│   ├── events.py
│   ├── main.py
│   ├── metrics.py
│   ├── state.py
│   ├── worker.py
│   └── ws_server.py
├── scripts/
│   └── ci-local.sh
└── tests/
    ├── conftest.py
    ├── test_client_smoke.py
    ├── test_config.py
    └── test_ws_server.py
```

---

## Validation commands

Run from the repository root.

### Build

No build step (static client + Python runtime). Install dependencies:

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

Or run the full local CI (format, lint, tests, optional pip-audit and gitleaks):

```bash
./scripts/ci-local.sh
```

Optional extras:

```bash
RUN_PIP_AUDIT=1 ./scripts/ci-local.sh
RUN_GITLEAKS=1 ./scripts/ci-local.sh
```

---

## Language and references

- All user-facing documentation is in English and suitable for GitHub.
- References to proprietary or internal tooling (e.g. Codex) have been removed from the archived tree; the issue-audit material is tool-agnostic.
