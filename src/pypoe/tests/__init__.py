"""
PyPoe Tests Package

Contains test suites for PyPoe functionality.
These tests are included only with the [dev] installation flag.

Available test modules:
- test_client.py: Core client functionality tests
- test_integrations.py: Integration tests for interfaces
- test_bot_locking.py: Bot interaction and locking tests
- test_chat_scrolling.py: Web interface scrolling tests
- test_conf.py: Test configuration utilities

Usage:
    pytest src/pypoe/tests/
    python -m pytest src/pypoe/tests/
    python -m pypoe.tests.test_client
"""

import os
from pathlib import Path

# Get the tests directory path
TESTS_DIR = Path(__file__).parent

def list_test_files():
    """List all available test files."""
    tests = []
    for file in TESTS_DIR.glob("test_*.py"):
        tests.append(file.name)
    return sorted(tests)

def get_test_path(test_name):
    """Get the full path to a test file."""
    if not test_name.endswith('.py'):
        test_name += '.py'
    return TESTS_DIR / test_name

__all__ = ['TESTS_DIR', 'list_test_files', 'get_test_path'] 