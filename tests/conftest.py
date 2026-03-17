"""
Pytest configuration — skip network tests when offline.
"""
import socket
import pytest


def _has_network() -> bool:
    try:
        socket.setdefaulttimeout(2)
        socket.getaddrinfo("openapi.blofin.com", 443)
        return True
    except OSError:
        return False


NETWORK_AVAILABLE = _has_network()

requires_network = pytest.mark.skipif(
    not NETWORK_AVAILABLE,
    reason="BloFin API unreachable — skipped (no network)",
)
