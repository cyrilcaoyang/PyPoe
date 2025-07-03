"""
PyPoe - Python client for Poe.com using the official API

This package provides a clean, async interface for interacting with Poe bots
including GPT-4, Claude, and more, with optional conversation history management.
"""

from .config import Config, get_config

# Core POE functionality (always available)
from .poe import PoeChatClient, HistoryManager

__all__ = ["Config", "get_config", "PoeChatClient", "HistoryManager"]

# Web interface (optional)
try:
    from .web import WebApp, create_app, run_server, WEB_AVAILABLE
    __all__.extend(["WebApp", "create_app", "run_server", "WEB_AVAILABLE"])
except ImportError:
    pass

# Slack bot (optional)
try:
    from .slack import PyPoeSlackBot, SLACK_AVAILABLE
    __all__.extend(["PyPoeSlackBot", "SLACK_AVAILABLE"])
except ImportError:
    pass

__version__ = "2.0.0"