from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http import HTTPStatus
from pathlib import Path
import re
from typing import TypeAlias
from urllib.parse import unquote, urlsplit


MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}
_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
ServerAddress: TypeAlias = tuple[str, int]
NODE_HTTP_METHODS = frozenset({
    "ACL", "BIND", "CHECKOUT", "CONNECT", "COPY", "DELETE", "GET", "HEAD", "LINK", "LOCK",
    "M-SEARCH", "MERGE", "MKACTIVITY", "MKCALENDAR", "MKCOL", "MOVE", "NOTIFY", "OPTIONS",
    "PATCH", "POST", "PROPFIND", "PROPPATCH", "PURGE", "PUT", "QUERY", "REBIND", "REPORT",
    "SEARCH", "SOURCE", "SUBSCRIBE", "TRACE", "UNBIND", "UNLINK", "UNLOCK", "UNSUBSCRIBE",
})


class StaticServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: ServerAddress, root: Path):
        self.root = root.resolve()
        super().__init__(server_address, StaticRequestHandler)


class StaticRequestHandler(BaseHTTPRequestHandler):
    server: StaticServer

    def __getattr__(self, name: str):
        if name.startswith("do_") and name[3:] in NODE_HTTP_METHODS:
            return self._serve
        raise AttributeError(name)

    def parse_request(self) -> bool:
        if not super().parse_request():
            return False
        if self.command not in NODE_HTTP_METHODS:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return False
        return True

    def do_GET(self) -> None:
        self._serve()

    def do_HEAD(self) -> None:
        self._serve(include_body=False)

    def do_POST(self) -> None:
        self._serve()

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST
    do_OPTIONS = do_POST

    def log_message(self, format: str, *args: object) -> None:
        return

    def _serve(self, *, include_body: bool = True) -> None:
        try:
            path_text = urlsplit(self.path).path
            if _PERCENT_ESCAPE.search(path_text):
                raise ValueError("malformed percent escape")
            decoded = unquote(path_text, encoding="utf-8", errors="strict")
            requested = "index.html" if decoded == "/" else decoded.lstrip("/")
            file_path = (self.server.root / requested).resolve()
            if not file_path.is_relative_to(self.server.root):
                self.send_response(403)
                self.end_headers()
                if include_body:
                    self.wfile.write(b"Forbidden")
                return
            body = file_path.read_bytes()
            self.send_response(200)
            self.send_header("content-type", MIME_TYPES.get(file_path.suffix, "application/octet-stream"))
            self.end_headers()
            if include_body:
                self.wfile.write(body)
        except FileNotFoundError:
            self._plain_error(404, b"Not found", include_body)
        except Exception:
            self._plain_error(500, b"Server error", include_body)

    def _plain_error(self, status: int, body: bytes, include_body: bool) -> None:
        self.send_response(status)
        self.send_header("content-type", "text/plain; charset=utf-8")
        self.end_headers()
        if include_body:
            self.wfile.write(body)


def create_server(root: Path | str, *, host: str = "", port: int = 4173) -> StaticServer:
    return StaticServer((host, port), Path(root))


def serve(root: Path | str, *, host: str = "", port: int = 4173) -> None:
    server = create_server(root, host=host, port=port)
    print(f"ETF comparison demo available at http://localhost:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
