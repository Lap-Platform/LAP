"""LAP SDK -- Lean API Platform client library."""

from .client import LAPClient, LAPDoc, EndpointInfo
from .registry import Registry

__version__ = "0.3.0"
__all__ = ["LAPClient", "LAPDoc", "EndpointInfo", "Registry"]
