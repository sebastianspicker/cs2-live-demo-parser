from pathlib import Path

import config


def test_strip_json5_removes_comments_and_trailing_commas():
    raw = """
    // line comment
    {
      "resolution": 2.0, /* block comment */
      "offset": {"x": 128, "y": 256,},
    }
    """
    stripped = config._strip_json5(raw)
    assert "line comment" not in stripped
    assert "block comment" not in stripped
    assert ",}" not in stripped
    assert ",]" not in stripped


def test_load_overview_meta_parses_meta(tmp_path):
    meta_dir = tmp_path / "de_test"
    meta_dir.mkdir(parents=True)
    meta_path = meta_dir / "meta.json5"
    meta_path.write_text(
        """
        {
          // comment
          "resolution": 2.0,
          "offset": {"x": 128, "y": 256,},
          "zRange": {"min": -100, "max": 200,}
        }
        """,
        encoding="utf-8",
    )
    bounds = config.load_overview_meta(tmp_path)
    assert "Test" in bounds
    entry = bounds["Test"]
    assert entry["min_x"] == -128.0
    assert entry["min_y"] == -256.0
    assert entry["max_x"] == -128.0 + 2.0 * 1024.0
    assert entry["max_y"] == -256.0 + 2.0 * 1024.0
    assert entry["z_range"]["min"] == -100.0
    assert entry["z_range"]["max"] == 200.0


def test_default_paths_resolve_from_repo_root(monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.delenv("CS2_MAP_BOUNDS_FILE", raising=False)
    monkeypatch.delenv("CS2_OVERVIEW_DIR", raising=False)
    monkeypatch.delenv("CS2_CONFIG_FILE", raising=False)
    monkeypatch.delenv("CS2_MAP_DEFINITIONS_FILE", raising=False)

    monkeypatch.chdir(repo_root / "server")

    assert config.get_bounds_path() == repo_root / "maps/world_bounds.json"
    assert config.get_overview_dir() == repo_root / "maps/overviews"
    assert config.get_config_path() == repo_root / "config.json"
    assert config.get_map_definitions_path() == repo_root / "maps/map_definitions.json"


def test_load_setting_str_prefers_env(monkeypatch):
    monkeypatch.setenv("CS2_BIND_HOST", "0.0.0.0")
    value = config.load_setting_str("server", "bind_host", "CS2_BIND_HOST", "127.0.0.1")
    assert value == "0.0.0.0"
