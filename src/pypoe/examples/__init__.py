"""
PyPoe Examples Package

Contains example scripts and demonstrations of PyPoe functionality.
These examples are included in the default installation to help users get started.

Available examples:
- basic_usage.py: Basic CLI usage examples
- demo_web_history.py: Web history interface demonstration  
- demo_scroll_test.py: Scrolling functionality demonstration
- debug_scrolling.py: Debugging tools for scrolling issues
- web_sample.py: Web interface sample implementation
"""

import os
from pathlib import Path

# Get the examples directory path
EXAMPLES_DIR = Path(__file__).parent

def list_examples():
    """List all available example scripts."""
    examples = []
    for file in EXAMPLES_DIR.glob("*.py"):
        if file.name != "__init__.py":
            examples.append(file.name)
    return sorted(examples)

def get_example_path(example_name):
    """Get the full path to an example script."""
    if not example_name.endswith('.py'):
        example_name += '.py'
    return EXAMPLES_DIR / example_name

__all__ = ['EXAMPLES_DIR', 'list_examples', 'get_example_path'] 