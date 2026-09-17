"""Static server for web/ plus one live endpoint: POST /api/company adds a company on stage."""
from __future__ import annotations

import json
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import build as buildmod
from .collect import add_to_pool, collect_one


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(Path("web").resolve()), **kw)

    def log_message(self, fmt, *args):  # quieter
        if "/api/" in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def do_POST(self):
        if self.path != "/api/company":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        domain = (body.get("domain") or "").strip().lower()
        if not domain:
            self._json(400, {"error": "domain required"})
            return
        try:
            add_to_pool(domain, body.get("name"))
            collect_one({"domain": domain, "name": body.get("name")})
            data = buildmod.build(buildmod.load_signals(), date.today(), synthetic=False, use_llm=body.get("llm", True))
            buildmod.write_build(data)
            company = next((c for c in data["companies"] if c["domain"] == domain), None)
            self._json(200, {"ok": True, "company": company, "meta": data["meta"]})
        except Exception as exc:
            self._json(500, {"error": str(exc)[:500]})

    def _json(self, code: int, payload: dict):
        raw = json.dumps(payload, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def serve(port: int = 8765) -> None:
    print(f"Mirror at http://localhost:{port}  (ctrl-c to stop)")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
