"""
CrewAI Tool for LAP API lookup.

Provides a CrewAI-compatible tool that agents can use to search and retrieve
API documentation in LAP format — compressed and agent-optimized.

Example usage:
    >>> from crewai import Agent, Task, Crew
    >>> from integrations.crewai.lap_tool import LAPLookup
    >>>
    >>> tool = LAPLookup(specs_dir="examples/lap/openapi/")
    >>> agent = Agent(
    ...     role="API Developer",
    ...     tools=[tool],
    ...     goal="Find the right API endpoint"
    ... )

Without CrewAI installed (standalone):
    >>> tool = LAPLookup(specs_dir="examples/lap/openapi/")
    >>> result = tool._run("github", endpoint="repos")
    >>> print(result)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Type

_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from lap.core.formats.lap import LAPSpec
from lap.core.parser import parse_lap
from lap.core.utils import read_file_safe

# Graceful degradation
try:
    from crewai.tools import BaseTool
    from pydantic import BaseModel, Field
    _HAS_CREWAI = True
except ImportError:
    # Stubs
    class BaseModel:  # type: ignore[no-redef]
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class Field:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            pass
        def __call__(self, *args, **kwargs):
            return None

    class BaseTool:  # type: ignore[no-redef]
        name: str = ""
        description: str = ""
        def _run(self, *args, **kwargs) -> str:
            raise NotImplementedError

    _HAS_CREWAI = False


class LAPLookupInput(BaseModel):
    """Input schema for LAPLookup tool."""
    api_name: str
    endpoint: Optional[str] = None


class LAPLookup(BaseTool):
    """Look up API documentation in LAP format.

    Searches loaded LAP specs by API name and optionally filters
    by endpoint path. Returns compressed API documentation optimized
    for LLM consumption.
    """

    name: str = "api_lookup"
    description: str = (
        "Look up API documentation in LAP format. "
        "Provide an api_name to get the full spec, or also provide "
        "an endpoint keyword to filter specific endpoints."
    )

    def __init__(self, specs_dir: str = None, specs: dict[str, LAPSpec] = None, **kwargs):
        if _HAS_CREWAI:
            super().__init__(**kwargs)
        self._specs: dict[str, LAPSpec] = specs or {}
        if specs_dir:
            self._load_specs_dir(specs_dir)

    def _load_specs_dir(self, specs_dir: str) -> None:
        """Load all .lap files from a directory."""
        p = Path(specs_dir)
        if not p.exists():
            return
        for f in p.glob("*.lap"):
            text = read_file_safe(str(f))
            if text:
                spec = parse_lap(text)
                key = spec.api_name.lower().replace(" ", "-") if spec.api_name else f.stem
                self._specs[key] = spec

    def add_spec(self, name: str, spec: LAPSpec) -> None:
        """Register a LAPSpec by name."""
        self._specs[name.lower()] = spec

    def _run(self, api_name: str, endpoint: str = None) -> str:
        """Look up API documentation.

        Args:
            api_name: Name of the API to look up (case-insensitive, fuzzy matched)
            endpoint: Optional endpoint keyword to filter (e.g., "repos", "issues")

        Returns:
            LAP formatted documentation string
        """
        api_key = api_name.lower().strip()

        # Exact match first
        spec = self._specs.get(api_key)

        # Fuzzy match
        if not spec:
            for key, s in self._specs.items():
                if api_key in key or api_key in s.api_name.lower():
                    spec = s
                    break

        if not spec:
            available = ", ".join(self._specs.keys()) if self._specs else "none"
            return f"API '{api_name}' not found. Available: {available}"

        if endpoint:
            # Filter endpoints matching the keyword
            keyword = endpoint.lower()
            matching = [
                ep for ep in spec.endpoints
                if keyword in ep.path.lower()
                or keyword in (ep.summary or "").lower()
                or keyword in ep.method.lower()
            ]
            if not matching:
                paths = [f"{ep.method.upper()} {ep.path}" for ep in spec.endpoints]
                return (
                    f"No endpoints matching '{endpoint}' in {spec.api_name}. "
                    f"Available: {'; '.join(paths[:10])}"
                )
            # Build filtered output
            lines = [f"@api {spec.api_name}", f"@base {spec.base_url}", ""]
            for ep in matching:
                lines.append(ep.to_lap())
                lines.append("")
            return "\n".join(lines)

        return spec.to_lap()
