"""LAP Registry — discover and search LAP files."""

from pathlib import Path
from typing import List, Optional

from .client import LAPClient, LAPDoc


class Registry:
    """Local registry of LAP files."""

    def __init__(self, directory: str):
        self._dir = Path(directory)
        self._client = LAPClient()

    def list(self) -> List[str]:
        """List all available LAP document names."""
        return sorted(
            p.stem.replace(".lean", "")
            for p in self._dir.glob("*.lap")
        )

    def get(self, name: str) -> Optional[LAPDoc]:
        """Get a LAP doc by name (exact or partial match)."""
        # Try exact match first
        for pattern in [f"{name}.lap", f"{name}.lean.lap"]:
            p = self._dir / pattern
            if p.exists():
                return self._client.load(str(p))

        # Partial match
        for p in self._dir.glob("*.lap"):
            if name.lower() in p.stem.lower():
                return self._client.load(str(p))

        return None

    def search(self, query: str) -> List[LAPDoc]:
        """Fuzzy search across all LAP files."""
        query = query.lower()
        results = []
        for p in sorted(self._dir.glob("*.lap")):
            # Check filename
            if query in p.stem.lower():
                results.append(self._client.load(str(p)))
                continue
            # Check file content
            content = p.read_text()[:500].lower()
            if query in content:
                results.append(self._client.load(str(p)))

        return results
