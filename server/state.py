from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def _get_value(row: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _get_team_num(row: Dict[str, Any]) -> Optional[int]:
    raw = row.get("team_num") or row.get("team") or row.get("m_iTeamNum")
    if raw is None:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _get_vector(
    row: Dict[str, Any], base: str
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    value = row.get(base)
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        x = float(value[0])
        y = float(value[1])
        z = float(value[2]) if len(value) >= 3 else 0.0
        return x, y, z
    x = _get_value(row, [f"{base}_x", f"{base}.X", f"{base}.x", f"{base}[0]"])
    y = _get_value(row, [f"{base}_y", f"{base}.Y", f"{base}.y", f"{base}[1]"])
    z = _get_value(row, [f"{base}_z", f"{base}.Z", f"{base}.z", f"{base}[2]"])
    if x is None or y is None:
        return None, None, None
    return float(x), float(y), float(z or 0.0)


def _get_yaw(row: Dict[str, Any]) -> float:
    yaw = _get_value(row, ["yaw", "m_angEyeAngles_y", "m_angEyeAngles.Y", "m_angEyeAngles.y"])
    if yaw is not None:
        return float(yaw)
    value = row.get("m_angEyeAngles")
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return float(value[1])
    return 0.0


def update_world_bounds(world_bounds: Dict[str, Optional[float]], x: float, y: float) -> None:
    if world_bounds["min_x"] is None or x < world_bounds["min_x"]:
        world_bounds["min_x"] = x
    if world_bounds["max_x"] is None or x > world_bounds["max_x"]:
        world_bounds["max_x"] = x
    if world_bounds["min_y"] is None or y < world_bounds["min_y"]:
        world_bounds["min_y"] = y
    if world_bounds["max_y"] is None or y > world_bounds["max_y"]:
        world_bounds["max_y"] = y


def build_players(
    rows: List[Dict[str, Any]],
    player_info: Dict[int, str],
    world_bounds: Dict[str, Optional[float]],
    fixed_bounds: bool,
) -> Dict[str, Any]:
    players = []
    alive_ct = 0
    alive_t = 0
    for row in rows:
        steamid = row.get("steamid") or row.get("steamid64") or row.get("player")
        try:
            steamid_int = int(steamid) if steamid is not None else None
        except Exception:
            steamid_int = None
        name = player_info.get(steamid_int) if steamid_int is not None else None
        if not name:
            name = f"Player_{steamid_int}" if steamid_int else "Player"

        team_num = _get_team_num(row)
        team = "CT" if team_num == 3 else "T" if team_num == 2 else "UNK"

        life_state = row.get("life_state")
        health = row.get("health") or 0
        try:
            health_int = int(health)
        except Exception:
            health_int = 0
        if life_state is None:
            is_alive = health_int > 0
        else:
            is_alive = life_state == 0
        armor = row.get("armor_value") or 0
        helmet = bool(row.get("has_helmet") or False)
        money = row.get("balance")
        try:
            money_value = int(money) if money is not None else 0
        except Exception:
            money_value = 0

        x = row.get("X")
        y = row.get("Y")
        z = row.get("Z")
        if x is None or y is None:
            x, y, z = _get_vector(row, "m_vecOrigin")
        if x is None or y is None:
            continue
        if not fixed_bounds:
            update_world_bounds(world_bounds, x, y)

        if not is_alive and health_int <= 0:
            continue

        if is_alive:
            if team == "CT":
                alive_ct += 1
            elif team == "T":
                alive_t += 1

        players.append(
            {
                "id": steamid_int or 0,
                "name": name,
                "x": round(x, 2),
                "y": round(y, 2),
                "z": round(z or 0.0, 2),
                "yaw": round(_get_yaw(row), 1),
                "team": team,
                "is_alive": bool(is_alive),
                "health": health_int,
                "armor": int(armor),
                "has_helmet": helmet,
                "money": money_value,
                "weapon": "Unknown",
            }
        )

    return {"players": players, "alive_ct": alive_ct, "alive_t": alive_t}


def build_kill_feed(kills_df) -> List[Dict[str, Any]]:
    feed = []
    for row in kills_df.tail(5).to_dict("records"):
        attacker = row.get("attacker_name") or row.get("attacker")
        victim = row.get("victim_name") or row.get("victim") or row.get("user_name")
        weapon = row.get("weapon") or row.get("weapon_name") or "Unknown"
        headshot = bool(row.get("headshot") or row.get("is_headshot") or False)
        feed.append(
            {
                "killer": attacker or "Unknown",
                "victim": victim or "Unknown",
                "killer_team": "UNK",
                "weapon": weapon,
                "weapon_emoji": "🔫",
                "headshot": headshot,
                "time": datetime.now().isoformat(),
            }
        )
    return feed


def get_buy_status(money: float) -> str:
    if money >= 5000:
        return "Full Buy"
    if money >= 3000:
        return "Half Buy"
    if money >= 2000:
        return "Force Buy"
    return "Eco"


def compute_economy(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ct_total = 0
    t_total = 0
    for row in rows:
        team_num = _get_team_num(row)
        account = row.get("balance")
        if account is None:
            continue
        try:
            account_value = int(account)
        except Exception:
            continue
        if team_num == 3:
            ct_total += account_value
        elif team_num == 2:
            t_total += account_value
    return {
        "ct": ct_total,
        "t": t_total,
        "ct_status": get_buy_status(ct_total / 5 if ct_total else 0),
        "t_status": get_buy_status(t_total / 5 if t_total else 0),
    }


def compute_elapsed_seconds(header: Optional[Dict[str, Any]], tick: int) -> float:
    if not isinstance(header, dict):
        return 0.0
    playback_ticks = header.get("playback_ticks")
    playback_time = header.get("playback_time")
    if not playback_ticks or not playback_time:
        return 0.0
    try:
        tick_rate = float(playback_ticks) / float(playback_time)
        if tick_rate <= 0:
            return 0.0
        return tick / tick_rate
    except Exception:
        return 0.0
