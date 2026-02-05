from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

from demoparser2 import DemoParser

from config import (
    MAP_DEFINITIONS,
    get_bounds_path,
    get_overview_dir,
    load_boltobserv_meta,
    load_setting_float,
    load_setting_int,
)
from state import build_players, compute_elapsed_seconds, compute_economy
from events import EventCollector


class AdvancedDemoParser:
    """
    Demo parser wrapper with:
    - Map detection (header or filename)
    - Tick window parsing
    - Event throttling + caching
    - Optional fixed world bounds
    """

    def __init__(self, demo_path: str):
        self.demo_path = Path(demo_path)
        self.file_size = self.demo_path.stat().st_size if self.demo_path.exists() else 0
        self.update_count = 0

        # Detected map
        self.map_name = None
        self.map_config = None

        # Demo parser state
        self.demo_parser = None
        self.player_info = {}
        self.available_props = None
        self.header = None
        self.last_tick = -1
        self.last_file_size = 0
        self.last_event_file_size = 0
        self.last_event_mtime = 0.0
        self.last_no_data_streak = 0
        self.last_demo_time = None
        self.last_demo_file_size = None

        # Tick window config
        self.tick_window = load_setting_int("parser", "tick_window", "CS2_TICK_WINDOW", 256)
        self.tick_window_min = load_setting_int(
            "parser", "tick_window_min", "CS2_TICK_WINDOW_MIN", 256
        )
        self.tick_window_max = load_setting_int(
            "parser", "tick_window_max", "CS2_TICK_WINDOW_MAX", 2048
        )
        if self.tick_window_min < 1:
            self.tick_window_min = 1
        if self.tick_window_max < self.tick_window_min:
            self.tick_window_max = self.tick_window_min
        if self.tick_window < self.tick_window_min:
            self.tick_window = self.tick_window_min
        if self.tick_window > self.tick_window_max:
            self.tick_window = self.tick_window_max

        # Events
        self.last_event_parse_time = 0.0
        self.event_parse_interval = load_setting_float(
            "parser", "event_parse_interval", "CS2_EVENT_PARSE_INTERVAL", 2.0
        )
        self.events_dirty = False
        self.event_collector = None

        # World bounds
        self.world_bounds = {
            "min_x": None,
            "max_x": None,
            "min_y": None,
            "max_y": None,
        }
        self.fixed_world_bounds = None
        self.world_z_range = None
        self.world_transform = None
        self.map_bounds_file = get_bounds_path()
        self.overview_dir = get_overview_dir()
        self.overview_checked = False
        self.boltobserv_bounds = {}
        self.boltobserv_checked = False

        # Metrics
        self.last_parse_time = 0.0
        self.parse_times = []

        print(
            f"📄 Parser initialized: {self.demo_path.name} ({self.file_size / 1024 / 1024:.2f} MB)"
        )

    def detect_map_from_filename(self) -> Optional[str]:
        filename_lower = self.demo_path.name.lower()
        for map_name in MAP_DEFINITIONS.keys():
            if map_name.lower() in filename_lower:
                self.map_name = map_name
                self.map_config = MAP_DEFINITIONS[map_name]
                print(f"✅ Map detected (filename): {map_name}")
                return map_name
        return None

    def _normalize_map_name(self, raw_name: Optional[str]) -> Optional[str]:
        if not raw_name:
            return None
        candidate = raw_name.lower()
        if candidate.startswith("de_"):
            candidate = candidate[3:]
        for key in MAP_DEFINITIONS.keys():
            if key.lower() == candidate:
                return key
        return None

    def _load_fixed_bounds(self) -> None:
        if self.fixed_world_bounds is not None:
            return
        if not self.map_bounds_file.exists():
            self.fixed_world_bounds = False
            return
        try:
            with open(self.map_bounds_file, "r", encoding="utf-8") as handle:
                bounds = json.load(handle)
        except Exception as exc:
            print(f"❌ Failed to load map bounds: {exc}")
            self.fixed_world_bounds = False
            return
        if not self.map_name:
            self.fixed_world_bounds = False
            return
        entry = bounds.get(self.map_name)
        if not isinstance(entry, dict):
            self.fixed_world_bounds = False
            return
        required = {"min_x", "max_x", "min_y", "max_y"}
        if not required.issubset(entry.keys()):
            self.fixed_world_bounds = False
            return
        self.world_bounds = {
            "min_x": float(entry["min_x"]),
            "max_x": float(entry["max_x"]),
            "min_y": float(entry["min_y"]),
            "max_y": float(entry["max_y"]),
        }
        transform = entry.get("transform")
        if isinstance(transform, dict):
            self.world_transform = {
                "flip_x": bool(transform.get("flip_x", False)),
                "flip_y": bool(transform.get("flip_y", False)),
                "rotate_deg": float(transform.get("rotate_deg", 0.0)),
            }
        z_range = entry.get("z_range")
        if isinstance(z_range, dict) and "min" in z_range and "max" in z_range:
            try:
                self.world_z_range = {"min": float(z_range["min"]), "max": float(z_range["max"])}
            except Exception:
                pass
        self.fixed_world_bounds = True

    def _load_overview_bounds(self) -> None:
        if self.overview_checked:
            return
        self.overview_checked = True
        if not self.map_name:
            return
        if not self.overview_dir.exists():
            return
        overview_path_json = self.overview_dir / f"{self.map_name}.json"
        overview_path_txt = self.overview_dir / f"{self.map_name}.txt"
        data = None
        if overview_path_json.exists():
            try:
                with open(overview_path_json, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except Exception:
                data = None
        elif overview_path_txt.exists():
            try:
                text = overview_path_txt.read_text(encoding="utf-8", errors="ignore")
                data = {"_raw": text}
            except Exception:
                data = None
        if not data:
            return

        if isinstance(data, dict) and {"min_x", "max_x", "min_y", "max_y"}.issubset(data.keys()):
            self.world_bounds = {
                "min_x": float(data["min_x"]),
                "max_x": float(data["max_x"]),
                "min_y": float(data["min_y"]),
                "max_y": float(data["max_y"]),
            }
            self.fixed_world_bounds = True
            return

        raw = data.get("_raw") if isinstance(data, dict) else None
        if not raw:
            return

        def find_float(key: str) -> Optional[float]:
            match = re.search(rf"{key}\"?\\s*\"?(-?\\d+(?:\\.\\d+)?)", raw)
            if match:
                try:
                    return float(match.group(1))
                except Exception:
                    return None
            return None

        pos_x = find_float("pos_x")
        pos_y = find_float("pos_y")
        scale = find_float("scale")
        width = find_float("width") or find_float("res_x") or find_float("resolution") or 1024.0
        height = find_float("height") or find_float("res_y") or find_float("resolution") or 1024.0
        if pos_x is None or pos_y is None or scale is None:
            return
        max_x = pos_x + (scale * width)
        max_y = pos_y + (scale * height)
        self.world_bounds = {
            "min_x": float(min(pos_x, max_x)),
            "max_x": float(max(pos_x, max_x)),
            "min_y": float(min(pos_y, max_y)),
            "max_y": float(max(pos_y, max_y)),
        }
        self.fixed_world_bounds = True

    def _load_boltobserv_bounds(self) -> None:
        if self.boltobserv_checked:
            return
        self.boltobserv_checked = True
        base_dir = Path("maps/boltobserv")
        self.boltobserv_bounds = load_boltobserv_meta(base_dir)
        if not self.map_name:
            return
        bounds = self.boltobserv_bounds.get(self.map_name)
        if not bounds:
            return
        if not self.fixed_world_bounds:
            self.world_bounds = {
                "min_x": float(bounds["min_x"]),
                "max_x": float(bounds["max_x"]),
                "min_y": float(bounds["min_y"]),
                "max_y": float(bounds["max_y"]),
            }
            self.fixed_world_bounds = True
        if self.world_z_range is None and isinstance(bounds, dict):
            z_range = bounds.get("z_range")
            if isinstance(z_range, dict) and "min" in z_range and "max" in z_range:
                try:
                    self.world_z_range = {
                        "min": float(z_range["min"]),
                        "max": float(z_range["max"]),
                    }
                except Exception:
                    pass

    def _ensure_parser(self) -> None:
        if self.demo_parser is None:
            self.demo_parser = DemoParser(str(self.demo_path))

    def _load_player_info(self) -> None:
        if self.player_info:
            return
        try:
            info_df = self.demo_parser.parse_player_info()
        except Exception as exc:
            print(f"❌ Player info parse error: {exc}")
            return
        for row in info_df.to_dict("records"):
            steamid = row.get("steamid") or row.get("steamid64") or row.get("xuid")
            name = row.get("name") or row.get("player_name")
            if steamid is not None and name:
                try:
                    self.player_info[int(steamid)] = str(name)
                except Exception:
                    continue

    def _refresh_events(self, max_tick: Optional[int] = None):
        if not self.events_dirty:
            return
        now = time.time()
        if (
            self.last_event_parse_time
            and now - self.last_event_parse_time < self.event_parse_interval
        ):
            return
        self.last_event_parse_time = now
        if self.event_collector is None:
            self.event_collector = EventCollector(self.demo_parser)
            self.event_collector.resolve_event_names()
        self.event_collector.refresh(max_tick=max_tick)

        self.events_dirty = False
        return

    def _ensure_context(self) -> Optional[Dict[str, Any]]:
        self._ensure_parser()
        if self.header is None:
            try:
                header = self.demo_parser.parse_header()
            except Exception:
                header = None
            if isinstance(header, dict):
                self.header = header
        header = self.header or {}
        map_name = header.get("map_name") if isinstance(header, dict) else None
        if map_name and not self.map_name:
            normalized = self._normalize_map_name(map_name) or map_name
            self.map_name = normalized
            self.map_config = MAP_DEFINITIONS.get(normalized)
            print(f"✅ Map detected (header): {normalized}")
        if not self.map_name:
            self.detect_map_from_filename()
        if self.map_name and not self.map_config:
            self.map_config = MAP_DEFINITIONS.get(self.map_name)
        self._load_fixed_bounds()
        if not self.fixed_world_bounds:
            self._load_boltobserv_bounds()
        if not self.fixed_world_bounds:
            self._load_overview_bounds()

        if self.available_props is None:
            available = set(self.demo_parser.list_updated_fields())
            wanted = [
                "X",
                "Y",
                "Z",
                "pitch",
                "yaw",
                "health",
                "armor_value",
                "team_num",
                "life_state",
                "has_helmet",
                "balance",
            ]
            filtered = [prop for prop in wanted if prop in available]
            self.available_props = filtered or wanted

        if not self.available_props:
            print("❌ No usable properties found in demo.")
            return None
        return header

    def _build_update(
        self, latest_df, latest_tick: int, file_size: int, header: Dict[str, Any], start_time: float
    ) -> Dict[str, Any]:
        self._load_player_info()
        player_payload = build_players(
            latest_df.to_dict("records"),
            self.player_info,
            self.world_bounds,
            bool(self.fixed_world_bounds),
        )
        players = player_payload["players"]
        self._refresh_events(max_tick=latest_tick)
        event_collector = self.event_collector
        kill_feed = event_collector.kill_feed_cache if event_collector else []
        economy = compute_economy(latest_df.to_dict("records"))

        map_payload = dict(self.map_config) if self.map_config else {}
        if all(self.world_bounds[key] is not None for key in self.world_bounds):
            map_payload["world_bounds"] = {
                "min_x": float(self.world_bounds["min_x"]),
                "max_x": float(self.world_bounds["max_x"]),
                "min_y": float(self.world_bounds["min_y"]),
                "max_y": float(self.world_bounds["max_y"]),
            }
        if self.world_transform:
            map_payload["world_transform"] = dict(self.world_transform)
        if self.world_z_range:
            map_payload["z_range"] = dict(self.world_z_range)

        elapsed_seconds = compute_elapsed_seconds(header, latest_tick)
        demo_metrics = self._compute_demo_metrics(file_size, elapsed_seconds, header)

        round_number = event_collector.round_number if event_collector else 0
        ct_score = event_collector.ct_score if event_collector else 0
        t_score = event_collector.t_score if event_collector else 0
        bomb_planted = event_collector.bomb_planted if event_collector else False
        bomb_position = event_collector.bomb_position if event_collector else None
        bomb_planter = event_collector.bomb_planter if event_collector else None
        events_cache = event_collector.events_cache if event_collector else []

        data = {
            "round": round_number or (ct_score + t_score + 1 if (ct_score + t_score) > 0 else 0),
            "time": elapsed_seconds,
            "ct_score": ct_score,
            "t_score": t_score,
            "money": economy,
            "players": players,
            "alive_ct": player_payload["alive_ct"],
            "alive_t": player_payload["alive_t"],
            "kill_feed": kill_feed,
            "events": list(events_cache),
            "bomb_planted": bomb_planted,
            "bomb": {
                "planted": bomb_planted,
                "position": bomb_position,
                "planter": bomb_planter,
            },
            "tick": latest_tick,
            "data_source": "demoparser2",
        }

        parse_time_ms = (time.time() - start_time) * 1000
        self.last_parse_time = parse_time_ms
        self.parse_times.append(parse_time_ms)
        self.update_count += 1

        return {
            "type": "position_update",
            "map": self.map_name,
            "map_config": map_payload,
            "data": data,
            "_parse_ms": round(parse_time_ms, 2),
            "_demo_time": round(elapsed_seconds, 2),
            "_demo_tick_rate": round(demo_metrics["demo_tick_rate"], 3),
            "_demo_remaining": round(demo_metrics["demo_remaining"], 2),
            "_demo_data_rate_bps": round(demo_metrics["demo_data_rate_bps"], 2),
            "_file_pos": file_size,
            "_file_size": file_size,
            "_update_count": self.update_count,
            "_avg_parse_ms": round(sum(self.parse_times) / len(self.parse_times), 2)
            if self.parse_times
            else 0,
            "_cmd_count": len(players),
        }

    def reset_state(self) -> None:
        self.last_tick = -1
        self.last_event_parse_time = 0.0
        self.events_dirty = True
        self.last_demo_time = None
        self.last_demo_file_size = None
        if self.event_collector:
            self.event_collector.reset_state()

    def get_tick_rate(self) -> float:
        self._ensure_parser()
        if self.header is None:
            try:
                self.header = self.demo_parser.parse_header()
            except Exception:
                self.header = None
        header = self.header or {}
        playback_ticks = header.get("playback_ticks")
        playback_time = header.get("playback_time")
        if playback_ticks and playback_time:
            try:
                tick_rate = float(playback_ticks) / float(playback_time)
                return tick_rate if tick_rate > 0 else 0.0
            except Exception:
                return 0.0
        return 0.0

    def get_total_ticks(self) -> int:
        if self.header is None:
            self.get_tick_rate()
        header = self.header or {}
        try:
            return int(header.get("playback_ticks") or 0)
        except Exception:
            return 0

    def _compute_demo_metrics(
        self, file_size: int, elapsed_seconds: float, header: Dict[str, Any]
    ) -> Dict[str, float]:
        playback_ticks = header.get("playback_ticks") if isinstance(header, dict) else None
        playback_time = header.get("playback_time") if isinstance(header, dict) else None
        demo_tick_rate = 0.0
        demo_remaining = 0.0
        if playback_ticks and playback_time:
            try:
                demo_tick_rate = float(playback_ticks) / float(playback_time)
                demo_remaining = max(0.0, float(playback_time) - float(elapsed_seconds))
            except Exception:
                demo_tick_rate = 0.0
                demo_remaining = 0.0
        demo_data_rate = 0.0
        if self.last_demo_time is not None and self.last_demo_file_size is not None:
            delta_time = elapsed_seconds - self.last_demo_time
            if delta_time > 0:
                demo_data_rate = (file_size - self.last_demo_file_size) / delta_time
        self.last_demo_time = elapsed_seconds
        self.last_demo_file_size = file_size
        return {
            "demo_tick_rate": demo_tick_rate,
            "demo_remaining": demo_remaining,
            "demo_data_rate_bps": demo_data_rate,
        }

    def _parse_ticks_window(
        self, start_tick: int, tick_window: int, grow_on_empty: bool
    ) -> Optional[Dict[str, Any]]:
        start_tick = max(0, int(start_tick))
        tick_range = range(start_tick, start_tick + tick_window)
        df = self.demo_parser.parse_ticks(self.available_props, ticks=tick_range)
        if df.empty and grow_on_empty:
            self.last_no_data_streak += 1
            if self.last_no_data_streak >= 3 and self.tick_window < self.tick_window_max:
                self.tick_window = min(self.tick_window * 2, self.tick_window_max)
            tick_range = range(start_tick, start_tick + (tick_window * 4))
            df = self.demo_parser.parse_ticks(self.available_props, ticks=tick_range)
        if df.empty or "tick" not in df.columns:
            return None
        latest_tick = int(df["tick"].max())
        latest_df = df[df["tick"] == latest_tick]
        if latest_df.empty:
            return None
        return {"df": df, "latest_df": latest_df, "latest_tick": latest_tick}

    def parse_incremental(self) -> Optional[Dict[str, Any]]:
        start_time = time.time()

        try:
            if not self.demo_path.exists():
                return None
            file_stat = self.demo_path.stat()
            file_size = file_stat.st_size
            file_mtime = file_stat.st_mtime
            now_ts = time.time()
            live_lag_sec = max(0.0, now_ts - file_mtime)
            if file_size == self.last_file_size:
                return None
            self.last_file_size = file_size
            if (
                file_size != self.last_event_file_size
                or file_stat.st_mtime != self.last_event_mtime
            ):
                self.events_dirty = True
                self.last_event_file_size = file_size
                self.last_event_mtime = file_stat.st_mtime

            header = self._ensure_context()
            if header is None:
                return None

            start_tick = max(self.last_tick + 1, 0)
            parsed = self._parse_ticks_window(start_tick, self.tick_window, grow_on_empty=True)
            if not parsed:
                return None
            latest_tick = parsed["latest_tick"]
            if latest_tick <= self.last_tick:
                return None
            if self.tick_window > self.tick_window_min:
                self.tick_window = max(self.tick_window_min, self.tick_window // 2)
            self.last_no_data_streak = 0

            self.last_tick = latest_tick
            update = self._build_update(
                parsed["latest_df"], latest_tick, file_size, header, start_time
            )
            update["_server_ts"] = round(now_ts, 3)
            update["_file_mtime"] = round(file_mtime, 3)
            update["_live_lag_sec"] = round(live_lag_sec, 3)
            return update

        except Exception as exc:
            print(f"❌ Parser error: {exc}")
            return None

    def parse_window(
        self, start_tick: int, tick_window: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        start_time = time.time()
        try:
            if not self.demo_path.exists():
                return None
            file_stat = self.demo_path.stat()
            file_size = file_stat.st_size
            file_mtime = file_stat.st_mtime
            now_ts = time.time()
            header = self._ensure_context()
            if header is None:
                return None

            tick_window = tick_window or self.tick_window
            parsed = self._parse_ticks_window(start_tick, tick_window, grow_on_empty=False)
            if not parsed:
                return None
            latest_tick = parsed["latest_tick"]

            self.last_tick = latest_tick
            self.events_dirty = True
            update = self._build_update(
                parsed["latest_df"], latest_tick, file_size, header, start_time
            )
            update["_server_ts"] = round(now_ts, 3)
            update["_file_mtime"] = round(file_mtime, 3)
            update["_live_lag_sec"] = 0.0
            return update

        except Exception as exc:
            print(f"❌ Parser error: {exc}")
            return None
