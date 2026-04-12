from html.parser import HTMLParser
from pathlib import Path


class IdCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == "id" and value:
                self.ids.add(value)


def _collect_ids(path: Path) -> set[str]:
    parser = IdCollector()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.ids


def test_client_html_contains_required_ids():
    html_path = Path("client/index.html")
    ids = _collect_ids(html_path)
    required = {
        "radarCanvas",
        "mapSelector",
        "demoSelector",
        "modeSelector",
        "samplingSelector",
        "samplingHintToggle",
        "samplingHintText",
        "mapOverrideBadge",
        "demoStatusBadge",
        "mapSafetyBadge",
        "playbackPlay",
        "playbackPause",
        "playbackBack",
        "playbackForward",
        "playbackSpeed",
        "playbackSeek",
        "playbackTime",
        "advisoryBanner",
        "advisoryText",
        "advisoryDismiss",
        "liveLag",
        "demoSpeed",
        "latencyEst",
        "dataRate",
        "playersAlive",
        "updateRate",
        "parseTime",
        "avgParseTime",
        "compressionRate",
    }
    missing = required - ids
    assert not missing, f"Missing IDs in client/index.html: {sorted(missing)}"


def test_client_js_handles_position_updates_and_state():
    app_js = Path("client/js/app.js").read_text(encoding="utf-8")
    assert 'message.type === "position_update"' in app_js
    assert 'message.type === "state"' in app_js
    assert "message._live_lag_sec" in app_js
    assert "demoSpeedPct" in app_js


def test_client_js_avoids_inner_html():
    app_js = Path("client/js/app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in app_js


def test_render_draws_bomb_marker():
    render_js = Path("client/js/render.js").read_text(encoding="utf-8")
    assert "const bomb = client.gameState.bomb" in render_js
    assert "C4" in render_js
