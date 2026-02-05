# Quick Start

## Prerequisites
- Python 3.8+
- A CS2 demo file (`.dem`)

## Run the server
```bash
pip install -r requirements.txt
python server/main.py
```
`requirements.txt` installs demoparser2 from PyPI (no local build needed).

Optional metrics:
```bash
python server/main.py --metrics-port 8766
```

The server listens on `ws://0.0.0.0:8765`.

Optional config:
- `config.json` (root) for server/client/parser settings
- `maps/map_definitions.json` for map metadata
- `maps/world_bounds.json` for world-to-radar bounds

## Add demo files
Place demo files in `demos/`. The map is detected from the filename or demo header.

Examples:
- `demo_mirage.dem`
- `match_dust2.dem`
- `scrim_nuke.dem`

Live mode will always follow the newest file in this folder. Manual mode lets
you select a specific demo and use playback controls.

## Open the client
Open `client/index.html` in your browser. The client defaults to
`ws://localhost:8765` and can be overridden with `?ws=ws://host:8765`.

Example:
```
file:///.../client/index.html?ws=ws://127.0.0.1:8765
```

## First steps in the UI
1. Choose a Mode:
   - Live: auto-selects the newest demo file and keeps tailing it.
   - Manual: pick a demo and use play/pause/seek/speed.
2. Optional: set a Map Override if detection is wrong.
3. Optional: adjust the MsgPack sampling interval (controls how often size stats refresh).
4. Watch the demo status and bounds safety badges for parsing readiness.
