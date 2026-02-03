# DECISIONS

## 2026-02-03: Default bind host is localhost
Decision: Default WebSocket and metrics servers bind to `127.0.0.1`.
Reason: Reduce exposure by default while allowing explicit overrides for remote access.
Tradeoffs: Remote access now requires configuration (`--bind-host 0.0.0.0` or config/env).

## 2026-02-03: CI security baselines
Decision: Add secret scanning (gitleaks), SAST (CodeQL), and dependency scanning (pip-audit).
Reason: Establish minimum security gates without heavy tooling changes.
Tradeoffs: Additional CI runtime and reliance on third-party actions (tag-pinned).

## 2026-02-03: Map data excluded from repo
Decision: Exclude `maps/` from version control due to licensing constraints.
Reason: Avoid distributing licensed map assets/metadata in the repository.
Tradeoffs: Users must provide local `maps/` files if they want custom bounds or overlays.
