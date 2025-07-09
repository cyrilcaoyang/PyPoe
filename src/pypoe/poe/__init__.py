"""
PyPoe Core Module

Contains the main POE client, history management, and database functionality.
"""

from .client import PoeChatClient

# Use the EnhancedHistoryManager as the primary HistoryManager (supports media and enhanced features)
try:
    from .enhanced_history import EnhancedHistoryManager as HistoryManager
except ImportError:
    # Fallback to comprehensive HistoryManager from manager.py
    from .manager import HistoryManager

# Import alternative history managers for compatibility
from .history import HistoryManager as SimpleHistoryManager
try:
    from .manager import HistoryManager as BasicHistoryManager
except ImportError:
    BasicHistoryManager = SimpleHistoryManager

__all__ = ["PoeChatClient", "HistoryManager", "SimpleHistoryManager", "BasicHistoryManager"] 