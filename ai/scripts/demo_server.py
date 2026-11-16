"""Local showcase of the AI work: one page of results plus live detection + tracking in the browser.

    python scripts/demo_server.py             # http://127.0.0.1:8765, opens the browser
    python scripts/demo_server.py --no-open --port 9000
    python scripts/demo_server.py --no-reid   # skip the Market-1501 nearest-crops precompute (~20 s first time)

Routes: /  the page;  /stream/<pets|tud|campus|adl|webcam>  MJPEG of the real pipeline;  /status  JSON;
/stop;  /results/<path>  committed result files;  /market/<split>/<file>  Market-1501 crops.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd_ai.demo import MARKET_DIR, SOURCES, LiveTracker, load_results, reid_showcase, render_page  # noqa: E402
from herd_ai.models import DEFAULT_MODEL, model_path  # noqa: E402
from herd_ai.paths import RESULTS_DIR  # noqa: E402

BOUNDARY = "herdframe"


class DemoServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, handler, page: str, live: LiveTracker | None):
        super().__init__(addr, handler)
        self.page = page.encode("utf-8")
        self.live = live
        self.stream_token = 0
        self.token_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server: DemoServer

    def log_message(self, fmt, *args):  # keep the console quiet except for errors
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)

    def _send_bytes(self, body: bytes, ctype: str, status=HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, root: Path, rel: str, allowed_suffixes: tuple[str, ...]) -> None:
        target = (root / rel).resolve()
        if root.resolve() not in target.parents or target.suffix.lower() not in allowed_suffixes or not target.is_file():
            self._send_bytes(b"not found", "text/plain", HTTPStatus.NOT_FOUND)
            return
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._send_bytes(target.read_bytes(), ctype)

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        path = unquote(url.path)
        if path == "/":
            self._send_bytes(self.server.page, "text/html; charset=utf-8")
        elif path.startswith("/results/"):
            self._send_file(RESULTS_DIR, path[len("/results/") :], (".png", ".jpg", ".jpeg", ".json", ".md"))
        elif path.startswith("/market/"):
            self._send_file(MARKET_DIR, path[len("/market/") :], (".jpg",))
        elif path == "/status":
            live = self.server.live
            self._send_bytes(json.dumps(live.status if live else {"error": "detector not loaded"}).encode(), "application/json")
        elif path == "/stop":
            with self.server.token_lock:
                self.server.stream_token += 1
            self._send_bytes(b"ok", "text/plain")
        elif path.startswith("/stream/"):
            self._stream(path[len("/stream/") :])
        else:
            self._send_bytes(b"not found", "text/plain", HTTPStatus.NOT_FOUND)

    def _stream(self, source: str) -> None:
        live = self.server.live
        if live is None or (source != "webcam" and source not in SOURCES):
            self._send_bytes(b"unknown source", "text/plain", HTTPStatus.NOT_FOUND)
            return
        with self.server.token_lock:
            self.server.stream_token += 1
            my_token = self.server.stream_token
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            for jpeg, _info in live.frames(source, keep_going=lambda: self.server.stream_token == my_token):
                self.wfile.write(f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n\r\n".encode())
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--model", type=Path, default=model_path(DEFAULT_MODEL.filename))
    ap.add_argument("--no-reid", action="store_true", help="skip the Market-1501 nearest-crops showcase")
    ap.add_argument("--no-open", action="store_true", help="do not open the browser")
    args = ap.parse_args(argv)

    results = load_results()
    reid_demo = [] if args.no_reid else reid_showcase()
    live = LiveTracker(args.model) if args.model.exists() else None
    if live is None:
        print(f"detector not found at {args.model}: live streams disabled (run scripts/download_models.py)", file=sys.stderr)
    page = render_page(results, reid_demo, model_name=f"YOLOv8n {live.det.input_size}" if live else "YOLOv8n")

    server = DemoServer((args.host, args.port), Handler, page, live)
    url = f"http://{args.host}:{args.port}/"
    print(f"Open Herd demo at {url}  (Ctrl+C to stop)")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
