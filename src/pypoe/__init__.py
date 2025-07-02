"""
PyPoe - Python client for Poe.com using the official API

This package provides a clean, async interface for interacting with Poe bots
including GPT-4, Claude, and more, with optional conversation history management.
"""

from .poe_client import PoeChatClient
from .config import Config, get_config

# Export HistoryManager if available
try:
    from .history_manager import HistoryManager
    __all__ = ["PoeChatClient", "Config", "get_config", "HistoryManager"]
except ImportError:
    __all__ = ["PoeChatClient", "Config", "get_config"]

__version__ = "2.0.0"