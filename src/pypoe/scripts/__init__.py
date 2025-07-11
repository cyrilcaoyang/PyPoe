"""
PyPoe Scripts Package

Contains utility scripts, setup tools, and maintenance utilities.
These scripts are included in the default installation to help users configure and maintain PyPoe.

Available script categories:
- setup/: Configuration and deployment scripts
- utils/: Maintenance and troubleshooting utilities
- history/: User conversation history (created at runtime)
"""

import os
from pathlib import Path

# Get the scripts directory path
SCRIPTS_DIR = Path(__file__).parent

def list_setup_scripts():
    """List all available setup scripts."""
    setup_dir = SCRIPTS_DIR / "setup"
    if not setup_dir.exists():
        return []
    
    scripts = []
    for file in setup_dir.glob("*.py"):
        scripts.append(file.name)
    return sorted(scripts)

def list_utility_scripts():
    """List all available utility scripts."""
    utils_dir = SCRIPTS_DIR / "utils"
    if not utils_dir.exists():
        return []
    
    scripts = []
    for file in utils_dir.glob("*.py"):
        scripts.append(file.name)
    return sorted(scripts)

def get_script_path(category, script_name):
    """Get the full path to a script in a specific category."""
    if not script_name.endswith('.py'):
        script_name += '.py'
    return SCRIPTS_DIR / category / script_name

__all__ = ['SCRIPTS_DIR', 'list_setup_scripts', 'list_utility_scripts', 'get_script_path'] 