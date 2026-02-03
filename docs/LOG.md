# LOG

## 2026-02-03
- Iteration 1 (Phase 1): Read-only analysis completed; produced initial findings backlog. Verification: repo inspection only (no tests run). Status: green. Follow-ups: address P1 XSS risk and P2 exposure defaults in Phase 3.
- Iteration 1 (Phase 2): Removed tracked cache/OS artifacts (.pytest_cache/.ruff_cache/.DS_Store/__pycache__). Verification: filesystem cleanup only (no tests run). Status: green. Follow-ups: set up CI/security baselines.
- Iteration 2 (Phase 2): Added GitHub issue/PR templates. Verification: file creation only (no tests run). Status: green. Follow-ups: CI/security baselines and .gitignore review.
- Iteration 3 (Phase 2): Added least-privilege GitHub Actions permissions in CI workflow. Verification: file edit only (no tests run). Status: green. Follow-ups: security baseline tooling.
- Iteration 4 (Phase 2): Added secret scanning workflow (gitleaks) in CI. Verification: file edit only (no tests run). Status: green. Follow-ups: SAST/SCA baselines.
- Iteration 5 (Phase 2): Added CodeQL SAST workflow (Python + JavaScript). Verification: file creation only (no tests run). Status: green. Follow-ups: SCA/dep scan + RUNBOOK updates.
- Iteration 6 (Phase 2): Added dependency scan workflow (pip-audit) and updated RUNBOOK security section. Verification: file edits only (no tests run). Status: green. Follow-ups: CI baseline completion and .gitignore review.
- Iteration 7 (Phase 2): Added dependabot config for pip dependencies. Verification: file creation only (no tests run). Status: green. Follow-ups: Phase 2 exit check, then Phase 3 remediation.
- Iteration 1 (Phase 3): Removed `innerHTML` usage in client rendering to mitigate XSS, added smoke test for `innerHTML` absence. Verification: `pytest -q` (pass). Status: green. Follow-ups: P2 bind host defaults.
- Iteration 2 (Phase 3): Default bind hosts changed to `127.0.0.1` for WebSocket/metrics with CLI/config/env overrides; tests added. Verification: `pytest -q` (pass). Status: green. Follow-ups: P2 demo file race handling.
- Iteration 3 (Phase 3): Guarded demo list stat calls against races; added tests for missing file stat failures. Verification: `pytest -q` (pass). Status: green. Follow-ups: Phase 3 next highest P3/P2 items (README tree, UI language consistency).
- Iteration 4 (Phase 3): README repo layout corrected (removed stale `demoparser-main/`). Verification: file edit only (no tests run). Status: green. Follow-ups: UI language consistency.
- Iteration 5 (Phase 3): Normalized UI strings to English for consistency. Verification: file edits only (no tests run). Status: green. Follow-ups: Phase 3 exit review / remaining P3 items.
- Iteration 1 (Phase 4): Expanded README (requirements, security, troubleshooting, bind host defaults), added DECISIONS.md, and added SECURITY.md/CONTRIBUTING.md. Verification: file edits only (no tests run). Status: green. Follow-ups: Phase 4 exit review.
- Iteration 2 (Phase 5): Removed `maps/` from repo for licensing, updated `.gitignore` and docs to mark maps as local-only. Verification: file edits only (no tests run). Status: green. Follow-ups: re-run tests/lint if desired.
