from __future__ import annotations

from pathlib import Path
import socket
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from agentic_project_builder.server import create_server


class StaticServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "index.html").write_text("<h1>demo</h1>", encoding="utf-8")
        (self.root / "app.js").write_text("export {};", encoding="utf-8")
        (self.root / "data.bin").write_bytes(b"\x00\x01")
        self.server = create_server(self.root, host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def get(self, path: str) -> tuple[int, str, bytes]:
        try:
            with urlopen(self.base_url + path, timeout=2) as response:
                return response.status, response.headers.get("content-type", ""), response.read()
        except HTTPError as error:
            return error.code, error.headers.get("content-type", ""), error.read()

    def raw_status(self, method: str) -> int:
        with socket.create_connection(("127.0.0.1", self.server.server_port), timeout=2) as connection:
            connection.sendall(f"{method} /app.js HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
            response = connection.recv(256)
        return int(response.split(b" ", 2)[1])

    def test_serves_root_query_and_mime_types_like_node_server(self) -> None:
        self.assertEqual(self.get("/?cache=no")[:2], (200, "text/html; charset=utf-8"))
        self.assertEqual(self.get("/")[2], b"<h1>demo</h1>")
        self.assertEqual(self.get("/app.js")[:2], (200, "text/javascript; charset=utf-8"))
        self.assertEqual(self.get("/data.bin")[:2], (200, "application/octet-stream"))

    def test_node_server_serves_static_content_regardless_of_http_method(self) -> None:
        for method in ("POST", "TRACE", "PROPFIND"):
            with self.subTest(method=method):
                request = Request(self.base_url + "/app.js", method=method, data=b"ignored")
                with urlopen(request, timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.read(), b"export {};")

    def test_accepts_node_v22_method_tokens_and_rejects_unknown_tokens(self) -> None:
        node_methods = (
            "ACL", "BIND", "CHECKOUT", "CONNECT", "COPY", "DELETE", "GET", "HEAD", "LINK", "LOCK",
            "M-SEARCH", "MERGE", "MKACTIVITY", "MKCALENDAR", "MKCOL", "MOVE", "NOTIFY", "OPTIONS",
            "PATCH", "POST", "PROPFIND", "PROPPATCH", "PURGE", "PUT", "QUERY", "REBIND", "REPORT",
            "SEARCH", "SOURCE", "SUBSCRIBE", "TRACE", "UNBIND", "UNLINK", "UNLOCK", "UNSUBSCRIBE",
        )
        for method in node_methods:
            with self.subTest(method=method):
                self.assertEqual(self.raw_status(method), 200)
        self.assertEqual(self.raw_status("BREW"), 400)

    def test_preserves_status_bodies_and_blocks_encoded_traversal(self) -> None:
        self.assertEqual(self.get("/missing.txt"), (404, "text/plain; charset=utf-8", b"Not found"))
        self.assertEqual(self.get("/%2e%2e/secret.txt"), (403, "", b"Forbidden"))
        self.assertEqual(self.get("/%2e%2e%2fsecret.txt"), (403, "", b"Forbidden"))


if __name__ == "__main__":
    unittest.main()
