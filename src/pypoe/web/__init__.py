"""
PyPoe Web Interface Module

Contains the FastAPI web application and related components.
"""

# Check if web dependencies are available
try:
    import fastapi
    import jinja2
    WEB_AVAILABLE = True
    
    from .app import WebApp, create_app, run_server
    __all__ = ["WebApp", "create_app", "run_server", "WEB_AVAILABLE"]
    
except ImportError:
    WEB_AVAILABLE = False
    __all__ = ["WEB_AVAILABLE"] 