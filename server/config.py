import json
import os
import re
from pathlib import Path
from typing import Callable, TypeVar

DEFAULT_MAP_DEFINITIONS = {
    "Mirage": {
        "name": "Mirage",
        "scale": 220.0,
        "width": 220,
        "height": 200,
        "radar_scale": 4.4,
        "origin_x": 0,
        "origin_y": 0,
        "spawns": {
            "T": [(-1200, -800), (-1000, -1000), (-800, -900)],
            "CT": [(200, 200), (400, 100), (300, 300)],
        },
    },
    "Inferno": {
        "name": "Inferno",
        "scale": 280.0,
        "width": 280,
        "height": 275,
        "radar_scale": 3.5,
        "origin_x": 0,
        "origin_y": 0,
        "spawns": {
            "T": [(-1500, -1500), (-1300, -1600)],
            "CT": [(500, 500), (600, 400)],
        },
    },
    "Nuke": {
        "name": "Nuke",
        "scale": 300.0,
        "width": 300,
        "height": 275,
        "radar_scale": 3.3,
        "origin_x": 0,
        "origin_y": 0,
        "spawns": {
            "T": [(-1500, -2500)],
            "CT": [(500, 500)],
        },
    },
    "Dust2": {
        "name": "Dust2",
        "scale": 260.0,
        "width": 260,
        "height": 240,
        "radar_scale": 3.8,
        "origin_x": 0,
        "origin_y": 0,
        "spawns": {
            "T": [(-1800, -2500)],
            "CT": [(500, 2500)],
        },
    },
    "Ancient": {
        "name": "Ancient",
        "scale": 300.0,
        "width": 300,
        "height": 300,
        "radar_scale": 3.3,
        "origin_x": 0,
        "origin_y": 0,
        "spawns": {
            "T": [(-1500, -1200)],
            "CT": [(500, 500)],
        },
    },
    "Vertigo": {
        "name": "Vertigo",
        "scale": 240.0,
        "width": 240,
        "height": 240,
        "radar_scale": 4.16,
        "origin_x": 0,
        "origin_y": 0,
        "spawns": {
            "T": [(0, -1500)],
            "CT": [(0, 1500)],
        },
    },
    "Overpass": {
        "name": "Overpass",
        "scale": 320.0,
        "width": 320,
        "height": 240,
        "radar_scale": 3.125,
        "origin_x": 0,
        "origin_y": 0,
        "spawns": {
            "T": [(-1500, -500)],
            "CT": [(500, 2500)],
        },
    },
    "Anubis": {
        "name": "Anubis",
        "scale": 5.22,
        "width": 1024,
        "height": 1024,
        "radar_scale": 5.22,
        "origin_x": 0,
        "origin_y": 0,
        "spawns": {
            "T": [(-1500, -500)],
            "CT": [(500, 2500)],
        },
    },
}

_T = TypeVar("_T")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_path(env_key: str, relative_path: str) -> Path:
    value = os.getenv(env_key)
    if value:
        return Path(value)
    return _repo_root() / relative_path


def _load_env_cast(key: str, cast: Callable[[str], _T], default: _T) -> _T:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


def load_env_float(key: str, default: float) -> float:
    return _load_env_cast(key, float, default)


def load_env_int(key: str, default: int) -> int:
    return _load_env_cast(key, int, default)


def load_config_value(section: str, key: str, default=None):
    config = load_app_config()
    if not isinstance(config, dict):
        return default
    bucket = config.get(section)
    if not isinstance(bucket, dict):
        return default
    if key not in bucket:
        return default
    return bucket.get(key)


def load_setting_float(section: str, key: str, env_key: str, default: float) -> float:
    env_value = os.getenv(env_key)
    if env_value is not None:
        try:
            return float(env_value)
        except ValueError:
            return default
    config_value = load_config_value(section, key, default)
    try:
        return float(config_value)
    except (TypeError, ValueError):
        return default


def load_setting_int(section: str, key: str, env_key: str, default: int) -> int:
    env_value = os.getenv(env_key)
    if env_value is not None:
        try:
            return int(env_value)
        except ValueError:
            return default
    config_value = load_config_value(section, key, default)
    try:
        return int(config_value)
    except (TypeError, ValueError):
        return default


def load_setting_str(section: str, key: str, env_key: str, default: str) -> str:
    env_value = os.getenv(env_key)
    if env_value is not None:
        return env_value
    config_value = load_config_value(section, key, default)
    if config_value is None:
        return default
    return str(config_value)


def get_bounds_path() -> Path:
    return _default_path("CS2_MAP_BOUNDS_FILE", "maps/world_bounds.json")


def get_overview_dir() -> Path:
    return _default_path("CS2_OVERVIEW_DIR", "maps/overviews")


def get_config_path() -> Path:
    return _default_path("CS2_CONFIG_FILE", "config.json")


def get_map_definitions_path() -> Path:
    return _default_path("CS2_MAP_DEFINITIONS_FILE", "maps/map_definitions.json")


def _strip_json5(text: str) -> str:
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def _normalize_boltobserv_name(folder_name: str) -> str:
    name = folder_name.lower()
    if name.startswith("de_"):
        name = name[3:]
    return name.capitalize() if name else folder_name


def load_boltobserv_meta(base_dir: Path) -> dict:
    bounds = {}
    if not base_dir.exists():
        return bounds
    for meta_path in base_dir.glob("de_*/meta.json5"):
        try:
            raw = meta_path.read_text(encoding="utf-8", errors="ignore")
            data = json.loads(_strip_json5(raw))
        except Exception:
            continue
        resolution = data.get("resolution")
        offset = data.get("offset", {})
        if resolution is None or "x" not in offset or "y" not in offset:
            continue
        try:
            resolution_value = float(resolution)
            offset_x = float(offset["x"])
            offset_y = float(offset["y"])
        except Exception:
            continue
        radar_size = 1024.0
        min_x = -offset_x
        min_y = -offset_y
        max_x = min_x + (resolution_value * radar_size)
        max_y = min_y + (resolution_value * radar_size)
        map_key = _normalize_boltobserv_name(meta_path.parent.name)
        entry = {
            "min_x": min(min_x, max_x),
            "max_x": max(min_x, max_x),
            "min_y": min(min_y, max_y),
            "max_y": max(min_y, max_y),
        }
        z_range = data.get("zRange") if isinstance(data, dict) else None
        if isinstance(z_range, dict) and "min" in z_range and "max" in z_range:
            try:
                entry["z_range"] = {"min": float(z_range["min"]), "max": float(z_range["max"])}
            except Exception:
                pass
        bounds[map_key] = entry
    return bounds


def load_map_definitions() -> dict:
    path = get_map_definitions_path()
    if not path.exists():
        return DEFAULT_MAP_DEFINITIONS
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_MAP_DEFINITIONS
    if not isinstance(data, dict):
        return DEFAULT_MAP_DEFINITIONS
    return data


def load_app_config() -> dict:
    config_path = get_config_path()
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


MAP_DEFINITIONS = load_map_definitions()
