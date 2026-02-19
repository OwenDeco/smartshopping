#!/usr/bin/env python3
"""Local server for SmartShopping.

- Serves static files.
- Adds POST /api/scrape endpoint to refresh `data/prices.json` by running scraper.
"""

from __future__ import annotations

import json
import subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "prices.json"
SCRAPER_FILE = ROOT / "scripts" / "scrape_prices.py"


class SmartShoppingHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/scrape":
            self.send_error(404, "Not found")
            return

        result = subprocess.run(
            ["python", str(SCRAPER_FILE)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

        if not DATA_FILE.exists():
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Dataset not found"}).encode("utf-8"))
            return

        products = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        payload = {
            "ok": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "products": products,
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))


def main() -> None:
    host = "0.0.0.0"
    port = 8080
    server = ThreadingHTTPServer((host, port), SmartShoppingHandler)
    print(f"Serving SmartShopping on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
