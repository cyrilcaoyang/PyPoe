"""
PyPoe Web Interface

FastAPI-based web interface for PyPoe.
Requires fastapi, uvicorn, jinja2, and python-multipart.
"""

try:
    from .app import create_app
    from .runner import run_server
    WEB_AVAILABLE = True
except ImportError as e:
    WEB_AVAILABLE = False
    def create_app(*args, **kwargs):
        raise ImportError(
            f"Web interface dependencies missing: {e}. "
            "Install with: pip install pypoe[web-ui]"
        )
    def run_server(*args, **kwargs):
        raise ImportError(
            f"Web interface dependencies missing: {e}. "
            "Install with: pip install pypoe[web-ui]"
        )

__all__ = ['create_app', 'run_server', 'WEB_AVAILABLE'] 