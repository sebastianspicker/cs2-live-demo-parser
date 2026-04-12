import asyncio
import json
import secrets
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import queue
from typing import Optional
from urllib.parse import parse_qs, urlparse

import msgpack

from config import (
    MAP_DEFINITIONS,
    is_loopback_host,
    load_setting_float,
    load_setting_int,
    load_setting_str,
)
from demo_parser import AdvancedDemoParser
from worker import start_worker


def _generate_api_key() -> str:
    """Generate a secure random API key."""
    return secrets.token_hex(16)


class ProfessionalBroadcastServer:
    def __init__(
        self,
        demo_dir: str,
        use_msgpack: bool = True,
        poll_interval: float = 0.8,
        parser_executor: str = "none",
        bind_host: str = "127.0.0.1",
    ):
        self.demo_dir = Path(demo_dir)
        self.use_msgpack = use_msgpack
        self.poll_interval = poll_interval
        self.parser_executor = parser_executor
        self.bind_host = bind_host
        self.executor = None
        self.worker_process = None
        self.worker_in = None
        self.worker_out = None
        self.worker_restart_at = 0.0
        self.worker_backoff = 1.0
        self.start_time = time.time()
        self.parse_mode = "live"
        self.selected_demo = None
        self.demo_list = []
        self.demo_list_version = 0
        self.demo_list_lock = threading.Lock()
        self.status_lock = threading.Lock()
        self.status_version = 0
        self.status_payload = {"type": "status", "message": "", "level": "info", "expires_in": 0}

        # Authentication
        self.api_key = load_setting_str("server", "api_key", "CS2_API_KEY", "")
        self.require_auth = load_setting_int("server", "require_auth", "CS2_REQUIRE_AUTH", 0) == 1
        self.allow_insecure_public_bind = (
            load_setting_int(
                "server",
                "allow_insecure_public_bind",
                "CS2_ALLOW_INSECURE_PUBLIC_BIND",
                0,
            )
            == 1
        )
        if not self.require_auth and not is_loopback_host(self.bind_host):
            if self.allow_insecure_public_bind:
                print(
                    "WARN: Insecure public bind allowed without auth "
                    "(CS2_ALLOW_INSECURE_PUBLIC_BIND=1)."
                )
            else:
                print(
                    "Security: non-loopback bind detected; "
                    "enabling authentication automatically."
                )
                self.require_auth = True
        # If auth is required but no key is configured, generate one
        if self.require_auth and not self.api_key:
            self.api_key = _generate_api_key()
            print(f"Auth: generated API key: {self.api_key}")
        elif self.api_key and not self.require_auth:
            print("Auth: API key configured but auth not required (set CS2_REQUIRE_AUTH=1 to enable)")

        # Server state
        self.state_lock = threading.Lock()
        self.clients = set()
        self.client_count = 0
        self.is_running = True

        # Parser state
        self.parser = None
        self.current_demo = None
        self.last_update = None

        # Phase 3: Update queue
        self.update_queue = deque(maxlen=100)

        # Metrics
        self.compression_stats = {"total": 0, "compressed": 0}
        self.parse_times = deque(maxlen=100)
        self.client_count_history = deque(maxlen=100)
        self.playback_playing = False
        self.playback_speed = 1.0
        self.playback_tick = 0.0
        self.last_msg_bytes = 0
        self.last_compression_rate = 0.0
        self.pack_count = 0
        self.live_latency_warning = False
        self.map_override = None
        self.demo_valid = False
        self.demo_loading = False
        self.base_poll_interval = poll_interval
        self.min_poll_interval = load_setting_float(
            "server",
            "min_poll_interval",
            "CS2_MIN_POLL_INTERVAL",
            0.2,
        )
        self.lag_streak = 0
        self.good_streak = 0
        self.bounds_safe = True
        self.msgpack_refresh_interval = load_setting_int(
            "server",
            "msgpack_refresh_interval",
            "CS2_MSGPACK_REFRESH_INTERVAL",
            10,
        )
        self.bind_port = load_setting_int(
            "server",
            "bind_port",
            "CS2_WS_PORT",
            8765,
        )
        self.loop = None

        if self.parser_executor == "thread":
            self.executor = ThreadPoolExecutor(max_workers=1)
        elif self.parser_executor == "process":
            self._start_worker()

        self._print_banner()

    def _print_banner(self):
        print("\n" + "=" * 60)
        print("  CS2 Live Demo Parser")
        print("=" * 60)
        print(f"  Demo folder : {self.demo_dir}")
        print(f"  WebSocket   : ws://{self.bind_host}:{self.bind_port}")
        print(f"  Encoding    : {'MsgPack' if self.use_msgpack else 'JSON'}")
        print(f"  Poll interval: {self.poll_interval}s (min {self.min_poll_interval}s)")
        print(f"  Executor    : {self.parser_executor}")
        print("=" * 60)
        print("  Open client/index.html in a browser to view the radar.")
        print("=" * 60 + "\n")

    async def start(self):
        try:
            import websockets
        except ImportError as exc:
            print(f"ERROR: Missing dependency: {exc}. Run 'pip install -r requirements.txt' and retry.")
            return
        self.loop = asyncio.get_running_loop()
        parser_thread = threading.Thread(target=self._parser_loop, daemon=True)
        parser_thread.start()

        print(f"Starting WebSocket server on {self.bind_host}:{self.bind_port} ...")
        try:
            async with websockets.serve(
                self.handle_client, self.bind_host, self.bind_port, ping_interval=20
            ):
                print(f"Server ready at ws://{self.bind_host}:{self.bind_port}")
                if self.require_auth:
                    print("Authentication required (pass API key via ?key= query parameter)")
                print("Waiting for clients ...\n")
                await asyncio.Future()
        except OSError as exc:
            print(f"ERROR: Could not start server: {exc}")
            self.is_running = False
            return

    def _validate_auth(self, websocket, path: str) -> bool:
        """Validate client authentication. Returns True if auth is valid or not required."""
        if not self.require_auth:
            return True
        # Check for API key in query string
        parsed = urlparse(path if path.startswith("ws") else f"ws://localhost{path}")
        query_params = parse_qs(parsed.query)
        provided_key = query_params.get("key", [None])[0]
        if provided_key and secrets.compare_digest(provided_key, self.api_key):
            return True
        # Also check for Authorization header (for clients that support it)
        # Note: websocket.request_headers may be available depending on the library version
        try:
            auth_header = getattr(websocket, "request_headers", {}).get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                if secrets.compare_digest(token, self.api_key):
                    return True
        except Exception:
            return False
        return False

    async def handle_client(self, websocket, path):
        client_id = id(websocket)

        # Authentication check
        if not self._validate_auth(websocket, path):
            print(f"Rejected unauthorized connection (client {client_id})")
            try:
                await websocket.send(json.dumps({"type": "error", "message": "Unauthorized"}))
            except Exception as exc:
                print(f"WARN: Could not send auth-rejected message to client {client_id}: {exc}")
            await websocket.close(code=4001, reason="Unauthorized")
            return

        with self.state_lock:
            self.clients.add(websocket)
            self.client_count = len(self.clients)
        last_status_version = 0
        last_demo_list_version = 0
        receiver_task = asyncio.create_task(self._client_receiver(websocket))

        print(f"Client connected (ID: {client_id}). Total clients: {self.client_count}")

        try:
            self._refresh_demo_list()
            demo_list, demo_list_version = self._get_demo_list_snapshot()
            await websocket.send(
                json.dumps(
                    {
                        "type": "connection",
                        "message": "Connected to CS2 Esports Broadcaster",
                        "version": "v8.0",
                        "client_id": client_id,
                        "maps_available": list(MAP_DEFINITIONS.keys()),
                        "timestamp": datetime.now().isoformat(),
                        "mode": self.parse_mode,
                        "selected_demo": self.selected_demo,
                        "demos": demo_list,
                        "msgpack_refresh_interval": self.msgpack_refresh_interval,
                        "map_override": self.map_override,
                        "demo_valid": self.demo_valid,
                        "demo_loading": self.demo_loading,
                        "bounds_safe": self.bounds_safe,
                    }
                )
            )
            last_demo_list_version = demo_list_version

            for update in list(self.update_queue)[-10:]:
                try:
                    await self._send_update(websocket, update)
                except Exception as exc:
                    print(f"WARN: Failed to send queued update to client {client_id}: {exc}")
                    break

            while True:
                try:
                    status_payload, status_version = self._get_status_snapshot()
                    if status_version != last_status_version:
                        await self._send_status(websocket, status_payload)
                        last_status_version = status_version
                    demo_list, demo_list_version = self._get_demo_list_snapshot()
                    if demo_list_version != last_demo_list_version:
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "demo_list",
                                    "demos": demo_list,
                                    "mode": self.parse_mode,
                                    "selected_demo": self.selected_demo,
                                }
                            )
                        )
                        last_demo_list_version = demo_list_version
                    await asyncio.wait_for(asyncio.sleep(self.poll_interval), timeout=5)
                    if self.last_update:
                        await self._send_update(websocket, self.last_update)
                except asyncio.TimeoutError:
                    try:
                        pong = await websocket.ping()
                        await asyncio.wait_for(pong, timeout=10)
                    except Exception:
                        break
                except Exception as exc:
                    print(f"Client loop error (ID: {client_id}): {exc}")
                    break

        except Exception as exc:
            print(f"Error with client {client_id}: {exc}")

        finally:
            if receiver_task:
                receiver_task.cancel()
            with self.state_lock:
                self.clients.discard(websocket)
                self.client_count = len(self.clients)
            print(f"Client disconnected (ID: {client_id}). Total clients: {self.client_count}")

    async def _send_update(self, websocket, update):
        try:
            if self.use_msgpack and isinstance(update, dict):
                try:
                    binary_payload, json_size, compressed_size, payload = self._pack_update(update)
                    self.compression_stats["total"] += json_size
                    self.compression_stats["compressed"] += compressed_size
                    await websocket.send(binary_payload)
                except Exception as pack_exc:
                    print(f"MsgPack encode failed, falling back to JSON: {pack_exc}")
                    await websocket.send(json.dumps(update))
            else:
                await websocket.send(json.dumps(update))
        except Exception as exc:
            print(f"Send error (client {id(websocket)}): {exc}")

    async def _send_status(self, websocket, payload):
        try:
            await websocket.send(json.dumps(payload))
        except Exception as exc:
            print(f"Failed to send status to client {id(websocket)}: {exc}")

    def _pack_update(self, update):
        payload = dict(update)
        if self.map_override:
            override = MAP_DEFINITIONS.get(self.map_override)
            if override:
                merged = dict(override)
                current_map = payload.get("map")
                current_config = payload.get("map_config") or {}
                if current_map == self.map_override and isinstance(current_config, dict):
                    for key in ("world_bounds", "world_transform", "z_range"):
                        if key in current_config:
                            merged[key] = current_config[key]
                payload["map"] = self.map_override
                payload["map_config"] = merged
                if not merged.get("world_bounds") and not merged.get("z_range"):
                    self._set_status(
                        "Map override active but no bounds found; projection may be inaccurate.",
                        level="warning",
                        sticky=True,
                    )
                    self._set_bounds_safe(False)
                else:
                    self._set_bounds_safe(True)
        payload["_compression_rate"] = round(self.last_compression_rate, 1)
        payload["_msg_bytes"] = int(self.last_msg_bytes)
        json_size = len(json.dumps(payload))
        binary_payload = msgpack.packb(payload)
        size = len(binary_payload)
        # Safe compression rate calculation with bounds checking
        compression_rate = 0.0
        if json_size > 0 and size >= 0:
            compression_rate = max(0.0, min(100.0, (1 - size / json_size) * 100))
        self.pack_count += 1
        interval = max(1, int(self.msgpack_refresh_interval or 1))
        should_refresh = self.pack_count % interval == 0
        if should_refresh:
            payload["_msg_bytes"] = size
            payload["_compression_rate"] = round(compression_rate, 1)
            binary_payload = msgpack.packb(payload)
            size = len(binary_payload)
            # Recalculate with same safety bounds
            compression_rate = 0.0
            if json_size > 0 and size >= 0:
                compression_rate = max(0.0, min(100.0, (1 - size / json_size) * 100))
        self.last_msg_bytes = size
        self.last_compression_rate = compression_rate
        return binary_payload, json_size, len(binary_payload), payload

    # Schema validation for WebSocket messages
    _MESSAGE_SCHEMAS = {
        "set_mode": {"mode": (str,)},
        "select_demo": {"name": (str,)},
        "playback": {"action": (str,)},
        "set_sampling": {"interval": (int, float)},
        "set_map_override": {"map": (str, type(None))},
        "request_demos": {},  # No required fields
    }

    def _validate_message(self, data: dict) -> Optional[str]:
        """Validate incoming WebSocket message. Returns message type if valid, None otherwise."""
        if not isinstance(data, dict):
            return None
        msg_type = data.get("type")
        if not isinstance(msg_type, str):
            return None
        schema = self._MESSAGE_SCHEMAS.get(msg_type)
        if schema is None:
            return None  # Unknown message type
        for field, expected_types in schema.items():
            value = data.get(field)
            # Allow None only if type(None) is in expected_types (e.g. set_map_override map)
            if value is None:
                if type(None) not in expected_types:
                    return None  # Missing required field
                continue
            if not isinstance(value, expected_types):
                return None  # Wrong type
        return msg_type

    async def _client_receiver(self, websocket):
        try:
            async for raw in websocket:
                data = None
                try:
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", errors="ignore")
                    data = json.loads(raw)
                except (TypeError, ValueError, json.JSONDecodeError):
                    data = None
                if data is None:
                    continue
                # Validate message schema
                msg_type = self._validate_message(data)
                if not msg_type:
                    continue  # Invalid message, ignore
                if msg_type == "set_mode":
                    mode = data.get("mode")
                    if isinstance(mode, str) and mode in {"live", "manual"}:
                        self._set_mode(mode)
                elif msg_type == "select_demo":
                    name = data.get("name")
                    if isinstance(name, str):
                        self._select_demo(name)
                elif msg_type == "playback":
                    self._handle_playback(data)
                elif msg_type == "set_sampling":
                    interval = data.get("interval")
                    if isinstance(interval, (int, float)):
                        self._set_sampling_interval(interval)
                elif msg_type == "set_map_override":
                    map_name = data.get("map")
                    if map_name is None or isinstance(map_name, str):
                        self._set_map_override(map_name)
                elif msg_type == "request_demos":
                    demo_list, _ = self._get_demo_list_snapshot()
                    try:
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "demo_list",
                                    "demos": demo_list,
                                    "mode": self.parse_mode,
                                    "selected_demo": self.selected_demo,
                                }
                            )
                        )
                    except Exception as exc:
                        print(f"WARN: Failed to send demo list to client: {exc}")
        except Exception as exc:
            print(f"Client receiver closed: {exc}")

    def _parser_loop(self):
        print("Parser thread started.\n")

        while self.is_running:
            try:
                if self.parser_executor == "process" and not self.worker_process:
                    now = time.time()
                    if now >= self.worker_restart_at:
                        self._start_worker()

                self._refresh_demo_list()
                self._select_active_demo()
                update = self._poll_parser()
                if update:
                    update["_poll_interval"] = self.poll_interval
                    self.last_update = update
                    self.parse_times.append(update.get("_parse_ms", 0))
                    self.update_queue.append(update)
                    self._log_metrics(update)
                    self._update_live_latency_status(update)
                    self._auto_tune_poll_interval(update)
                elif self.parser and not self.parser.demo_path.exists():
                    self._set_status(
                        "Demo file missing. Waiting for a valid demo.", level="warning", sticky=True
                    )
                    self.parser = None
                    self.current_demo = None
                    self._set_demo_valid(False)
                    self._set_demo_loading(False)

                time.sleep(self.poll_interval)

            except Exception as exc:
                print(f"Parser error: {exc}")
                time.sleep(1)

    def _select_active_demo(self) -> None:
        if not self.demo_dir.exists():
            return
        if self.parse_mode == "manual":
            if not self.selected_demo:
                self._set_status(
                    "Manual mode: select a demo to start parsing.", level="info", sticky=True
                )
                self._set_demo_valid(False)
                self._set_demo_loading(False)
                return
            demo_path = self._resolve_demo_path(self.selected_demo)
            if not demo_path:
                self._set_status(
                    "Selected demo not found. Pick another demo.", level="error", sticky=True
                )
                self._set_demo_valid(False)
                self._set_demo_loading(False)
                return
            if not self._is_valid_demo(demo_path):
                self._set_status(
                    "Selected demo is invalid. Pick another demo.", level="error", sticky=True
                )
                self._set_demo_valid(False)
                self._set_demo_loading(False)
                return
            if self.current_demo == str(demo_path):
                return
            self._load_demo(demo_path)
            return

        demo_candidates = []
        for path in self.demo_dir.glob("*.dem"):
            try:
                stat = path.stat()
            except OSError:
                continue
            demo_candidates.append((stat.st_mtime, path))
        if not demo_candidates:
            self._set_status(
                "No demos found. Add a .dem file to start parsing.", level="warning", sticky=True
            )
            self._set_demo_valid(False)
            self._set_demo_loading(False)
            return
        latest_demo = max(demo_candidates, key=lambda item: item[0])[1]
        if not self._is_valid_demo(latest_demo):
            self._set_status(
                "Latest demo is invalid. Waiting for a valid demo.", level="warning", sticky=True
            )
            self._set_demo_valid(False)
            self._set_demo_loading(False)
            return
        if self.current_demo == str(latest_demo):
            return
        self._load_demo(latest_demo)

    def _load_demo(self, demo_path: Path) -> None:
        self.current_demo = str(demo_path)
        self._set_status("", level="info", sticky=False)
        self.playback_tick = 0.0
        self.playback_playing = False
        print(f"Loading demo: {demo_path.name}")
        self._set_demo_loading(True)
        self.parser = AdvancedDemoParser(demo_path)
        if self.worker_in:
            try:
                self.worker_in.put({"cmd": "set_demo", "path": str(demo_path)})
                self.worker_out.get(timeout=2)
                self._set_demo_valid(True)
                self._set_demo_loading(False)
            except Exception as exc:
                print(f"Worker init failed: {exc}")
                self._stop_worker()
                self._set_demo_valid(False)
                self._set_demo_loading(False)
        else:
            self._set_demo_valid(True)
            self._set_demo_loading(False)

    def _resolve_demo_path(self, name: str) -> Optional[Path]:
        if not name:
            return None
        # Block overly long names
        if len(name) > 255:
            return None
        # URL-decode to catch encoded traversal attempts
        import urllib.parse

        try:
            decoded_name = urllib.parse.unquote(name)
        except Exception:
            return None
        # Block directory traversal attempts (both raw and decoded)
        dangerous_patterns = ["/", "\\", "..", "\x00"]
        for pattern in dangerous_patterns:
            if pattern in name or pattern in decoded_name:
                return None
        # Only allow alphanumeric, underscore, hyphen, and .dem extension
        import re

        if not re.match(r"^[\w\-]+\.dem$", decoded_name, re.IGNORECASE):
            return None
        demo_dir = self.demo_dir.resolve()
        candidate = (self.demo_dir / decoded_name).resolve()
        # Verify the resolved path is still within demo_dir
        try:
            candidate.relative_to(demo_dir)
        except Exception:
            return None
        if candidate.suffix.lower() != ".dem":
            return None
        if not candidate.exists():
            return None
        return candidate

    def _is_valid_demo(self, path: Path) -> bool:
        try:
            file_size = path.stat().st_size
            if file_size <= 1024:
                return False
            with open(path, "rb") as handle:
                header = handle.read(8)
            return header.startswith(b"HL2DEMO")
        except Exception:
            return False

    def _set_mode(self, mode: Optional[str]) -> None:
        if mode not in {"live", "manual"}:
            return
        self.parse_mode = mode
        if mode == "live":
            self.selected_demo = None
            self._broadcast_state_update()
            self.playback_playing = False
            self.playback_tick = 0.0
            self._set_demo_valid(False)
            self._set_demo_loading(False)
        self._set_status(f"Switched to {mode} mode.", level="info", sticky=False)

    def _select_demo(self, name: Optional[str]) -> None:
        if not name:
            return
        # Input validation for demo name
        if not isinstance(name, str):
            return
        if len(name) > 255:
            return
        # Basic sanity check - must end with .dem
        if not name.lower().endswith(".dem"):
            return
        self.selected_demo = name
        if self.parse_mode != "manual":
            self.parse_mode = "manual"
        if self.parser:
            self.parser.reset_state()
        self.playback_tick = 0.0
        self.playback_playing = False
        self._set_demo_valid(False)
        self._set_demo_loading(True)
        self._set_status(f"Selected demo: {name}", level="info", sticky=False)
        self._broadcast_state_update()

    def _handle_playback(self, data: dict) -> None:
        action = data.get("action")
        if action == "play":
            self.playback_playing = True
        elif action == "pause":
            self.playback_playing = False
        elif action == "speed":
            try:
                speed = float(data.get("speed", 1.0))
            except Exception:
                speed = 1.0
            self.playback_speed = max(0.25, min(4.0, speed))
        elif action == "seek":
            if not self.parser:
                return
            tick_rate = self.parser.get_tick_rate() or 64.0
            target_tick = None
            if "tick" in data:
                try:
                    target_tick = int(data.get("tick"))
                except Exception:
                    target_tick = None
            if target_tick is None and "time" in data:
                try:
                    target_tick = int(float(data.get("time")) * tick_rate)
                except Exception:
                    target_tick = None
            if target_tick is None:
                return
            total_ticks = self.parser.get_total_ticks()
            if total_ticks > 0:
                target_tick = max(0, min(target_tick, total_ticks - 1))
            self.playback_tick = float(target_tick)
            self.parser.reset_state()

    def _set_sampling_interval(self, interval) -> None:
        try:
            value = int(interval)
        except Exception:
            return
        value = max(1, min(value, 60))
        self.msgpack_refresh_interval = value
        self._set_status(f"Sampling interval set to {value}.", level="info", sticky=False)

    def _set_attr_and_broadcast(self, attr_name: str, value: bool) -> None:
        if getattr(self, attr_name) == value:
            return
        setattr(self, attr_name, value)
        self._broadcast_state_update()

    def _set_demo_valid(self, value: bool) -> None:
        self._set_attr_and_broadcast("demo_valid", value)

    def _set_demo_loading(self, value: bool) -> None:
        self._set_attr_and_broadcast("demo_loading", value)

    def _set_map_override(self, map_name: Optional[str]) -> None:
        if not map_name or map_name == "auto":
            self.map_override = None
            self._set_status("Map override cleared.", level="info", sticky=False)
            self._set_bounds_safe(True)
            return
        if map_name not in MAP_DEFINITIONS:
            self._set_status("Map override ignored: unknown map.", level="warning", sticky=False)
            return
        self.map_override = map_name
        self._set_status(f"Map override set to {map_name}.", level="info", sticky=False)

    def _set_bounds_safe(self, value: bool) -> None:
        self._set_attr_and_broadcast("bounds_safe", value)

    def _refresh_demo_list(self) -> None:
        demos = []
        if self.demo_dir.exists():
            entries = []
            for path in self.demo_dir.glob("*.dem"):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                entries.append((stat.st_mtime, stat.st_size, path.name))
            for mtime, size, name in sorted(entries, key=lambda item: item[0], reverse=True):
                demos.append({"name": name, "size": size, "mtime": mtime})
        with self.demo_list_lock:
            if demos != self.demo_list:
                self.demo_list = demos
                self.demo_list_version += 1

    def _get_demo_list_snapshot(self):
        with self.demo_list_lock:
            return list(self.demo_list), self.demo_list_version

    def _set_status(self, message: str, level: str = "info", sticky: bool = False) -> None:
        payload = {
            "type": "status",
            "message": message,
            "level": level,
            "expires_in": 0 if sticky else 5000,
        }
        with self.status_lock:
            if payload == self.status_payload:
                return
            self.status_payload = payload
            self.status_version += 1

    def _broadcast_state_update(self) -> None:
        if self.loop is None:
            return
        with self.state_lock:
            if not self.clients:
                return
            payload = json.dumps(
                {
                    "type": "state",
                    "mode": self.parse_mode,
                    "selected_demo": self.selected_demo,
                    "map_override": self.map_override,
                    "demo_valid": self.demo_valid,
                    "demo_loading": self.demo_loading,
                    "bounds_safe": self.bounds_safe,
                }
            )
            clients_snapshot = list(self.clients)

        for client in clients_snapshot:
            try:
                future = asyncio.run_coroutine_threadsafe(client.send(payload), self.loop)
                future.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
            except Exception as exc:
                print(f"WARN: Failed to broadcast state update: {exc}")

    def _update_live_latency_status(self, update: dict) -> None:
        if self.parse_mode != "live":
            return
        lag = update.get("_live_lag_sec")
        if lag is None:
            return
        if lag > 1.0:
            self.live_latency_warning = True
            self._set_status(f"Live latency {lag:.2f}s (target < 1s)", level="warning", sticky=True)
        elif self.live_latency_warning:
            self.live_latency_warning = False
            self._set_status("", level="info", sticky=False)

    def _auto_tune_poll_interval(self, update: dict) -> None:
        if self.parse_mode != "live":
            return
        lag = update.get("_live_lag_sec")
        if lag is None:
            return
        if lag > 1.0:
            self.lag_streak += 1
            self.good_streak = 0
        elif lag < 0.4:
            self.good_streak += 1
            self.lag_streak = 0
        else:
            self.lag_streak = 0
            self.good_streak = 0

        if self.lag_streak >= 2 and self.poll_interval > self.min_poll_interval:
            self.poll_interval = max(self.min_poll_interval, round(self.poll_interval - 0.1, 2))
            self.lag_streak = 0
        elif self.good_streak >= 10 and self.poll_interval < self.base_poll_interval:
            self.poll_interval = min(self.base_poll_interval, round(self.poll_interval + 0.1, 2))
            self.good_streak = 0

    def _get_status_snapshot(self):
        with self.status_lock:
            return dict(self.status_payload), self.status_version

    def _poll_parser(self):
        if not self.parser:
            return None
        if self.parse_mode == "manual":
            return self._poll_manual_parser()
        if self.worker_in and self.worker_out:
            return self._poll_worker()
        if self.executor:
            try:
                future = self.executor.submit(self.parser.parse_incremental)
                return future.result()
            except Exception as exc:
                print(f"Executor parse error: {exc}")
                self.executor = None
                return self.parser.parse_incremental()
        return self.parser.parse_incremental()

    def _poll_manual_parser(self):
        if not self.parser:
            return None
        total_ticks = self.parser.get_total_ticks()
        if self.playback_playing:
            tick_rate = self.parser.get_tick_rate() or 64.0
            self.playback_tick += tick_rate * self.poll_interval * self.playback_speed
            if total_ticks > 0 and self.playback_tick >= total_ticks:
                self.playback_tick = float(max(0, total_ticks - 1))
                self.playback_playing = False
                self._set_status("Playback finished.", level="info", sticky=False)
        start_tick = int(max(0, self.playback_tick))
        return self.parser.parse_window(start_tick, self.parser.tick_window)

    def _log_metrics(self, update) -> None:
        if not self.parser or self.parser.update_count % 10 != 0:
            return
        avg_parse = sum(self.parse_times) / len(self.parse_times) if self.parse_times else 0
        compression_pct = 0
        if self.compression_stats["total"] > 0:
            compression_pct = (
                self.compression_stats["compressed"] / self.compression_stats["total"]
            ) * 100
        print(
            f"Parse: {update.get('_parse_ms', 0):.1f}ms | "
            f"Avg: {avg_parse:.1f}ms | "
            f"Compression: {compression_pct:.1f}% | "
            f"Clients: {self.client_count} | "
            f"Map: {update.get('map', 'Unknown')}"
        )

    def _start_worker(self):
        if self.worker_process:
            return
        self.worker_process, self.worker_in, self.worker_out = start_worker()
        self.worker_backoff = 1.0

    def _stop_worker(self):
        if not self.worker_process:
            return
        try:
            self.worker_in.put({"cmd": "stop"})
        except Exception as exc:
            print(f"WARN: Failed to signal worker stop: {exc}")
        try:
            self.worker_process.join(timeout=2)
        except Exception as exc:
            print(f"WARN: Failed to join worker process: {exc}")
        self.worker_process = None
        self.worker_in = None
        self.worker_out = None

    def _poll_worker(self):
        try:
            self.worker_in.put({"cmd": "poll"})
            response = self.worker_out.get(timeout=2)
            if not isinstance(response, dict):
                return None
            return response.get("update")
        except queue.Empty:
            return None
        except Exception as exc:
            print(f"Worker poll failed: {exc}")
            self._stop_worker()
            self.worker_restart_at = time.time() + self.worker_backoff
            self.worker_backoff = min(self.worker_backoff * 2, 30.0)
            return None

    def get_metrics(self):
        compression_pct = 0.0
        if self.compression_stats["total"] > 0:
            compression_pct = (
                self.compression_stats["compressed"] / self.compression_stats["total"]
            ) * 100
        avg_parse = sum(self.parse_times) / len(self.parse_times) if self.parse_times else 0.0
        last_parse = self.parse_times[-1] if self.parse_times else 0.0
        return {
            "uptime_sec": round(time.time() - self.start_time, 2),
            "clients": self.client_count,
            "compression_pct": round(compression_pct, 2),
            "avg_parse_ms": round(avg_parse, 2),
            "last_parse_ms": round(last_parse, 2),
            "last_tick": (self.last_update.get("data") or {}).get("tick")
            if self.last_update
            else None,
            "map": self.last_update.get("map") if self.last_update else None,
            "parser_executor": self.parser_executor,
        }

    def shutdown(self):
        self.is_running = False
        self._stop_worker()
