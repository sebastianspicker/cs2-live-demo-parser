# REPO_MAP

## Top-Level Layout
- `client/` - Browser UI (HTML/CSS/JS). Connects to WebSocket server and renders radar.
- `server/` - Python server, demo parsing, WebSocket broadcasting, metrics, worker process.
- `tests/` - Pytest suite; adds `server/` to `sys.path` for imports.
- `docs/` - User documentation.
- `maps/` - Local-only map metadata (gitignored due to licensing).
- `demos/` - Demo files (.dem); empty by default.
- `config.json` - Runtime configuration (server/parser/client settings).

## Entry Points
- `server/main.py` - CLI entrypoint that starts the WebSocket server and optional metrics server.
- `client/index.html` - Browser client entrypoint.

## Core Modules (Server)
- `server/ws_server.py` - WebSocket server, client lifecycle, polling loop, update broadcasting.
- `server/demo_parser.py` - Demo parsing wrapper around `demoparser2`, map detection, bounds, payload assembly.
- `server/events.py` - Event parsing and kill feed construction.
- `server/state.py` - Player state normalization, economy calculations, helper utilities.
- `server/worker.py` - Optional multiprocessing worker for parsing.
- `server/metrics.py` - Simple JSON metrics endpoint.
- `server/config.py` - Config/env loading and map defaults.

## Client Flow
- `client/index.html` loads JS and CSS.
- `client/js/app.js` connects to `ws://localhost:8765`, processes `connection`, `position_update`, and `state` messages.
- `client/js/render.js` renders radar state (players, bomb, overlays).

## Data / Config
- `config.json` - Default settings (poll interval, parser limits, UI defaults).
- `maps/map_definitions.json` - Optional local map metadata (gitignored).
- `maps/world_bounds.json` - Optional local world bounds (gitignored).
- `maps/boltobserv/` - Optional upstream metadata (GPL-3.0, local-only).

## Tests
- `tests/test_config.py` - Config parsing, JSON5 strip, boltobserv parsing.
- `tests/test_ws_server.py` - Demo path validation, header validation, ordering, msgpack size handling.
- `tests/test_client_smoke.py` - Client HTML/JS sanity checks.

## Hot Spots / Risk Areas
- `server/ws_server.py` - Concurrency (async + threads), client management, update throttling.
- `server/demo_parser.py` - Parsing window, bounds logic, map detection, event parsing.
- `server/events.py` - Event extraction and stateful caches.
