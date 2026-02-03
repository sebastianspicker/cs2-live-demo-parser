from __future__ import annotations

from typing import Any, Dict, List, Optional

from state import build_kill_feed


class EventCollector:
    def __init__(self, demo_parser):
        self.demo_parser = demo_parser
        self.event_names: Dict[str, str] = {}
        self.events_cache: List[Dict[str, Any]] = []
        self.kill_feed_cache: List[Dict[str, Any]] = []

        self.round_number = 0
        self.ct_score = 0
        self.t_score = 0
        self.bomb_planted = False

        self.last_event_tick = -1
        self.last_round_tick = -1
        self.last_score_tick = -1
        self.last_bomb_planted_tick = -1
        self.last_bomb_resolve_tick = -1
        self.last_weapon_fire_tick = -1
        self.last_player_hurt_tick = -1
        self.last_player_blind_tick = -1
        self.last_hegrenade_detonate_tick = -1
        self.last_flashbang_detonate_tick = -1
        self.last_smokegrenade_detonate_tick = -1
        self.last_smokegrenade_expired_tick = -1
        self.last_molotov_detonate_tick = -1
        self.last_decoy_detonate_tick = -1
        self._event_frames: Dict[str, Any] = {}
        self.bomb_position: Optional[Dict[str, float]] = None
        self.bomb_planter: Optional[str] = None

    def reset_state(self) -> None:
        self.events_cache = []
        self.kill_feed_cache = []
        self.round_number = 0
        self.ct_score = 0
        self.t_score = 0
        self.bomb_planted = False
        self.last_event_tick = -1
        self.last_round_tick = -1
        self.last_score_tick = -1
        self.last_bomb_planted_tick = -1
        self.last_bomb_resolve_tick = -1
        self.last_weapon_fire_tick = -1
        self.last_player_hurt_tick = -1
        self.last_player_blind_tick = -1
        self.last_hegrenade_detonate_tick = -1
        self.last_flashbang_detonate_tick = -1
        self.last_smokegrenade_detonate_tick = -1
        self.last_smokegrenade_expired_tick = -1
        self.last_molotov_detonate_tick = -1
        self.last_decoy_detonate_tick = -1
        self._event_frames = {}
        self.bomb_position = None
        self.bomb_planter = None

    def resolve_event_names(self) -> None:
        try:
            available = set(self.demo_parser.list_game_events())
        except Exception:
            available = set()
        candidates = {
            "player_death": ["player_death"],
            "round_start": ["round_start", "round_prestart", "round_announce_match_start"],
            "round_end": ["round_end", "round_officially_ended"],
            "bomb_planted": ["bomb_planted"],
            "bomb_defused": ["bomb_defused"],
            "bomb_exploded": ["bomb_exploded"],
            "weapon_fire": ["weapon_fire"],
            "player_hurt": ["player_hurt"],
            "player_blind": ["player_blind"],
            "hegrenade_detonate": ["hegrenade_detonate"],
            "flashbang_detonate": ["flashbang_detonate"],
            "smokegrenade_detonate": ["smokegrenade_detonate"],
            "smokegrenade_expired": ["smokegrenade_expired"],
            "molotov_detonate": ["molotov_detonate", "inferno_startburn"],
            "decoy_detonate": ["decoy_detonate", "decoy_started"],
        }
        resolved = {}
        for key, options in candidates.items():
            for name in options:
                if name in available:
                    resolved[key] = name
                    break
        self.event_names = resolved

    def _event_position(self, row: Dict[str, Any]) -> Optional[Dict[str, float]]:
        for prefix in ("", "pos_", "position_", "user_", "attacker_", "victim_", "assister_"):
            x = row.get(f"{prefix}x")
            y = row.get(f"{prefix}y")
            z = row.get(f"{prefix}z")
            if x is None and y is None:
                x = row.get(f"{prefix}X")
                y = row.get(f"{prefix}Y")
                z = row.get(f"{prefix}Z")
            if x is None or y is None:
                continue
            try:
                return {"x": float(x), "y": float(y), "z": float(z or 0.0)}
            except Exception:
                continue
        return None

    def _event_player_name(self, row: Dict[str, Any], keys: List[str]) -> Optional[str]:
        for key in keys:
            value = row.get(key)
            if value:
                return str(value)
        return None

    def _get_new_events(self, event_name: str, last_tick_attr: str, max_tick: Optional[int] = None):
        event_key = self.event_names.get(event_name)
        if not event_key:
            return None
        events_df = self._event_frames.get(event_key)
        if events_df is None or events_df.empty:
            return None
        last_tick = getattr(self, last_tick_attr)
        if "tick" in events_df.columns and last_tick >= 0:
            events_df = events_df[events_df["tick"] > last_tick]
            if events_df.empty:
                return None
        if "tick" in events_df.columns and max_tick is not None:
            events_df = events_df[events_df["tick"] <= max_tick]
            if events_df.empty:
                return None
        if "tick" in events_df.columns and not events_df.empty:
            setattr(self, last_tick_attr, int(events_df["tick"].max()))
        return events_df

    def _winner_team(self, row: Dict[str, Any]) -> Optional[str]:
        winner = row.get("winner") or row.get("winner_team") or row.get("winner_name")
        winner_num = row.get("winner_team_num")
        if isinstance(winner_num, (int, float)):
            if int(winner_num) == 3:
                return "CT"
            if int(winner_num) == 2:
                return "T"
        if isinstance(winner, (int, float)):
            if int(winner) == 3:
                return "CT"
            if int(winner) == 2:
                return "T"
        if isinstance(winner, str):
            upper = winner.upper()
            if "CT" in upper or "COUNTER" in upper:
                return "CT"
            if "T" in upper or "TERRORIST" in upper:
                return "T"
        return None

    def _fetch_events_batch(self) -> Dict[str, Any]:
        if not self.event_names:
            return {}
        names = list({name for name in self.event_names.values() if name})
        parser = self.demo_parser
        if hasattr(parser, "parse_events"):
            try:
                result = parser.parse_events(names, player=["X", "Y", "Z"])
            except Exception:
                result = None
            if isinstance(result, dict):
                return result
            if isinstance(result, list):
                frames: Dict[str, Any] = {}
                for item in result:
                    if isinstance(item, tuple) and len(item) == 2:
                        event_name, frame = item
                        if isinstance(event_name, str):
                            frames[event_name] = frame
                if frames:
                    return frames
            if result is not None and len(names) == 1:
                return {names[0]: result}
        frames: Dict[str, Any] = {}
        for name in names:
            try:
                frames[name] = parser.parse_event(name, player=["X", "Y", "Z"])
            except Exception:
                continue
        return frames

    def refresh(self, max_tick: Optional[int] = None) -> None:
        self._event_frames = self._fetch_events_batch()

        kills_df = self._get_new_events("player_death", "last_event_tick", max_tick)
        if kills_df is not None:
            feed = build_kill_feed(kills_df)
            if feed:
                self.kill_feed_cache = feed
            for row in kills_df.to_dict("records"):
                tick = row.get("tick")
                victim = self._event_player_name(row, ["victim_name", "victim", "user_name"])
                attacker = self._event_player_name(row, ["attacker_name", "attacker"])
                self.events_cache.append(
                    {"type": "player_death", "tick": tick, "victim": victim, "attacker": attacker}
                )

        round_df = self._get_new_events("round_start", "last_round_tick", max_tick)
        if round_df is not None:
            self.round_number += len(round_df.index)
            for row in round_df.to_dict("records"):
                tick = row.get("tick")
                self.events_cache.append({"type": "round_start", "tick": tick})

        round_end_df = self._get_new_events("round_end", "last_score_tick", max_tick)
        if round_end_df is not None:
            for row in round_end_df.to_dict("records"):
                team = self._winner_team(row)
                if team == "CT":
                    self.ct_score += 1
                elif team == "T":
                    self.t_score += 1
                tick = row.get("tick")
                self.events_cache.append({"type": "round_end", "tick": tick, "winner": team})

        planted_df = self._get_new_events("bomb_planted", "last_bomb_planted_tick", max_tick)
        if planted_df is not None:
            self.bomb_planted = True
            for row in planted_df.to_dict("records"):
                tick = row.get("tick")
                player = self._event_player_name(
                    row, ["userid_name", "user_name", "player_name", "userid"]
                )
                position = self._event_position(row)
                if position:
                    self.bomb_position = position
                if player:
                    self.bomb_planter = player
                payload = {"type": "bomb_planted", "tick": tick}
                if player:
                    payload["player"] = player
                if position:
                    payload.update(position)
                self.events_cache.append(payload)
        defused_df = self._get_new_events("bomb_defused", "last_bomb_resolve_tick", max_tick)
        exploded_df = self._get_new_events("bomb_exploded", "last_bomb_resolve_tick", max_tick)
        if defused_df is not None or exploded_df is not None:
            self.bomb_planted = False
            self.bomb_position = None
            self.bomb_planter = None
            if defused_df is not None:
                for row in defused_df.to_dict("records"):
                    tick = row.get("tick")
                    player = self._event_player_name(
                        row, ["userid_name", "user_name", "player_name", "userid"]
                    )
                    payload = {"type": "bomb_defused", "tick": tick}
                    if player:
                        payload["player"] = player
                    self.events_cache.append(payload)
            if exploded_df is not None:
                for row in exploded_df.to_dict("records"):
                    tick = row.get("tick")
                    self.events_cache.append({"type": "bomb_exploded", "tick": tick})

        weapon_df = self._get_new_events("weapon_fire", "last_weapon_fire_tick", max_tick)
        if weapon_df is not None:
            for row in weapon_df.to_dict("records"):
                tick = row.get("tick")
                player = self._event_player_name(
                    row, ["userid_name", "user_name", "player_name", "userid"]
                )
                self.events_cache.append({"type": "weapon_fire", "tick": tick, "player": player})

        hurt_df = self._get_new_events("player_hurt", "last_player_hurt_tick", max_tick)
        if hurt_df is not None:
            for row in hurt_df.to_dict("records"):
                tick = row.get("tick")
                victim = self._event_player_name(row, ["victim_name", "user_name", "userid"])
                attacker = self._event_player_name(row, ["attacker_name", "attacker"])
                self.events_cache.append(
                    {"type": "player_hurt", "tick": tick, "victim": victim, "attacker": attacker}
                )

        blind_df = self._get_new_events("player_blind", "last_player_blind_tick", max_tick)
        if blind_df is not None:
            for row in blind_df.to_dict("records"):
                tick = row.get("tick")
                player = self._event_player_name(
                    row, ["userid_name", "user_name", "player_name", "userid"]
                )
                self.events_cache.append({"type": "player_blind", "tick": tick, "player": player})

        utility_events = [
            "hegrenade_detonate",
            "flashbang_detonate",
            "smokegrenade_detonate",
            "smokegrenade_expired",
            "molotov_detonate",
            "decoy_detonate",
        ]
        for event_name in utility_events:
            df = self._get_new_events(event_name, f"last_{event_name}_tick", max_tick)
            if df is None:
                continue
            for row in df.to_dict("records"):
                tick = row.get("tick")
                position = self._event_position(row)
                payload = {"type": event_name, "tick": tick}
                if position:
                    payload.update(position)
                self.events_cache.append(payload)

        if len(self.events_cache) > 20:
            self.events_cache = self.events_cache[-20:]
