import os
from pathlib import Path

import msgpack

from ws_server import ProfessionalBroadcastServer


def _write_demo(path: Path, valid: bool) -> None:
    header = b"HL2DEMO\x00" if valid else b"NOTDEMO\x00"
    path.write_bytes(header + b"x" * 32)


def test_resolve_demo_path_blocks_traversal(tmp_path):
    server = ProfessionalBroadcastServer(tmp_path, use_msgpack=False, poll_interval=0.1)
    outside = tmp_path.parent / "escape.dem"
    outside.write_bytes(b"HL2DEMO\x00" + b"x")
    assert server._resolve_demo_path(str(outside)) is None


def test_is_valid_demo_header(tmp_path):
    server = ProfessionalBroadcastServer(tmp_path, use_msgpack=False, poll_interval=0.1)
    valid = tmp_path / "valid.dem"
    invalid = tmp_path / "invalid.dem"
    _write_demo(valid, True)
    _write_demo(invalid, False)
    assert server._is_valid_demo(valid) is True
    assert server._is_valid_demo(invalid) is False


def test_refresh_demo_list_orders_latest_first(tmp_path):
    server = ProfessionalBroadcastServer(tmp_path, use_msgpack=False, poll_interval=0.1)
    older = tmp_path / "older.dem"
    newer = tmp_path / "newer.dem"
    _write_demo(older, True)
    _write_demo(newer, True)
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))
    server._refresh_demo_list()
    demos, _ = server._get_demo_list_snapshot()
    assert [d["name"] for d in demos] == ["newer.dem", "older.dem"]


def test_pack_update_sets_msg_bytes_consistently(tmp_path):
    server = ProfessionalBroadcastServer(tmp_path, use_msgpack=True, poll_interval=0.1)
    payload = {"type": "position_update", "data": {"tick": 1}}
    binary, _, _, _ = server._pack_update(payload)
    decoded = msgpack.unpackb(binary, raw=False)
    assert isinstance(decoded["_msg_bytes"], int)
    assert decoded["_msg_bytes"] >= 0
    assert server.last_msg_bytes == len(binary)


def test_default_bind_host_is_localhost(tmp_path):
    server = ProfessionalBroadcastServer(tmp_path, use_msgpack=False, poll_interval=0.1)
    assert server.bind_host == "127.0.0.1"


def test_refresh_demo_list_skips_missing_files(tmp_path, monkeypatch):
    server = ProfessionalBroadcastServer(tmp_path, use_msgpack=False, poll_interval=0.1)
    ok_demo = tmp_path / "ok.dem"
    missing_demo = tmp_path / "missing.dem"
    _write_demo(ok_demo, True)
    _write_demo(missing_demo, True)

    original_stat = Path.stat

    def stat_with_missing(self, *args, **kwargs):
        if self.name == "missing.dem":
            raise FileNotFoundError
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat_with_missing)
    server._refresh_demo_list()
    demos, _ = server._get_demo_list_snapshot()
    names = {entry["name"] for entry in demos}
    assert "ok.dem" in names
    assert "missing.dem" not in names


def test_select_active_demo_skips_stat_failures(tmp_path, monkeypatch):
    server = ProfessionalBroadcastServer(tmp_path, use_msgpack=False, poll_interval=0.1)
    ok_demo = tmp_path / "ok.dem"
    missing_demo = tmp_path / "missing.dem"
    _write_demo(ok_demo, True)
    _write_demo(missing_demo, True)

    original_stat = Path.stat

    def stat_with_missing(self, *args, **kwargs):
        if self.name == "missing.dem":
            raise FileNotFoundError
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat_with_missing)
    server._select_active_demo()
    assert server.current_demo == str(ok_demo)
