"""LangChain integration for LAP LAP format."""
try:
    from .lap_loader import LAPLoader, LAPRetriever
except ImportError:
    pass
