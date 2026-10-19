"""Serve the static onboarding website (Sprint 36).

No build step, no dependencies: plain HTTP static server for `apps/website/`.
The site's workload catalog and dashboard/download links are configurable at
runtime (query params `?api=` / `?dashboard=` / `?download=`, or the on-page
coordinator URL, remembered in localStorage).

Usage:
    python scripts/serve_website.py                 # http://127.0.0.1:8080
    python scripts/serve_website.py --port 9000
"""

from __future__ import annotations

import argparse
import functools
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "apps" / "website"


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve apps/website (Sprint 36)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(WEB_ROOT))
    httpd = HTTPServer((args.host, args.port), handler)
    print(f"serving {WEB_ROOT} at http://{args.host}:{args.port}/  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
