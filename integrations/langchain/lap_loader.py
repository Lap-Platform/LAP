"""
LangChain Document Loader for LAP API specs.

Loads LAP files as LangChain Documents — one per endpoint —
enabling RAG pipelines over API documentation with massive token savings.

Example usage:
    >>> from integrations.langchain.lap_loader import LAPLoader
    >>> loader = LAPLoader("examples/lap/openapi/petstore.lap")
    >>> docs = loader.load()
    >>> print(docs[0].page_content)
    '@endpoint GET /repos/{owner}/{repo}\\n@desc Get a repository...'
    >>> print(docs[0].metadata)
    {'api': 'GitHub', 'method': 'GET', 'path': '/repos/{owner}/{repo}', 'params_count': 3}

    # Retriever usage:
    >>> retriever = LAPRetriever("examples/lap/openapi/petstore.lap")
    >>> results = retriever.get_relevant_documents("list repositories")
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

# Add src to path for imports
_src = str(Path(__file__).resolve().parent.parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from core.formats.lap import LAPSpec, Endpoint
from core.parser import parse_lap
from core.utils import read_file_safe

# Graceful degradation — works without LangChain installed
try:
    from langchain.document_loaders import BaseLoader
    from langchain.schema import Document
    from langchain.schema.retriever import BaseRetriever
    _HAS_LANGCHAIN = True
except ImportError:
    # Provide stubs so the module is importable without langchain
    class BaseLoader:  # type: ignore[no-redef]
        """Stub for langchain.document_loaders.BaseLoader."""
        def load(self) -> list:
            raise NotImplementedError

    class Document:  # type: ignore[no-redef]
        """Stub for langchain.schema.Document."""
        def __init__(self, page_content: str = "", metadata: dict = None):
            self.page_content = page_content
            self.metadata = metadata or {}

        def __repr__(self) -> str:
            return f"Document(metadata={self.metadata}, content={self.page_content[:80]}...)"

    class BaseRetriever:  # type: ignore[no-redef]
        """Stub for langchain.schema.retriever.BaseRetriever."""
        pass

    _HAS_LANGCHAIN = False


def _endpoint_to_document(endpoint: Endpoint, api_name: str, lean: bool = False) -> Document:
    """Convert a single Endpoint to a LangChain Document."""
    content = endpoint.to_lap(lean=lean)
    params_count = (
        len(endpoint.required_params)
        + len(endpoint.optional_params)
        + len(endpoint.request_body)
    )
    metadata = {
        "api": api_name,
        "method": endpoint.method.upper(),
        "path": endpoint.path,
        "params_count": params_count,
    }
    if endpoint.summary:
        metadata["summary"] = endpoint.summary
    return Document(page_content=content, metadata=metadata)


class LAPLoader(BaseLoader):
    """Load LAP API specs as LangChain documents.

    Each endpoint in the spec becomes a separate Document with:
    - page_content: The LAP text for that endpoint
    - metadata: {api, method, path, params_count, summary}

    Args:
        path: Path to a .lap file
        lean: If True, strip descriptions for maximum compression
        spec: Alternatively, pass an already-parsed LAPSpec directly
    """

    def __init__(self, path: str = None, lean: bool = False, spec: LAPSpec = None):
        self.path = path
        self.lean = lean
        self._spec = spec

    def _get_spec(self) -> LAPSpec:
        if self._spec:
            return self._spec
        if not self.path:
            raise ValueError("Either path or spec must be provided")
        text = read_file_safe(self.path)
        if text is None:
            raise FileNotFoundError(f"Cannot read LAP file: {self.path}")
        return parse_lap(text)

    def load(self) -> List[Document]:
        """Load and return one Document per endpoint."""
        spec = self._get_spec()
        return [
            _endpoint_to_document(ep, spec.api_name, lean=self.lean)
            for ep in spec.endpoints
        ]


class LAPRetriever:
    """Simple keyword-based retriever for LAP endpoints.

    Searches endpoint paths, summaries, and parameter names for keyword matches.
    For production use, wrap with a proper vector store retriever.

    Example:
        >>> retriever = LAPRetriever("examples/lap/openapi/petstore.lap")
        >>> docs = retriever.get_relevant_documents("create issue")
        >>> print(docs[0].metadata['path'])
        '/repos/{owner}/{repo}/issues'
    """

    def __init__(self, path: str = None, lean: bool = False, spec: LAPSpec = None):
        loader = LAPLoader(path=path, lean=lean, spec=spec)
        self._documents = loader.load()
        self._spec = loader._get_spec()

    def get_relevant_documents(self, query: str, top_k: int = 5) -> List[Document]:
        """Return documents matching the query by keyword scoring."""
        query_terms = query.lower().split()
        scored = []
        for doc in self._documents:
            score = 0
            searchable = (
                doc.metadata.get("path", "").lower()
                + " " + doc.metadata.get("summary", "").lower()
                + " " + doc.metadata.get("method", "").lower()
                + " " + doc.page_content.lower()
            )
            for term in query_terms:
                if term in searchable:
                    score += 1
                    # Bonus for path match
                    if term in doc.metadata.get("path", "").lower():
                        score += 2
                    # Bonus for summary match
                    if term in doc.metadata.get("summary", "").lower():
                        score += 1
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    async def aget_relevant_documents(self, query: str, top_k: int = 5) -> List[Document]:
        """Async version — just wraps sync since we're doing in-memory search."""
        return self.get_relevant_documents(query, top_k)
