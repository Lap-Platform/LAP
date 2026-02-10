"""LAP middleware for LangChain integration."""

from .client import LAPClient

try:
    from langchain.schema import Document
    from langchain.document_loaders.base import BaseLoader
    _HAS_LANGCHAIN = True
except ImportError:
    _HAS_LANGCHAIN = False

    class Document:
        def __init__(self, page_content="", metadata=None):
            self.page_content = page_content
            self.metadata = metadata or {}

    class BaseLoader:
        def load(self):
            raise NotImplementedError


class LAPDocLoader(BaseLoader):
    """LangChain-compatible document loader for LAP files."""

    def __init__(self, path: str, lean: bool = True):
        self.path = path
        self.lean = lean
        self._client = LAPClient()

    def load(self):
        """Load LAP file as LangChain Document objects."""
        doc = self._client.load(self.path)
        documents = []

        # One document per endpoint
        for ep in doc.endpoints:
            content = f"{ep.method} {ep.path}"
            if ep.summary:
                content += f"\n{ep.summary}"
            if ep.required_params:
                params = ", ".join(f"{p.name}: {p.type}" for p in ep.required_params)
                content += f"\nRequired: {params}"
            if ep.optional_params:
                params = ", ".join(f"{p.name}: {p.type}" for p in ep.optional_params)
                content += f"\nOptional: {params}"

            documents.append(Document(
                page_content=content,
                metadata={
                    "source": self.path,
                    "api": doc.api_name,
                    "method": ep.method,
                    "path": ep.path,
                },
            ))

        return documents

    def load_full(self):
        """Load as a single document with full context."""
        doc = self._client.load(self.path)
        return [Document(
            page_content=doc.to_context(lean=self.lean),
            metadata={"source": self.path, "api": doc.api_name},
        )]
