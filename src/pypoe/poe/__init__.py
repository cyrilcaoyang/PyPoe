"""
PyPoe Core Module

Contains the main POE client, history management, and database functionality.
"""

from .client import PoeChatClient

# Use the main HistoryManager from manager.py (the more comprehensive one)
from .manager import HistoryManager

# Import the simple HistoryManager from history.py as well for web interface
from .history import HistoryManager as SimpleHistoryManager

__all__ = ["PoeChatClient", "HistoryManager", "SimpleHistoryManager"] 