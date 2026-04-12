# Security and Anti-Cheat FAQ

## Will I get banned?
The tool reads demo files from disk and does not access game memory or
modify game files. Tournament rules and platform policies still apply.

## Can VAC or FaceIT detect this?
The tool operates as a separate process and only reads `.dem` files. VAC and
FaceIT focus on memory access and tampering of the running game process.

## Is this legal?
Demo files are designed for replay and analysis. This tool only consumes that
data. Always confirm usage rules with event organizers and platform policies.

## Can I use it in tournaments?
Ask the organizer first. Demo analysis is common in esports, but rules vary.

## Does it work with 64-tick and 128-tick demos?
Yes. Both tick rates are supported.

## Bandwidth usage
Typical bandwidth per client:
- LAN: low (hundreds of KB/s for several clients)
- Internet: low (hundreds of KB/s)

## Data privacy
The tool does not upload data or require accounts. Everything runs locally.

## Can it be used for live advantage?
Incremental demo parsing can approach near real-time depending on how the demo
is written and your polling interval. Live mode also auto-tunes the polling
interval when lag is high. This can create competitive risks if demo files are
accessible during live play. See `docs/VALVE_NOTICE.md` for a focused
discussion and latency estimates.

## What does "live lag" mean?
Live lag is the time delta between the demo file timestamp and the current
server timestamp (`_live_lag_sec`). It is not a network ping. A low value means
the demo is being tailed quickly; higher values mean the parser is behind.
