"""LAN check for Sprint 0: can this machine reach the coordinator over the network?

Usage:
    python scripts/check_lan.py --host 127.0.0.1 --port 8000
    python scripts/check_lan.py --host 192.168.4.68 --port 8000   # from second PC

Checks: DNS/hostname resolution, TCP connect, HTTP /health (if reachable).
Exit 0 only if TCP connects AND /health returns HTTP 200.
"""

from __future__ import annotations

import argparse
import socket
import sys

import httpx


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Check LAN reachability of coordinator (Sprint 0)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--timeout", type=float, default=5.0)
    args = p.parse_args(argv)

    print(f"host={args.host} port={args.port}")
    try:
        resolved = socket.getaddrinfo(args.host, args.port, type=socket.SOCK_STREAM)
        print(f"resolve OK: {resolved[0][4]}")
    except socket.gaierror as exc:
        print(f"resolve FAILED: {exc}")
        return 1

    try:
        with socket.create_connection((args.host, args.port), timeout=args.timeout):
            print("tcp connect OK")
    except OSError as exc:
        print(f"tcp connect FAILED: {exc}")
        print("hint: start coordinator with --host 0.0.0.0 and allow Windows firewall TCP inbound on this port (LAN only, Sprint 0).")
        return 1

    url = f"http://{args.host}:{args.port}/health"
    try:
        resp = httpx.get(url, timeout=args.timeout)
        print(f"GET {url} -> {resp.status_code} {resp.text[:200]}")
        return 0 if resp.status_code == 200 else 1
    except Exception as exc:  # noqa: BLE001
        print(f"HTTP /health FAILED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
