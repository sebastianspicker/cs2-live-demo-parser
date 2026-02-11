#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Entrypoint for the CS2 Esports Broadcaster server."""

import argparse
import asyncio
from pathlib import Path

from config import load_app_config, load_setting_str
from metrics import start_metrics_server
from ws_server import ProfessionalBroadcastServer


def _safe_float(value, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_args():
    repo_root = Path(__file__).resolve().parents[1]
    app_config = load_app_config()
    server_config = app_config.get("server", {}) if isinstance(app_config, dict) else {}
    default_bind_host = load_setting_str("server", "bind_host", "CS2_BIND_HOST", "127.0.0.1")
    default_metrics_host = load_setting_str(
        "server",
        "metrics_host",
        "CS2_METRICS_HOST",
        default_bind_host,
    )

    poll_default = _safe_float(server_config.get("poll_interval"), 0.8)
    metrics_port_default = _safe_int(server_config.get("metrics_port"), 0)
    parser_exec_default = server_config.get("parser_executor", "none")
    if parser_exec_default not in ("none", "thread", "process"):
        parser_exec_default = "none"

    parser = argparse.ArgumentParser(description="CS2 Esports Broadcaster")
    parser.add_argument(
        "--demo-dir", default=str(server_config.get("demo_dir", repo_root / "demos"))
    )
    parser.add_argument("--poll-interval", type=float, default=poll_default)
    parser.add_argument("--no-msgpack", action="store_true")
    parser.add_argument(
        "--parser-executor",
        choices=["none", "thread", "process"],
        default=parser_exec_default,
    )
    parser.add_argument("--metrics-port", type=int, default=metrics_port_default)
    parser.add_argument("--bind-host", default=default_bind_host)
    parser.add_argument("--metrics-host", default=default_metrics_host)
    return parser.parse_args()


async def main():
    args = parse_args()

    demo_dir = Path(args.demo_dir)
    demo_dir.mkdir(exist_ok=True)

    if not list(demo_dir.glob("*.dem")):
        print("⚠️  No .dem files found yet. Drop a demo into the folder to start parsing.\n")

    server = ProfessionalBroadcastServer(
        demo_dir,
        use_msgpack=not args.no_msgpack,
        poll_interval=args.poll_interval,
        parser_executor=args.parser_executor,
        bind_host=args.bind_host,
    )

    if args.metrics_port > 0:
        start_metrics_server(server, args.metrics_port, args.metrics_host)
        print(f"📈 Metrics available at http://{args.metrics_host}:{args.metrics_port}/metrics")

    try:
        await server.start()
    except KeyboardInterrupt:
        print("\n\n✅ Server shutting down gracefully...")
        server.shutdown()
    except Exception as exc:
        print(f"\n❌ Fatal error: {exc}")
        server.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Server stopped")
    except Exception as exc:
        print(f"\n❌ Fatal error: {exc}")
