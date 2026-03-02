#!/usr/bin/env python3
"""DocLean Registry Client."""

import json
import urllib.request
from urllib.parse import urlencode


class RegistryClient:
    def __init__(self, base_url="http://localhost:8420"):
        self.base_url = base_url.rstrip("/")

    def _get(self, path, accept="application/json"):
        req = urllib.request.Request(f"{self.base_url}{path}", headers={"Accept": accept})
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode()
            if "json" in resp.headers.get("Content-Type", ""):
                return json.loads(data)
            return data

    def list(self):
        """List all available APIs."""
        return self._get("/v1/apis")

    def get(self, name, format=None):
        """Get a specific API spec. format: None, 'lean', or 'openapi'."""
        path = f"/v1/apis/{name}"
        if format:
            path += f"?format={format}"
        accept = "application/doclean+v1" if format == "lean" else "application/json"
        return self._get(path, accept)

    def search(self, query):
        """Search APIs by keyword."""
        return self._get(f"/v1/search?{urlencode({'q': query})}")

    def stats(self):
        """Get registry statistics."""
        return self._get("/v1/stats")


if __name__ == "__main__":
    c = RegistryClient()
    print("=== APIs ===")
    for api in c.list()["apis"]:
        print(f"  {api['name']:20s} v{api['version']:5s} {api['endpoints']} endpoints")
    print(f"\n=== Stats ===")
    print(json.dumps(c.stats(), indent=2))
    print(f"\n=== Search 'charge' ===")
    print(json.dumps(c.search("charge"), indent=2))
