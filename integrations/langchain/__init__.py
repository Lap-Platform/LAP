"""LangChain integration for LAP DocLean format."""
try:
    from .lap_loader import DocLeanLoader, DocLeanRetriever
except ImportError:
    pass
