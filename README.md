# CS2 Live Demo Parser

CS2 demo parser and WebSocket broadcaster for near real-time spectator overlays and match analysis.

Why: Provide low-latency, read-only demo telemetry for overlays without game memory access.

---

> **Small indie company corner** — How Valve “fixed” the issue two weeks after the bug was published on Reddit:
>
> ```
> _record (cheat dontrecord release)
> record (cheat dontrecord release)
> ```
>
> That’s not a bugfix. The bug is still there—they just hid it. Competitive matches: command disabled. Everywhere else: same command, now gated behind `sv_cheats 1`. So instead of fixing the underlying issue, they swept it under the rug and called it a day. Legitimate use cases (e.g. local live radar from `record name` during a match) get broken in the process. Very clever.

---

## Features
- Incremental demo parsing with automatic map detection
- Two modes: Live (tail newest demo file) and Manual (pick demo + playback controls)
- WebSocket streaming for multiple concurrent clients (JSON or MsgPack)
- MsgPack compression stats embedded at a configurable sampling interval
- Browser radar client with grid or overview textures + height layering
- Bomb position marker + bomb carrier indicator
- Map override control and bounds safety warnings when projection is risky
- Live lag tracking with automatic poll tuning down to a configurable floor
- demoparser2 backend from PyPI (friendly props like `X/Y/Z`, `yaw`, `health`)
- Read-only demo analysis (no game memory access)
- Optional map metadata from overview assets (see `maps/` in docs)

## Excluded features
Some functionality is intentionally kept out of this repository and excluded
from version control to reduce the risk of misuse as a cheat. Local-only
features should live under `private/` (and are ignored by `.gitignore`).

## Requirements
Python 3.13 and pip.

## Quick start
1. Create a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

2. Start the server:

```bash
python server/main.py
```

By default, the server binds to `127.0.0.1`. For remote access, pass `--bind-host 0.0.0.0`.

3. Drop demo files into `demos/` (the server creates it on first run).

4. Open the client:
- `client/index.html` (defaults to `ws://localhost:8765`)
- Use the Mode selector to choose Live or Manual.
- Manual mode requires selecting a demo before playback controls unlock.
- Map Override is optional. Use Auto to keep detected maps.

## Development (lint + tests)
Install dev tools and run the offline test suite:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
ruff check .
ruff format .
pytest -q
```

## Validation (build / run / test)
From repo root:

- **Install:** `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt`
- **Run:** `python server/main.py` (then open `client/index.html`)
- **Test:** `ruff format --check . && ruff check . && pytest -q`
- **Full local CI:** `./scripts/ci-local.sh` (optional: `RUN_PIP_AUDIT=1` or `RUN_GITLEAKS=1`)

See `ARCHIVE.md` for the full list of validation commands and archive rationale.

## Security
- Default bind host is `127.0.0.1`. To expose externally, set `--bind-host 0.0.0.0` (or `bind_host` in `config.json`) and consider network-level protections.
- CI includes secret scanning (gitleaks), SAST (CodeQL), and dependency scanning (pip-audit).

## Configuration
- `config.json` (root): server/client/parser settings
- Optional local files (gitignored; see below):
  - `maps/map_definitions.json`: map metadata for UI defaults
  - `maps/world_bounds.json`: world-to-radar bounds

Key server settings (config or env):
- `server.poll_interval` / `CS2_POLL_INTERVAL` (seconds)
- `server.min_poll_interval` / `CS2_MIN_POLL_INTERVAL` (auto-tuning floor)
- `server.msgpack_refresh_interval` / `CS2_MSGPACK_REFRESH_INTERVAL` (metrics sampling)
- `server.bind_host` / `CS2_BIND_HOST` (bind address; default `127.0.0.1`)
- `server.metrics_host` / `CS2_METRICS_HOST` (metrics bind address; default `127.0.0.1`)

UI controls:
- Map override (Auto or specific map)
- Sampling interval for MsgPack compression stats
- Playback controls (play/pause/seek/speed) in Manual mode

## Documentation
- `docs/QUICK_START.md`
- `docs/INSTALLATION.md`
- `docs/PARSER_DOCUMENTATION.md`
- `docs/SECURITY_AND_ANTICHEAT_FAQ.md`
- `docs/VALVE_NOTICE.md` (incremental demo reading risks and latency)
- `docs/RUNBOOK.md` (setup, run, lint, test, troubleshooting)
- `docs/issue-audit/` (read-only code audit template; see `docs/issue-audit/README.md`)
- `ARCHIVE.md` (archive notice, keep/remove/move list, validation commands)
- `SECURITY.md` (security reporting guidance)
- `CONTRIBUTING.md` (development + contribution notes)

## Repository layout
```
.
├── client/                 Browser client
├── server/                 Python WebSocket server
├── demos/                  Demo files (.dem)
├── docs/                   Public documentation
├── scripts/                CI local reproduction (ci-local.sh)
└── tests/                  Pytest suite
```

## Optional local data (gitignored)
- `maps/` (local-only, excluded for licensing). You may provide:
  - `maps/map_definitions.json`
  - `maps/world_bounds.json`
  - `maps/overviews/` – optional overview images and metadata, e.g. `de_*/meta.json5` (see docs; some assets may have separate licenses)

## License
MIT. See `LICENSE`.

## Troubleshooting
- If no demos are detected, place `.dem` files in `demos/` or pass `--demo-dir`.
- If the client cannot connect, ensure the server is running and the WebSocket URL matches host/port.
- If tests fail to import server modules, run from repo root so `tests/conftest.py` can set `sys.path`.
