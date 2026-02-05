# Valve Notice: Incremental Demo Reading Risk

This repository demonstrates that CS2 `.dem` files can be read incrementally
while they are still being written. That capability enables near real-time
state reconstruction without accessing game memory or using GSI. It is useful
for broadcast tooling, but it also creates a potential abuse path if live demo
files are accessible during active matches.

## Summary of the risk
- A growing demo file can be parsed continuously to extract player positions,
  events, and round state.
- If a live demo is exposed to untrusted parties, it can be used as a de‑facto
  low‑latency radar.
- The tool in this repo is read‑only and does not modify the game client, but
  the data alone can provide an unfair competitive advantage.

## Latency estimate (practical range)
Latency depends on demo writing cadence, disk flush behavior, and polling.
With default settings (`poll_interval = 0.8s`, `tick_window = 256`):
- Typical end‑to‑end delay: ~0.8–1.6 seconds.
- Event-heavy scenes can add ~0.2–0.5 seconds of parsing overhead.

With aggressive tuning (`poll_interval = 0.2–0.4s`) and fast storage:
- Best‑case delay can approach ~0.3–0.8 seconds.

These figures are observational estimates from the architecture. Real latency
varies by machine, demo size, and server tick rate.

Live mode also tracks `_live_lag_sec` and can auto-tune the poll interval down
to `min_poll_interval` when lag exceeds 1s. This helps the parser catch up but
does not guarantee a fixed latency target on slower disks or very large demos.

## Why this matters
Even sub‑second delays can be enough to influence decision‑making in high‑level
play. If live demos are accessible (e.g., shared network paths, open HTTP
endpoints, or observer machines with broad file access), they can be exploited.

## Suggested mitigations
- Do not expose live demo files to untrusted users or networks.
- Restrict filesystem access on observer/broadcast machines.
- Delay or buffer demo writing when competitive integrity is required.
- Consider server‑side safeguards if live demos are distributed automatically.

This notice is provided to support responsible use and to highlight the need
for access controls around live demo files.
