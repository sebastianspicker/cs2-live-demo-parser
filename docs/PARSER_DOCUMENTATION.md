# Parser Documentation

## Overview
The server incrementally reads a `.dem` file, extracts state updates, and
broadcasts them to connected clients over WebSocket. It supports:
- Live mode: tail the newest demo file as it grows.
- Manual mode: select a demo and control playback (play/pause/seek/speed).

Data flow:
```
Demo file (.dem) -> incremental parser -> game state -> WebSocket clients
```

## Modes and playback
Live mode always follows the newest `.dem` file in `demos/`. Manual mode lets
clients pick a demo from the list and drive playback:
- `play` / `pause` toggles the playback clock.
- `seek` jumps to a specific demo tick.
- `speed` scales playback speed (0.25x to 4.0x).

Live parsing prioritizes low latency. The server tracks live lag and can
auto-tune `poll_interval` down to `min_poll_interval` when lag exceeds 1s.

## demoparser2 props
The server uses demoparser2’s friendly prop names (not raw `m_*` fields).
For tick parsing it requests:
`X`, `Y`, `Z`, `yaw`, `health`, `armor_value`, `team_num`, `life_state`,
`has_helmet`, `balance`.

Event parsing requests player extras `X/Y/Z`, which produce fields like
`user_X`, `user_Y`, `attacker_X`, etc. These are mapped into event payloads
such as bomb positions.

## Map detection
The server detects the map using:
1. Demo filename (preferred)
2. Demo header metadata

If no map is detected, the map name remains unset and the client falls back to
generic rendering.

## Map override and bounds safety
The UI can send a Map Override (Auto or specific map). If an override is set,
the server forces the map name and map config to the selected entry in
`maps/map_definitions.json`. If that entry does not contain bounds or `z_range`,
the server flags `bounds_safe = false` and sends a warning status.

## Map bounds for accurate radar mapping
The server can load fixed world bounds per map from `maps/world_bounds.json` to
improve coordinate-to-radar mapping. If no fixed bounds are provided, it
derives bounds dynamically from player positions observed in the demo.

**Format (this project)**  
We use **bounds-based** metadata: `world_bounds` with `min_x`, `max_x`, `min_y`, `max_y` (world units), plus optional `world_transform` (`flip_x`, `flip_y`, `rotate_deg`) and `z_range`. The client maps world coordinates to screen pixels with: `(x - min_x) / (max_x - min_x) * width` (and similarly for y), then applies transform/rotation.

**Relation to pos_x / pos_y / scale metadata**  
Some parsers use **pos_x, pos_y, scale** (e.g. from VDF): translate with `(x - pos_x, pos_y - y)` then scale by `1/scale` to get pixel coordinates. Our bounds are equivalent to a box: `min_x`, `max_x`, `min_y`, `max_y` define the same region; `scale` would be `(max_x - min_x) / imageWidth`. If you have overview assets that only provide pos_x/pos_y/scale, you can convert: e.g. `min_x = pos_x`, `max_x = pos_x + scale * imageWidth`, and similarly for y (accounting for y-flip if needed).

Environment override:
- `CS2_MAP_BOUNDS_FILE` (defaults to `maps/world_bounds.json`)
- `CS2_OVERVIEW_DIR` (defaults to `maps/overviews`)
- `CS2_OVERVIEW_META_DIR` (defaults to `maps/overviews`; directory for `de_*/meta.json5` metadata)
- `CS2_MAP_DEFINITIONS_FILE` (defaults to `maps/map_definitions.json`)

Map metadata defaults live in `maps/map_definitions.json`.

## Optional map metadata (meta.json5)
The overview directory (default `maps/overviews/`) may contain per-map metadata in
`de_*/meta.json5` files. If you use third-party assets there, check their license
and any local LICENSE or README in that directory.

The parser can derive `world_bounds` from such `meta.json5` by reading
`resolution` and `offset`. This is used when `maps/world_bounds.json` does not
define a map.

If `zRange` is available in the metadata, it is exposed as `z_range` and
used by the client to scale player dots by height (useful for Nuke/Vertigo).

## Update loop
- Parses a moving tick window (`tick_window`) from the demo
- Tracks players, bomb status, round info, and events
- Emits state updates at the configured poll interval

## Parsing strategy, update interval, and latency

**Incremental parsing (this project)**  
The server only parses **new ticks** since the last run: it advances a tick window (`parse_ticks(start_tick, tick_window)`) and sends the latest game state. It does **not** re-parse the entire demo on each update. This keeps CPU and I/O low and scales well for long-running live recordings.

**Alternative: full-demo parse per update**  
Some reference implementations (e.g. Go-based live radars) re-open the demo and call a “parse to end” on every file change. That gives a single, consistent “last frame” but becomes expensive as the file grows. We keep incremental parsing as the default.

**Poll interval and latency**  
- Server: `--poll-interval` (default `0.8` s) is how often the parser checks the demo file and emits updates. Lower values (e.g. `0.1`–`0.2`) reduce latency but increase CPU. The server can auto-tune down to `CS2_MIN_POLL_INTERVAL` (default `0.2`) when live lag is high.
- Client: Updates are pushed over WebSocket as soon as the server produces them; no client polling.
- End-to-end latency is roughly: file write delay + poll interval + parse time + network. For low-latency LAN use, consider `--poll-interval 0.2` (or lower if the machine can keep up).

## WebSocket message format
Clients receive JSON or MsgPack payloads. MsgPack uses the same fields as JSON.

Message types:
- `connection`: welcome payload with current mode, demo list, and config flags.
- `demo_list`: updated demo list on change or request.
- `state`: mode/selection changes and flags like `demo_valid` or `bounds_safe`.
- `status`: transient or sticky banner messages.
- `position_update`: the main stream payload.

Example `position_update` payload (abridged):
```json
{
  "type": "position_update",
  "map": "Mirage",
  "map_config": {
    "world_bounds": {
      "min_x": -3230,
      "max_x": 1946,
      "min_y": -1471,
      "max_y": 3705
    },
    "z_range": { "min": -200, "max": 400 }
  },
  "data": {
    "tick": 1234,
    "time": 321.2,
    "round": 5,
    "ct_score": 2,
    "t_score": 3,
    "money": { "ct": 6400, "t": 7200 },
    "alive_ct": 4,
    "alive_t": 5,
    "players": [
      {
        "id": 1,
        "name": "Player1",
        "team": "CT",
        "x": 100.5,
        "y": 200.3,
        "z": 64.0,
        "yaw": 90,
        "health": 100,
        "armor": 100,
        "is_alive": true
      }
    ],
    "bomb": {
      "planted": false,
      "position": { "x": 150.0, "y": 220.0, "z": 0.0 },
      "planter": "Player2"
    },
    "kill_feed": [
      {
        "killer": "Player1",
        "victim": "Player2",
        "weapon": "M4A1",
        "headshot": true
      }
    ],
    "events": [
      { "type": "player_death", "tick": 1234 },
      { "type": "bomb_planted", "tick": 1200 }
    ],
    "bomb_planted": false
  },
  "_server_ts": 1699999999.12,
  "_file_mtime": 1699999999.12,
  "_live_lag_sec": 0.42,
  "_poll_interval": 0.8,
  "_demo_time": 321.2,
  "_demo_tick_rate": 64.0,
  "_demo_remaining": 240.0,
  "_demo_data_rate_bps": 50213.5
}
```

## Configuration
Config file:
- `config.json` (root) with `server`, `client`, and `parser` sections. Override with `CS2_CONFIG_FILE`.

Environment overrides:
- `CS2_TICK_WINDOW` (default `256`)
- `CS2_TICK_WINDOW_MIN` (default `256`)
- `CS2_TICK_WINDOW_MAX` (default `2048`)
- `CS2_EVENT_PARSE_INTERVAL` (default `2.0`)
- `CS2_MAP_BOUNDS_FILE` (default `maps/world_bounds.json`)
- `CS2_OVERVIEW_DIR` (default `maps/overviews`)
- `CS2_MAP_DEFINITIONS_FILE` (default `maps/map_definitions.json`)
- `CS2_MIN_POLL_INTERVAL` (default `0.2`)
- `CS2_MSGPACK_REFRESH_INTERVAL` (default `10`)

CLI overrides:
- `--demo-dir`
- `--poll-interval`
- `--no-msgpack`
- `--parser-executor` (`none`, `thread`, `process`)

## Metrics endpoint
Run the server with `--metrics-port` to expose basic JSON stats:
```
python server/main.py --metrics-port 8766
```
Endpoint: `http://localhost:8766/metrics`

## Future work: dropped items (weapons, defuse kits on map)

We do **not** currently show dropped weapons or defuse kits on the radar. Parsers that do use a full game-state API (e.g. iterate all weapons, filter by no owner, read entity positions). Our stack uses **demoparser2** with tick-based entity properties (player-centric); it does not expose a ready-made “all weapons without owner” list. Adding dropped items would require either:

- A separate entity/prop pass in demoparser2 (if it can return weapon entities and owner handles per tick), or  
- A different or additional library that provides game-state-style access.

The client already has settings “Show kits on map” and “Show weapons on map” so that when server-side support is added, the UI can toggle them without further changes.
