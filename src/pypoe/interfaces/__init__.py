"""
PyPoe Interfaces Package

Provides web and slack interfaces for PyPoe.
These interfaces require additional dependencies to function.
"""

# Web interface - requires web-ui dependencies
from .web import WEB_AVAILABLE, create_app as create_web_app, run_server as run_web_server

# Slack interface - requires web-ui dependencies (includes slack deps)
from . import slack

__all__ = [
    'create_web_app', 'run_web_server', 'WEB_AVAILABLE',
    'slack'
] 