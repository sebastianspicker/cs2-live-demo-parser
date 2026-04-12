import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOGGER = logging.getLogger(__name__)


def make_metrics_handler(server_ref):
    class MetricsHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0] if self.path else ""
            if path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
                return
            if path != "/metrics":
                self.send_response(404)
                self.end_headers()
                return
            try:
                payload = json.dumps(server_ref.get_metrics()).encode("utf-8")
            except Exception as exc:
                LOGGER.error("Failed to serialize metrics payload: %s", exc)
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"internal_error"}')
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            return

    return MetricsHandler


def start_metrics_server(server_ref, port: int, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    handler = make_metrics_handler(server_ref)
    metrics_server = ThreadingHTTPServer((host, port), handler)
    metrics_thread = threading.Thread(target=metrics_server.serve_forever, daemon=True)
    metrics_thread.start()
    return metrics_server
