from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import base64
import hashlib
import json
import os
from pathlib import Path
import queue
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


DEFAULT_URL = "http://127.0.0.1:4173/"
DEFAULT_CHROME_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe"


@dataclass(frozen=True, slots=True)
class BrowserConfig:
    url: str = DEFAULT_URL
    chrome_path: Path = Path(DEFAULT_CHROME_PATH)
    cdp_port: int = 9333

    @classmethod
    def from_environment(
        cls,
        *,
        url: str | None = None,
        chrome_path: str | Path | None = None,
        cdp_port: int | None = None,
    ) -> BrowserConfig:
        return cls(
            url=url if url is not None else os.environ.get("URL", DEFAULT_URL),
            chrome_path=Path(chrome_path if chrome_path is not None else os.environ.get("CHROME_PATH", DEFAULT_CHROME_PATH)),
            cdp_port=cdp_port if cdp_port is not None else int(os.environ.get("CDP_PORT", "9333")),
        )


def failure_for_event(event: dict[str, Any]) -> str | None:
    method = event.get("method")
    params = event.get("params") or {}
    if method == "Log.entryAdded":
        entry = params.get("entry") or {}
        if entry.get("level") in {"error", "warning"}:
            return f"Log.{entry['level']}: {entry.get('text')}"
    if method == "Runtime.exceptionThrown":
        details = params.get("exceptionDetails") or {}
        return f"Runtime.exceptionThrown: {details.get('text') or 'exception'}"
    if method == "Network.responseReceived":
        response = params.get("response") or {}
        if response.get("status", 0) >= 400:
            return f"HTTP {response.get('status')}: {response.get('url')}"
    if method == "Network.loadingFailed":
        return f"Network.loadingFailed: {params.get('errorText') or 'failed'} {params.get('requestId') or ''}"
    return None


def page_state_failures(state: dict[str, Any]) -> list[str]:
    checks = (
        (state.get("fundCount") == 3, f"Expected 3 ETF options, got {state.get('fundCount')}"),
        (state.get("rowCount") == 9, f"Expected 9 rendered comparison rows, got {state.get('rowCount')}"),
        (state.get("explanationCount", 0) > 0, "Expected rendered explanation items"),
        (state.get("sourceCount", 0) > 0, "Expected rendered source links"),
        (state.get("validation") == "", f"Unexpected validation message: {state.get('validation')}"),
        (state.get("heading") == "FieldSPYQQQ", f"Unexpected comparison heading: {state.get('heading')}"),
    )
    return [message for valid, message in checks if not valid]


def _request_json(method: str, path: str, port: int, timeout: float = 1.0) -> dict[str, Any]:
    request = Request(f"http://127.0.0.1:{port}{path}", method=method)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_for_cdp(port: int, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            _request_json("GET", "/json/version", port)
            return
        except (OSError, URLError, ValueError):
            time.sleep(0.1)
    raise RuntimeError(f"Chrome CDP did not start on port {port}")


def _encode_client_frame(payload: bytes, opcode: int = 1) -> bytes:
    first = 0x80 | opcode
    length = len(payload)
    if length < 126:
        header = bytes((first, 0x80 | length))
    elif length < 65536:
        header = bytes((first, 0x80 | 126)) + struct.pack("!H", length)
    else:
        header = bytes((first, 0x80 | 127)) + struct.pack("!Q", length)
    mask = secrets.token_bytes(4)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return header + mask + masked


def _valid_websocket_handshake(header_text: str, key: str) -> bool:
    expected = base64.b64encode(
        hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
    ).decode("ascii")
    lower_header = header_text.lower()
    return " 101 " in header_text and f"sec-websocket-accept: {expected}".lower() in lower_header


class CdpClient:
    def __init__(self, sock: socket.socket, initial_data: bytes = b"") -> None:
        self._socket = sock
        self._buffer = bytearray(initial_data)
        self._next_id = 1
        self._pending: dict[int, queue.Queue[Any]] = {}
        self._waiters: dict[str, deque[queue.Queue[Any]]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._closed = threading.Event()
        self.on_event: Callable[[dict[str, Any]], None] = lambda event: None
        self._reader = threading.Thread(target=self._read_loop, name="cdp-reader", daemon=True)
        self._reader.start()

    @classmethod
    def connect(cls, websocket_url: str, timeout: float = 5.0) -> CdpClient:
        parsed = urlsplit(websocket_url)
        if parsed.scheme != "ws":
            raise ValueError(f"Unsupported CDP websocket scheme: {parsed.scheme}")
        port = parsed.port or 80
        sock = socket.create_connection((parsed.hostname or "127.0.0.1", port), timeout=timeout)
        sock.settimeout(None)
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        request = "\r\n".join((
            f"GET {target} HTTP/1.1",
            f"Host: {parsed.netloc}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
            "",
            "",
        )).encode("ascii")
        sock.sendall(request)
        response = bytearray()
        while b"\r\n\r\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("CDP websocket closed during handshake")
            response.extend(chunk)
        header, rest = bytes(response).split(b"\r\n\r\n", 1)
        header_text = header.decode("iso-8859-1")
        if not _valid_websocket_handshake(header_text, key):
            sock.close()
            raise ConnectionError(f"Bad websocket handshake: {header_text}")
        return cls(sock, rest)

    def send(self, method: str, params: dict[str, Any] | None = None, timeout: float = 5.0) -> Any:
        response_queue: queue.Queue[Any] = queue.Queue(maxsize=1)
        with self._lock:
            message_id = self._next_id
            self._next_id += 1
            self._pending[message_id] = response_queue
        payload = json.dumps({"id": message_id, "method": method, "params": params or {}}, separators=(",", ":")).encode("utf-8")
        with self._send_lock:
            self._socket.sendall(_encode_client_frame(payload))
        try:
            response = response_queue.get(timeout=timeout)
        except queue.Empty as error:
            with self._lock:
                self._pending.pop(message_id, None)
            raise TimeoutError(f"Timed out waiting for {method}") from error
        if isinstance(response, BaseException):
            raise response
        if "error" in response:
            raise RuntimeError(json.dumps(response["error"]))
        return response.get("result")

    def prepare_wait(self, method: str) -> queue.Queue[Any]:
        waiter: queue.Queue[Any] = queue.Queue(maxsize=1)
        with self._lock:
            self._waiters[method].append(waiter)
        return waiter

    def wait(self, method: str, waiter: queue.Queue[Any], timeout: float = 5.0) -> dict[str, Any]:
        try:
            result = waiter.get(timeout=timeout)
        except queue.Empty as error:
            with self._lock:
                try:
                    self._waiters[method].remove(waiter)
                except ValueError:
                    pass
            raise TimeoutError(f"Timed out waiting for {method}") from error
        if isinstance(result, BaseException):
            raise result
        return result

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        try:
            with self._send_lock:
                self._socket.sendall(_encode_client_frame(b"", opcode=8))
        except OSError:
            pass
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._socket.close()
        self._reader.join(timeout=1)

    def _read_loop(self) -> None:
        try:
            while not self._closed.is_set():
                opcode, payload = self._read_frame()
                if opcode == 8:
                    break
                if opcode == 9:
                    with self._send_lock:
                        self._socket.sendall(_encode_client_frame(payload, opcode=10))
                    continue
                if opcode != 1:
                    continue
                self._handle(json.loads(payload.decode("utf-8")))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            if not self._closed.is_set():
                self._fail_pending(error)
        finally:
            self._closed.set()

    def _read_exact(self, count: int) -> bytes:
        while len(self._buffer) < count:
            chunk = self._socket.recv(65536)
            if not chunk:
                raise ConnectionError("CDP websocket closed")
            self._buffer.extend(chunk)
        result = bytes(self._buffer[:count])
        del self._buffer[:count]
        return result

    def _read_frame(self) -> tuple[int, bytes]:
        first, second = self._read_exact(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        mask = self._read_exact(4) if second & 0x80 else None
        payload = self._read_exact(length)
        if mask:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return opcode, payload

    def _handle(self, message: dict[str, Any]) -> None:
        message_id = message.get("id")
        if message_id is not None:
            with self._lock:
                pending = self._pending.pop(message_id, None)
            if pending:
                pending.put(message)
            return
        method = message.get("method")
        if method:
            self.on_event(message)
            with self._lock:
                waiters = self._waiters.get(method)
                waiter = waiters.popleft() if waiters else None
            if waiter:
                waiter.put(message)

    def _fail_pending(self, error: BaseException) -> None:
        with self._lock:
            queues = list(self._pending.values())
            self._pending.clear()
            for waiters in self._waiters.values():
                queues.extend(waiters)
            self._waiters.clear()
        for pending in queues:
            pending.put(error)


def _navigate_and_wait(cdp: CdpClient, url: str) -> None:
    waiter = cdp.prepare_wait("Page.loadEventFired")
    cdp.send("Page.navigate", {"url": url})
    cdp.wait("Page.loadEventFired", waiter)


_PAGE_STATE_EXPRESSION = """(() => ({
  fundCount: document.querySelectorAll('#left-etf option').length,
  rowCount: document.querySelectorAll('#comparison-table [role=row]').length,
  explanationCount: document.querySelectorAll('#explanation-output li').length,
  sourceCount: document.querySelectorAll('#source-list a').length,
  validation: document.querySelector('#validation-message')?.textContent ?? null,
  heading: document.querySelector('#comparison-table [role=row]')?.textContent ?? null
}))()"""


def _evaluate(cdp: CdpClient, expression: str) -> Any:
    response = cdp.send("Runtime.evaluate", {"expression": expression, "returnByValue": True})
    if response.get("exceptionDetails"):
        raise RuntimeError(f"Browser evaluation failed: {response['exceptionDetails'].get('text', 'exception')}")
    return response.get("result", {}).get("value")


def _wait_for_page_state(cdp: CdpClient, timeout: float = 5.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        value = _evaluate(cdp, _PAGE_STATE_EXPRESSION)
        state = value if isinstance(value, dict) else {}
        if state.get("fundCount"):
            return state
        time.sleep(0.05)
    raise RuntimeError(f"Browser UI did not initialize: {state}")


def _exercise_page(cdp: CdpClient) -> list[str]:
    failures = page_state_failures(_wait_for_page_state(cdp))
    invalid = _evaluate(cdp, """(() => {
      const left = document.querySelector('#left-etf');
      left.value = document.querySelector('#right-etf').value;
      left.dispatchEvent(new Event('change'));
      return {
        validation: document.querySelector('#validation-message').textContent,
        rowCount: document.querySelectorAll('#comparison-table [role=row]').length,
        explanation: document.querySelector('#explanation-output').textContent
      };
    })()""")
    if invalid != {
        "validation": "Choose two distinct ETFs before comparing.",
        "rowCount": 0,
        "explanation": "Comparison unavailable until the selection is valid.",
    }:
        failures.append(f"Invalid-selection behavior mismatch: {invalid}")
    alternate = _evaluate(cdp, """(() => {
      const left = document.querySelector('#left-etf');
      left.value = 'VTI';
      left.dispatchEvent(new Event('change'));
      return {
        rowCount: document.querySelectorAll('#comparison-table [role=row]').length,
        heading: document.querySelector('#comparison-table [role=row]')?.textContent
      };
    })()""")
    if alternate != {"rowCount": 9, "heading": "FieldVTIQQQ"}:
        failures.append(f"Alternate-comparison behavior mismatch: {alternate}")
    return failures


def _remove_tree(path: Path) -> None:
    for attempt in range(6):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == 5:
                raise
            time.sleep(0.1)


def run_browser_check(config: BrowserConfig) -> list[str]:
    user_data_dir = Path(tempfile.mkdtemp(prefix=f"etf-console-check-{os.getpid()}-"))
    chrome: subprocess.Popen[bytes] | None = None
    cdp: CdpClient | None = None
    failures: list[str] = []
    try:
        chrome = subprocess.Popen(
            [
                str(config.chrome_path), "--headless=new", "--disable-gpu", "--no-first-run",
                "--no-default-browser-check", f"--remote-debugging-port={config.cdp_port}",
                f"--user-data-dir={user_data_dir}", "about:blank",
            ],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _wait_for_cdp(config.cdp_port)
        target = _request_json("PUT", f"/json/new?{quote('about:blank', safe='')}", config.cdp_port)
        cdp = CdpClient.connect(target["webSocketDebuggerUrl"])

        def capture(event: dict[str, Any]) -> None:
            failure = failure_for_event(event)
            if failure is not None:
                failures.append(failure)

        cdp.on_event = capture
        for domain in ("Log", "Runtime", "Page", "Network"):
            cdp.send(f"{domain}.enable")
        _navigate_and_wait(cdp, config.url)
        failures.extend(_exercise_page(cdp))
        _navigate_and_wait(cdp, config.url)
        failures.extend(page_state_failures(_wait_for_page_state(cdp)))
        return failures
    finally:
        if cdp is not None:
            cdp.close()
        if chrome is not None and chrome.poll() is None:
            chrome.terminate()
            try:
                chrome.wait(timeout=1)
            except subprocess.TimeoutExpired:
                chrome.kill()
                chrome.wait(timeout=2)
        _remove_tree(user_data_dir)


def browser_check_from_environment(
    *, url: str | None = None, chrome_path: str | Path | None = None, cdp_port: int | None = None
) -> int:
    config = BrowserConfig.from_environment(url=url, chrome_path=chrome_path, cdp_port=cdp_port)
    try:
        failures = run_browser_check(config)
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(
        "Live browser smoke passed for initial render, invalid selection, alternate comparison, "
        f"reload, and clean console/network logs: {config.url}"
    )
    return 0
