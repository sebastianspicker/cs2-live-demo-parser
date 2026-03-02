# Code Inspection Findings (Appended)

## 1. Potential errors and security risks

### 1a. Potential errors
- **client/js/msgpack.js `readUint8()`**: When `offset >= bytes.length`, `bytes[offset++]` returns `undefined`. Decoder logic then uses that value (e.g. `byte <= 0x7f`) and can fall through to wrong branches or cause other read functions to read past the buffer, leading to undefined behaviour or exceptions. Malformed or truncated payloads can trigger this.
- **client/js/app.js `applyStateFromMessage`**: The code sets `this.mode = message.mode` whenever `message.mode` is truthy. If the server or a MITM ever sends a non-string (e.g. number) or an unexpected string, the client state and UI (e.g. `this.mode === "manual"`) can be wrong. Only `"live"` and `"manual"` are valid.
- **server/events.py `_get_new_events`**: Returns a filtered DataFrame that may be a view into `_event_frames`. Callers only call `.to_dict("records")` and iterate, but if any future code mutated the returned DataFrame, it could affect the cached frames. Defensive copy avoids that.

### 1b. Security risks
- No new critical security issues identified in this pass (path traversal, map sanitization, MessagePack bounds, and auth are already addressed).

## 2. Suspicious areas and why

| Area | Why suspicious |
|------|----------------|
| msgpack `readUint8()` | No check that `offset < bytes.length`; reading past end yields `undefined` and breaks decoder assumptions. |
| `applyStateFromMessage` mode | Assigns `message.mode` without validating it is `"live"` or `"manual"`. |
| `_get_new_events` return | Returns a possibly shared DataFrame; mutation by caller would corrupt cache. |

## 3. Prioritisation
- **P2**: readUint8 past end (truncated/malformed payloads), mode validation (server/MITM sends bad type).
- **P3**: DataFrame copy (defensive; current callers don't mutate).

## 4. Why each problem could occur
- **readUint8**: Truncated WebSocket message or malformed MessagePack leaves decoder with offset at or past buffer end; next read returns `undefined`.
- **mode**: Server bug or malicious message could send `mode: 1` or `mode: "unknown"`; client would store it and playback/UI logic could misbehave.
- **DataFrame**: Pandas filtering often returns a view; returning it to callers is safe only if callers never mutate; a copy is a low-cost safeguard.

## 5. Severity

| ID | Severity | Item |
|----|----------|------|
| 1 | **P2** | msgpack `readUint8()` can read past buffer → undefined, decoder confusion. |
| 2 | **P2** | `applyStateFromMessage` accepts any truthy `message.mode` → invalid client state. |
| 3 | **P3** | `_get_new_events` returns possibly shared DataFrame → risk of cache mutation. |

## 6. Fixes applied
- **P2**: In msgpack.js, guard `readUint8()` so that if `offset >= bytes.length` we throw `RangeError` before reading. **Done.**
- **P2**: In `applyStateFromMessage`, set `this.mode` only when `message.mode === "live"` or `message.mode === "manual"`. **Done.**
- **P3**: In events.py `_get_new_events`, return `events_df.copy()` when returning the DataFrame (so callers don't mutate cached data). **Done.**


---

## Second inspection pass (full codebase)

### 1a. Potential errors (re-check)
- **server/config.py `load_overview_meta`**: If JSON has `"offset"` as a non-dict (e.g. number or list), `"x" not in offset` can raise `TypeError`. Code relied on the surrounding try/except to continue; adding an explicit `isinstance(offset, dict)` check makes the contract clear and avoids exception-driven flow. **P3.**
- No other new error patterns found in server (ws_server, state, events, demo_parser, worker, main, metrics) or client (app.js, events.js, render.js, msgpack.js). Path resolution (`_resolve_demo_path`), message validation (`_validate_message`), `get_metrics` (last_update guarded), and client `handleMessage` / `loadMapImage` (sanitized key) were re-verified.

### 1b. Security risks (re-check)
- No new security issues. Path traversal blocked in `_resolve_demo_path`; map names validated against `MAP_DEFINITIONS`; client map image URLs built from sanitized key only; auth uses `secrets.compare_digest`; worker receives only server-resolved paths.

### 2. Suspicious areas (second pass)
| Area | Why suspicious |
|------|----------------|
| config `load_overview_meta` offset | `data.get("offset", {})` can be non-dict from JSON; `"x" not in offset` then raises. |

### 3. Prioritisation
- **P3**: config offset type check (malformed meta.json5 or hand-edited JSON).

### 4. Why it could occur
- External or hand-edited `meta.json5` / JSON with `"offset": 123` or `"offset": []` causes `offset` to be non-dict; the existing try/except catches it but an explicit type check is clearer and more robust.

### 5. Severity (second pass)
| ID | Severity | Item |
|----|----------|------|
| 4 | **P3** | config.py `load_overview_meta`: require `isinstance(offset, dict)` before using `offset`. |

### 6. Fixes applied (second pass)
- **P3**: In config.py `load_overview_meta`, require `isinstance(offset, dict)` before using `offset` (use `data.get("offset")` and skip if not a dict). **Done.**


---

## Third inspection pass (full codebase)

### 1a. Potential errors (re-check)
- **client/js/app.js `handlePositionUpdate`**: `processEvents(this, message.data.events || [])` assumes `message.data` is always set. If a malformed or legacy `position_update` lacks `data`, `message.data.events` throws `TypeError`. **P3.**
- No other new error patterns found. Config `load_config_value` already guards `bucket` with `isinstance(bucket, dict)`; demo_parser `_compute_demo_metrics` always returns the expected keys; state `build_players` receives rows from `to_dict("records")` (list of dicts); events `refresh` uses `.copy()` return from `_get_new_events`.

### 1b. Security risks (re-check)
- No new security issues identified.

### 2. Suspicious areas (third pass)
| Area | Why suspicious |
|------|----------------|
| `handlePositionUpdate` `message.data.events` | Direct property access on `message.data`; if `data` is missing, throws. |

### 3. Prioritisation
- **P3**: Defensive optional chaining for `message.data` when passing events to `processEvents`.

### 4. Why it could occur
- Malformed WebSocket payload, legacy server version, or proxy altering the message could omit `data`; client would throw before `updateUI` and leave UI stale or break the message loop.

### 5. Severity (third pass)
| ID | Severity | Item |
|----|----------|------|
| 5 | **P3** | app.js `handlePositionUpdate`: use `message.data?.events || []` to avoid TypeError when `data` is missing. |

### 6. Fixes applied (third pass)
- **P3**: In app.js `handlePositionUpdate`, call `processEvents(this, message.data?.events || [])` so missing `message.data` does not throw. **Done.**


---

## Fourth inspection pass (startup, metrics, config types, client DOM)

### 1a. Potential errors (re-check)
- **server/main.py `parse_args`**: `demo_dir_default = server_config.get("demo_dir", repo_root / "demos")` can be a non-string from JSON (e.g. `[]` or `{}`). The code only normalized `None` or blank string; `str([])` would become `"[]"` and `Path("[].").mkdir(exist_ok=True)` would create a literal `[]` directory. **P3.**
- No other new error patterns. main.py `_safe_float`/`_safe_int` handle None and invalid types; metrics handler already catches `get_metrics()` exceptions; client uses `textContent` (XSS-safe) and `message.data?.events` is already guarded; render.js returns early when `!client.gameState`.

### 1b. Security risks (re-check)
- No new security issues. Client DOM updates use `textContent` for server data, not `innerHTML`.

### 2. Suspicious areas (fourth pass)
| Area | Why suspicious |
|------|----------------|
| main.py `demo_dir_default` | Config `demo_dir` from JSON may be non-string; only None/blank were normalized, so list/dict could yield weird path. |

### 3. Prioritisation
- **P3**: Normalise invalid `demo_dir` config type so `--demo-dir` default is always a valid path string.

### 4. Why it could occur
- Hand-edited or generated `config.json` with `"demo_dir": []` or `"demo_dir": {}` leaves `demo_dir_default` as non-string; `str(...)` then produces an invalid default path.

### 5. Severity (fourth pass)
| ID | Severity | Item |
|----|----------|------|
| 6 | **P3** | main.py `parse_args`: ensure `demo_dir_default` is `str` or `Path`, else use `repo_root / "demos"`. |

### 6. Fixes applied (fourth pass)
- **P3**: In main.py `parse_args`, add `elif not isinstance(demo_dir_default, (str, Path)): demo_dir_default = repo_root / "demos"` so invalid config types do not produce a bad default path. **Done.**


---

## Fifth inspection pass (worker process, queues, edge cases)

### 1a. Potential errors (re-check)
- **server/ws_server.py `_poll_worker`**: `response = self.worker_out.get(timeout=2)` is always a dict in normal operation, but if the worker process or queue ever produced a non-dict (e.g. serialisation glitch, future code change), `response.get("update")` would raise `AttributeError`. **P3.**
- No other new error patterns. build_kill_feed receives DataFrame from _get_new_events (copy); compute_elapsed_seconds guards playback_ticks/playback_time; msgpack unsupported bytes return null; client reconnect uses backoff and setTimeout; queue module is imported for queue.Empty.

### 1b. Security risks (re-check)
- No new security issues identified.

### 2. Suspicious areas (fifth pass)
| Area | Why suspicious |
|------|----------------|
| `_poll_worker` `response.get("update")` | Assumes `response` is always a dict; non-dict would raise. |

### 3. Prioritisation
- **P3**: Defensive type check on worker response before calling `.get("update")`.

### 4. Why it could occur
- Multiprocessing queue in theory could return an unexpected type after a crash or serialisation edge case; or a future change to the worker could put a different shape. Guarding avoids `AttributeError` and keeps the parser loop running.

### 5. Severity (fifth pass)
| ID | Severity | Item |
|----|----------|------|
| 7 | **P3** | ws_server `_poll_worker`: ensure `response` is a dict before `response.get("update")`. |

### 6. Fixes applied (fifth pass)
- **P3**: In ws_server.py `_poll_worker`, after `worker_out.get(timeout=2)`, add `if not isinstance(response, dict): return None` before `return response.get("update")`. **Done.**


---

## Sixth inspection pass (localStorage, JSON parse, number display)

### 1a. Potential errors (re-check)
- **client/js/app.js `loadRadarSettings`**: `JSON.parse(raw)` can return `null` when `raw` is the string `"null"`. The code then accesses `parsed.dotSize`, `parsed.bombSize`, etc., which throws `TypeError` (null has no properties). **P3.**
- No other new error patterns. Demo parser `parse_incremental`/ `parse_window` wrap in try/except; client numeric displays use values from message with `|| 0` or are guarded elsewhere; `toFixed` on NaN yields `"NaN"` (no throw). Defensive check for `parsed` after `JSON.parse` avoids the null/primitive case.

### 1b. Security risks (re-check)
- No new security issues. localStorage is same-origin; parsed settings are not inserted as HTML.

### 2. Suspicious areas (sixth pass)
| Area | Why suspicious |
|------|----------------|
| `loadRadarSettings` `parsed` after `JSON.parse` | `parsed` can be `null` or a primitive; property access then throws. |

### 3. Prioritisation
- **P3**: Guard `parsed` so it is a non-null object before reading properties.

### 4. Why it could occur
- User or extension could set `localStorage[cs2_radar_settings] = "null"`; or a bug could store a non-object JSON value. `JSON.parse("null")` returns `null`, causing `parsed.dotSize` to throw.

### 5. Severity (sixth pass)
| ID | Severity | Item |
|----|----------|------|
| 8 | **P3** | app.js `loadRadarSettings`: ensure `parsed` is a non-null object after `JSON.parse` before reading properties. |

### 6. Fixes applied (sixth pass)
- **P3**: In app.js `loadRadarSettings`, after `JSON.parse(raw)` add `if (parsed === null || typeof parsed !== "object") return { ...DEFAULT_RADAR_SETTINGS };` so null or primitive parsed values do not cause `TypeError`. **Done.**

---

## Seventh inspection pass (deep inspection, 2026-03-02)

### 1a. Potential errors

| # | Location | Issue | Why suspicious |
|---|----------|-------|----------------|
| 9 | `server/config.py` | Silent `except Exception: continue/pass` in metadata parsing | Could hide malformed file states and make behavior non-deterministic during troubleshooting. |
| 10 | `server/events.py` | `except Exception: continue` in event extraction loops | Potentially masks parser/data-shape regressions and drops events silently. |
| 11 | `server/state.py` | broad int/float conversion catches | Catch-all exceptions can hide type/data bugs and complicate root-cause analysis. |
| 12 | `server/demo_parser.py` | silent pass/continue in z-range/player parsing | Parsing faults could be silently ignored, making diagnostics harder. |
| 13 | `server/ws_server.py` | multiple `except ...: pass/continue` in auth/send/broadcast/worker stop paths | Swallowing transport or queue failures can keep stale state and hide connection issues. |
| 14 | `pyproject.toml` pytest config | `pytest-asyncio` deprecation warning (`asyncio_default_fixture_loop_scope` unset) | Constant warning noise in test runs and future behavior change risk. |

### 1b. Security risks

- No new P0/P1 remote exploit vectors identified in this pass (demo path traversal protection, schema checks, and auth comparison remain in place).
- Exception swallowing above was treated as **P3 hardening** due operational/security-observability impact.

### 2. Prioritisation by probability

- **P3 (high probability operationally):** silent exception handlers in hot paths (websocket and parser loops) because these paths execute frequently in production.

### 3. Why each problem could occur

- Untrusted/variable input shapes (demo metadata, websocket payloads, event rows) can trigger conversion/parsing errors.
- Silent handlers convert those failures into hidden drops instead of explicit fallback/logging.
- pytest-asyncio warns when loop scope is implicit; relying on defaults may break when plugin defaults change.

### 4. Fixes applied

- Replaced silent `pass/continue` exception bodies with explicit fallbacks and/or guarded control flow.
- Narrowed several conversion catches to `TypeError/ValueError` and converted “except+continue” blocks to “parse-then-check” flow.
- Added diagnostic logging for websocket send/broadcast/worker-stop failures.
- Added pytest config: `[tool.pytest.ini_options]` with `asyncio_default_fixture_loop_scope = "function"`.

### 5. Verification

- `ruff check .`: pass
- `pytest -q`: 15 passed
- `bandit -r server -x tests --severity-level low`: no issues
- `pip-audit -r requirements*.txt`: no known vulnerabilities

### 6. Classification (seventh pass)

- **P0:** none
- **P1:** none
- **P2:** none
- **P3:** resolved (no remaining Bandit low findings in `server/`)

---

## Eighth inspection pass (deep inspection, 2026-03-02)

### 1a. Potential errors

- Re-scanned parser/websocket/config/state paths after seventh-pass hardening.
- No new runtime issues identified.

### 1b. Security risks

- Re-checked auth path, demo-path resolution, message schema validation, and dependency audit outputs.
- No new security issues identified.

### 2. Suspicious areas reviewed

| Area | Why suspicious | Result |
|------|----------------|--------|
| WebSocket auth/broadcast loops | High-frequency network/error handling path | No new defects; current guarded/logged handling remains stable. |
| Demo path resolution | Historical traversal hotspot | Existing traversal controls remain effective. |
| Pytest async loop defaults | Historical warning noise path | Configured; warnings removed. |

### 3. Classification (eighth pass)

- **P0:** none
- **P1:** none
- **P2:** none
- **P3:** none new

### 4. Verification

- `ruff check .`: pass
- `pytest -q`: 15 passed
- `bandit -r server -x tests --severity-level low`: no issues
- `pip-audit -r requirements*.txt`: no known vulnerabilities

---

## Ninth inspection pass (deep inspection, 2026-03-02)

### 1a. Potential errors

| # | Location | Issue | Why suspicious |
|---|----------|-------|----------------|
| 15 | `server/ws_server.py` network bind/auth interaction | Non-loopback bind (`0.0.0.0` etc.) could run without auth by default | Service may be reachable beyond localhost without credential checks if operator changes bind host only. |

### 1b. Security risks

| # | Location | Issue | Why suspicious |
|---|----------|-------|----------------|
| 16 | `server/metrics.py` error responses | Raw exception text returned to clients on metrics serialization failure | May disclose internals/config paths in error responses. |

### 2. Prioritisation by probability

- **P1 (high):** non-loopback binding without auth.
- **P2 (medium):** exception-detail leakage in metrics endpoint.

### 3. Why each problem could occur

- Host binding and auth were configured independently; changing host to non-loopback did not force/auth-gate exposure.
- Metrics handler serialized `{"error": str(exc)}` directly in HTTP 500 path.

### 4. Fixes applied

- Added `config.is_loopback_host()` helper.
- In `ProfessionalBroadcastServer`:
  - if bind host is non-loopback and auth is disabled, auth is now auto-enabled by default.
  - explicit opt-out added via `CS2_ALLOW_INSECURE_PUBLIC_BIND=1` / `server.allow_insecure_public_bind=1`.
- In `main.py`:
  - metrics host is forced to `127.0.0.1` unless explicitly allowed via
    `CS2_ALLOW_PUBLIC_METRICS=1` / `server.allow_public_metrics=1`.
- In `metrics.py`:
  - replaced error body with generic `{"error":"internal_error"}` and server-side logging.
- Added tests:
  - loopback helper variants (`tests/test_config.py`)
  - auth auto-enable and explicit insecure override (`tests/test_ws_server.py`)

### 5. Verification

- `ruff check .`: pass
- `pytest -q`: 18 passed
- `bandit -r server -x tests --severity-level low`: no issues
- `pip-audit -r requirements*.txt`: no known vulnerabilities

### 6. Classification (ninth pass)

- **P0:** none
- **P1:** resolved
- **P2:** resolved
- **P3:** none new

---

## Tenth inspection pass (release-prep verification, 2026-03-02)

### 1a. Potential errors

- Re-ran static and runtime checks after README/CI standardization changes.
- No new runtime defects identified in parser, websocket, client, or config paths.

### 1b. Security risks

- Re-ran dependency and SAST gates (`pip-audit`, `bandit`).
- No new security issues identified.

### 2. Suspicious areas reviewed

| Area | Why suspicious | Result |
|------|----------------|--------|
| Parser and client failure paths | README diagram refactor can drift from implemented behavior | Updated diagrams now include explicit parse-error and reconnect branches that match current code paths. |
| CI parity with local gates | Local gate included Bandit while CI previously did not | CI now runs Bandit in the main workflow. |

### 3. Classification (tenth pass)

- **P0:** none
- **P1:** none
- **P2:** none
- **P3:** none new

### 4. Verification

- `ruff check .`: pass
- `pytest -q`: 18 passed
- `bandit -r server -x tests --severity-level low`: no issues
- `pip-audit -r requirements.txt`: no known vulnerabilities
- `pip-audit -r requirements-dev.txt`: no known vulnerabilities

### 5. Closure

- Final iteration result: **no new P3 findings**.
