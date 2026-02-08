#!/usr/bin/env python3
"""DocLean Registry Server — lightweight API serving DocLean specs."""

import json
import os
import re
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get("DOCLEAN_PORT", 8420))
OUTPUT_DIR = Path(os.environ.get("DOCLEAN_OUTPUT", Path(__file__).resolve().parent.parent / "output"))


def _parse_spec(text: str) -> dict:
    """Extract metadata from a .doclean file."""
    meta = {}
    for line in text.splitlines():
        if m := re.match(r"^@api\s+(.+)", line):
            meta["description"] = m.group(1).strip()
        elif m := re.match(r"^@version\s+(.+)", line):
            meta["version"] = m.group(1).strip()
        elif m := re.match(r"^@base\s+(.+)", line):
            meta["base_url"] = m.group(1).strip()
    meta["endpoints"] = len(re.findall(r"^@endpoint\s+", text, re.MULTILINE))
    return meta


def _load_specs() -> dict:
    """Load all specs from OUTPUT_DIR. Returns {name: {meta, text, lean_text, ...}}."""
    specs = {}
    if not OUTPUT_DIR.exists():
        return specs
    for f in sorted(OUTPUT_DIR.glob("*.doclean")):
        stem = f.stem
        if stem.endswith(".lean"):
            continue  # handled below
        name = stem
        text = f.read_text()
        meta = _parse_spec(text)
        lean_path = OUTPUT_DIR / f"{name}.lean.doclean"
        lean_text = lean_path.read_text() if lean_path.exists() else None
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat()
        specs[name] = {
            "name": name,
            "description": meta.get("description", name),
            "version": meta.get("version", "unknown"),
            "base_url": meta.get("base_url", ""),
            "endpoints": meta.get("endpoints", 0),
            "last_updated": mtime,
            "size": len(text),
            "lean_size": len(lean_text) if lean_text else None,
            "_text": text,
            "_lean_text": lean_text,
        }
    return specs


class RegistryHandler(BaseHTTPRequestHandler):
    specs: dict = {}

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Accept, Content-Type")

    def _json(self, data, status=200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, text, ct="text/plain", status=200):
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", ct)
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _404(self, msg="Not found"):
        self._json({"error": msg}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)
        accept = self.headers.get("Accept", "")

        if path == "/v1/apis":
            items = []
            for s in self.specs.values():
                items.append({k: v for k, v in s.items() if not k.startswith("_")})
            return self._json({"apis": items, "count": len(items)})

        if m := re.match(r"^/v1/apis/([^/]+)$", path):
            name = m.group(1)
            spec = self.specs.get(name)
            if not spec:
                return self._404(f"API '{name}' not found")

            fmt = qs.get("format", [None])[0]

            if fmt == "lean" or "doclean" in accept:
                text = spec["_lean_text"] or spec["_text"]
                return self._text(text, "application/doclean+v1")
            if fmt == "openapi":
                # Best-effort: return JSON metadata (full conversion would need the converter module)
                return self._json({
                    "note": "OpenAPI conversion — returning structured metadata",
                    "name": spec["name"],
                    "description": spec["description"],
                    "version": spec["version"],
                    "base_url": spec["base_url"],
                    "endpoints": spec["endpoints"],
                    "raw": spec["_text"],
                })
            if "application/json" in accept:
                return self._json({k: v for k, v in spec.items() if not k.startswith("_")})
            # Default: return doclean text
            return self._text(spec["_text"], "application/doclean+v1")

        if path == "/v1/search":
            q = qs.get("q", [""])[0].lower()
            if not q:
                return self._json({"error": "Missing ?q= parameter"}, 400)
            results = []
            for s in self.specs.values():
                if q in s["name"].lower() or q in s["description"].lower() or q in s["_text"].lower():
                    results.append({k: v for k, v in s.items() if not k.startswith("_")})
            return self._json({"query": q, "results": results, "count": len(results)})

        if path == "/v1/stats":
            total_apis = len(self.specs)
            total_endpoints = sum(s["endpoints"] for s in self.specs.values())
            ratios = []
            for s in self.specs.values():
                if s["lean_size"] and s["size"]:
                    ratios.append(s["lean_size"] / s["size"])
            avg_ratio = sum(ratios) / len(ratios) if ratios else 0
            return self._json({
                "total_apis": total_apis,
                "total_endpoints": total_endpoints,
                "avg_compression_ratio": round(avg_ratio, 3),
                "avg_size_reduction": f"{round((1 - avg_ratio) * 100, 1)}%",
            })

        if path == "" or path == "/":
            return self._json({
                "service": "DocLean Registry",
                "version": "0.1.0",
                "endpoints": ["/v1/apis", "/v1/apis/{name}", "/v1/search?q=", "/v1/stats"],
            })

        self._404()

    def log_message(self, format, *args):
        sys.stderr.write(f"[registry] {args[0]}\n")


def serve(port=PORT):
    RegistryHandler.specs = _load_specs()
    print(f"DocLean Registry serving {len(RegistryHandler.specs)} APIs on :{port}")
    print(f"  Output dir: {OUTPUT_DIR}")
    httpd = HTTPServer(("0.0.0.0", port), RegistryHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        httpd.server_close()


if __name__ == "__main__":
    serve()
