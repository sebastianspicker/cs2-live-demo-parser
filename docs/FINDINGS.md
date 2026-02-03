# FINDINGS

Prioritized backlog of issues found in Phase 1 (read-only analysis). Each item includes severity, location, expected vs actual, fix strategy, and verification signal.

## P1
- P1 Security: Client-side XSS via `innerHTML` rendering of demo data (player names, kill feed).
  - Location: `client/js/app.js` (economy list in `updateUI`, kill feed in `updateKillFeed`).
  - Expected vs Actual: Untrusted demo-derived strings should be rendered as text; currently injected into HTML, allowing script/markup injection.
  - Repro: Use a demo with a player name containing HTML (e.g., `<img onerror=...>`), observe DOM injection in kill feed/economy list.
  - Fix strategy: Replace `innerHTML` with DOM creation + `textContent`, or sanitize/escape all user-controlled strings.
  - Verification: Add a unit test that renders with a name containing HTML and asserts no HTML injection; manual UI check with a crafted demo name.
  - Status: Fixed in Phase 3 Iteration 1 (removed `innerHTML`, DOM construction + test).

## P2
- P2 Security/Exposure: WebSocket + metrics bind to `0.0.0.0` without auth/TLS by default.
  - Location: `server/ws_server.py` (`websockets.serve(..., "0.0.0.0", 8765)`), `server/metrics.py` (metrics server binds `0.0.0.0`).
  - Expected vs Actual: Default should be localhost-only or clearly documented with optional bind address; current defaults expose on all interfaces.
  - Fix strategy: Make bind host configurable (env/config/CLI) with secure default `127.0.0.1`, document overrides.
  - Verification: Update tests/config to verify default bind host and successful override.
  - Status: Fixed in Phase 3 Iteration 2 (default bind host set to localhost; CLI/config/env supported; tests added).

- P2 Stability: Demo list refresh can throw on file races (deleted/rotated demos) and disconnect clients.
  - Location: `server/ws_server.py` (`_refresh_demo_list`, `_select_active_demo`).
  - Expected vs Actual: Transient filesystem changes should not crash/tear down client sessions; currently `path.stat()` exceptions can bubble to client handler.
  - Fix strategy: Wrap per-file stat calls in `try/except` and skip missing files; guard max() with non-empty list checks.
  - Verification: Add test that deletes a demo between glob and stat; client loop should continue without exception.
  - Status: Fixed in Phase 3 Iteration 3 (stat guards + tests for missing files).

## P3
- P3 Docs: README repo layout lists `demoparser-main/`, but directory is not present.
  - Location: `README.md` (Repository layout section).
  - Expected vs Actual: README should reflect actual repo contents; current entry is stale.
  - Fix strategy: Update README layout or restore referenced directory (if intended).
  - Verification: README repo tree matches `find` output.
  - Status: Fixed in Phase 3 Iteration 4 (README layout updated).

- P3 Hygiene: Cached/OS files are tracked despite `.gitignore`.
  - Location: `.pytest_cache/`, `.ruff_cache/`, `.DS_Store` (tracked in repo).
  - Expected vs Actual: Cache/OS artifacts should be untracked; currently present in repo history.
  - Fix strategy: Remove tracked cache/OS files; keep `.gitignore` entries.
  - Verification: `git status` clean after removal; caches not re-added.
  - Status: Fixed in Phase 2 Iteration 1 (removed tracked cache/OS files).

- P3 Docs/UX: Status strings mix English + German in UI (e.g., "Demo Auswahl", "Demo waehlen...") without policy.
  - Location: `client/index.html`.
  - Expected vs Actual: Consistent UI language; currently mixed.
  - Fix strategy: Decide on language policy and normalize UI strings.
  - Verification: UI strings consistent with chosen locale.
  - Status: Fixed in Phase 3 Iteration 5 (UI strings normalized to English).
