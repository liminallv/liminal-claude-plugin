import json
import socket
import uuid
from pathlib import Path

from .discovery import choose_session, NoSession

DEFAULT_TIMEOUT = 30.0


class BridgeUnreachable(RuntimeError):
    pass


class BridgeFailure(RuntimeError):
    def __init__(self, message: str, traceback: str = ""):
        super().__init__(message)
        self.traceback = traceback


class BridgeClient:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.pinned_pid: int | None = None
        self._session: dict | None = None

    def pin(self, pid: int | None) -> None:
        self.pinned_pid = pid
        self._session = None

    def session(self) -> dict:
        if self._session is None:
            self._session = choose_session(self.project_root, self.pinned_pid)
        return self._session

    def _request(self, message: dict, timeout: float) -> dict:
        session = self.session()
        host, port = session.get("host", "127.0.0.1"), int(session["port"])
        try:
            sock = socket.create_connection((host, port), timeout=timeout + 2.0)
        except OSError as e:
            self._session = None
            raise BridgeUnreachable(
                f"Blender (pid {session.get('pid')}) stopped answering on port {port}: {e}. "
                "If it is still open, toggle the bridge in the LM Bridge panel; otherwise start it again."
            ) from e
        try:
            sock.sendall((json.dumps(message) + "\n").encode("utf-8"))
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(65536)
                if not chunk:
                    raise BridgeUnreachable("Blender closed the connection before replying.")
                buf += chunk
        except (OSError, socket.timeout) as e:
            raise BridgeUnreachable(f"Request to Blender failed: {e}") from e
        finally:
            sock.close()
        return json.loads(buf.split(b"\n", 1)[0].decode("utf-8"))

    def call(self, method: str, timeout: float = DEFAULT_TIMEOUT, **params):
        reply = self._request(
            {"type": "call", "id": str(uuid.uuid4()), "method": method, "params": params, "timeout": timeout},
            timeout,
        )
        if reply.get("type") == "error":
            raise BridgeFailure(reply.get("message", "unknown error"), reply.get("traceback", ""))
        return reply.get("value")

    def exec(self, code: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
        reply = self._request({"type": "exec", "id": str(uuid.uuid4()), "code": code, "timeout": timeout}, timeout)
        if reply.get("type") == "error":
            raise BridgeFailure(reply.get("message", "unknown error"), reply.get("traceback", ""))
        return reply

    def eval(self, code: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
        reply = self._request({"type": "eval", "id": str(uuid.uuid4()), "code": code, "timeout": timeout}, timeout)
        if reply.get("type") == "error":
            raise BridgeFailure(reply.get("message", "unknown error"), reply.get("traceback", ""))
        return reply

    def health(self) -> dict:
        return self._request({"type": "health"}, 5.0)

    def log(self) -> list[str]:
        reply = self._request({"type": "get_log"}, 10.0)
        if reply.get("type") == "error":
            raise BridgeFailure(reply.get("message", "unknown error"))
        return list(reply.get("lines", []))


__all__ = ["BridgeClient", "BridgeUnreachable", "BridgeFailure", "NoSession"]
