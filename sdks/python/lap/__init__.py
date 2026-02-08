"""LAP SDK — LeanAgent Protocol client library."""

from .client import LAPClient, DocLeanDoc, EndpointInfo
from .registry import Registry

__version__ = "0.1.0"
__all__ = ["LAPClient", "DocLeanDoc", "EndpointInfo", "Registry"]
