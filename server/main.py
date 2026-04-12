#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Entrypoint for the CS2 Esports Broadcaster server."""

import argparse
import asyncio
from pathlib import Path

from config import is_loopback_host, load_app_config, load_setting_int, load_setting_str
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

    demo_dir_default = server_config.get("demo_dir", repo_root / "demos")
    if demo_dir_default is None or (
        isinstance(demo_dir_default, str) and not demo_dir_default.strip()
    ):
        demo_dir_default = repo_root / "demos"
    elif not isinstance(demo_dir_default, (str, Path)):
        demo_dir_default = repo_root / "demos"

    parser = argparse.ArgumentParser(description="CS2 Esports Broadcaster")
    parser.add_argument("--demo-dir", default=str(demo_dir_default))
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
    allow_public_metrics = (
        load_setting_int(
            "server",
            "allow_public_metrics",
            "CS2_ALLOW_PUBLIC_METRICS",
            0,
        )
        == 1
    )

    demo_dir = Path(args.demo_dir)
    demo_dir.mkdir(exist_ok=True)

    if not list(demo_dir.glob("*.dem")):
        print(f"No .dem files in {demo_dir}/ yet. Drop a demo file there to start parsing.\n")

    server = ProfessionalBroadcastServer(
        demo_dir,
        use_msgpack=not args.no_msgpack,
        poll_interval=args.poll_interval,
        parser_executor=args.parser_executor,
        bind_host=args.bind_host,
    )

    if args.metrics_port > 0:
        if not allow_public_metrics and not is_loopback_host(args.metrics_host):
            print(
                "Security: metrics host is non-loopback but public metrics are "
                "not allowed. Falling back to 127.0.0.1."
            )
            args.metrics_host = "127.0.0.1"
        start_metrics_server(server, args.metrics_port, args.metrics_host)
        print(f"Metrics endpoint: http://{args.metrics_host}:{args.metrics_port}/metrics")

    try:
        await server.start()
    except KeyboardInterrupt:
        print("\nShutting down ...")
        server.shutdown()
    except Exception as exc:
        print(f"\nFatal error: {exc}")
        server.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except Exception as exc:
        print(f"\nFatal error: {exc}")
