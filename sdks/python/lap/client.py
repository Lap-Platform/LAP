"""LAP Client — load and query LAP documents."""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# Allow importing from the existing src/ modules
_src_path = str(Path(__file__).resolve().parents[3] / "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from core.formats.lap import LAPSpec, Endpoint, Param, ResponseSchema, ErrorSchema, ResponseField
from core.parser import parse_lap
from core.utils import count_tokens as _count_tokens, get_tiktoken_encoding


@dataclass
class EndpointInfo:
    """Structured endpoint data returned by LAPDoc.get_endpoint()."""
    method: str
    path: str
    summary: str
    required_params: List[Param]
    optional_params: List[Param]
    request_body: List[Param]
    response_schemas: List[ResponseSchema]
    error_schemas: List[ErrorSchema]

    @property
    def response_schema(self) -> Optional[ResponseSchema]:
        """Primary (first) response schema."""
        return self.response_schemas[0] if self.response_schemas else None


class LAPDoc:
    """A loaded LAP document with query and formatting methods."""

    def __init__(self, spec: LAPSpec, raw_text: str):
        self._spec = spec
        self._raw = raw_text

    @property
    def api_name(self) -> str:
        return self._spec.api_name

    @property
    def base_url(self) -> str:
        return self._spec.base_url

    @property
    def version(self) -> str:
        return self._spec.version

    @property
    def endpoints(self) -> List[EndpointInfo]:
        return [self._wrap_endpoint(ep) for ep in self._spec.endpoints]

    def _wrap_endpoint(self, ep: Endpoint) -> EndpointInfo:
        return EndpointInfo(
            method=ep.method.upper(),
            path=ep.path,
            summary=ep.summary,
            required_params=ep.required_params,
            optional_params=ep.optional_params,
            request_body=ep.request_body,
            response_schemas=ep.response_schemas,
            error_schemas=ep.error_schemas,
        )

    def get_endpoint(self, method: str, path: str) -> Optional[EndpointInfo]:
        """Find an endpoint by method and path."""
        method = method.upper()
        for ep in self._spec.endpoints:
            if ep.method.upper() == method and ep.path == path:
                return self._wrap_endpoint(ep)
        return None

    def to_context(self, lean: bool = False) -> str:
        """Format for LLM context injection."""
        return self._spec.to_lap(lean=lean)

    def token_count(self, lean: bool = False) -> int:
        """Count tokens using tiktoken (falls back to char estimate)."""
        text = self.to_context(lean=lean)
        return _count_tokens(text)


class LAPClient:
    """Main LAP client for loading LAP documents."""

    def load(self, path: str) -> LAPDoc:
        """Load a .lap file and return a queryable document."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"LAP file not found: {path}")
        raw = p.read_text()
        spec = parse_lap(raw)
        return LAPDoc(spec, raw)
