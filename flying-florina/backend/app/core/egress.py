"""OFFLINE_MODE egress guard.

When OFFLINE_MODE=true the backend process refuses outbound socket
connections and DNS lookups for anything but loopback. Blocked attempts are
counted and exposed through /api/demo/status so the offline test can prove
that no external call was attempted. This is a process-level guard for the
demo, not a substitute for host or network firewalls.
"""

from __future__ import annotations

import ipaddress
import socket
import threading
from typing import Any

_lock = threading.Lock()
_state: dict[str, Any] = {"installed": False, "blocked": [], "allowed_loopback": 0}
_orig_connect = socket.socket.connect
_orig_connect_ex = socket.socket.connect_ex
_orig_getaddrinfo = socket.getaddrinfo

LOCAL_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost", ""}


class EgressBlocked(OSError):
    pass


def _is_local_host(host: Any) -> bool:
    if host is None:
        return True
    h = host.decode() if isinstance(host, bytes) else str(host)
    if h.lower() in LOCAL_NAMES:
        return True
    try:
        return ipaddress.ip_address(h.split("%")[0]).is_loopback
    except ValueError:
        return False


def _record(target: str) -> None:
    with _lock:
        _state["blocked"].append(target)
        _state["blocked"] = _state["blocked"][-50:]


def _check(sock: socket.socket, address: Any) -> None:
    if sock.family == getattr(socket, "AF_UNIX", None):
        return
    host = address[0] if isinstance(address, tuple) else address
    if not _is_local_host(host):
        _record(f"{host}:{address[1] if isinstance(address, tuple) and len(address) > 1 else ''}")
        raise EgressBlocked(f"OFFLINE_MODE: outbound connection to {host} blocked")
    with _lock:
        _state["allowed_loopback"] += 1


def _connect(self: socket.socket, address: Any) -> Any:
    _check(self, address)
    return _orig_connect(self, address)


def _connect_ex(self: socket.socket, address: Any) -> Any:
    _check(self, address)
    return _orig_connect_ex(self, address)


def _getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
    if not _is_local_host(host):
        _record(f"dns:{host}")
        raise EgressBlocked(f"OFFLINE_MODE: DNS lookup for {host} blocked")
    return _orig_getaddrinfo(host, *args, **kwargs)


def install() -> None:
    with _lock:
        if _state["installed"]:
            return
        socket.socket.connect = _connect  # type: ignore[method-assign]
        socket.socket.connect_ex = _connect_ex  # type: ignore[method-assign]
        socket.getaddrinfo = _getaddrinfo  # type: ignore[assignment]
        _state["installed"] = True


def uninstall() -> None:
    with _lock:
        socket.socket.connect = _orig_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = _orig_connect_ex  # type: ignore[method-assign]
        socket.getaddrinfo = _orig_getaddrinfo  # type: ignore[assignment]
        _state["installed"] = False


def status() -> dict[str, Any]:
    with _lock:
        return {"installed": _state["installed"], "blocked_attempts": len(_state["blocked"]), "recent_blocked": list(_state["blocked"][-10:]),
                "loopback_connections": _state["allowed_loopback"]}
