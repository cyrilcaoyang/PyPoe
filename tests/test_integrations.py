"""
Tests for PyPoe optional integrations.
"""
import pytest
from unittest.mock import patch

def test_slack_bot_import_available():
    """Test that Slack bot can be imported when dependencies are available."""
    try:
        from pypoe.slack_bot import SLACK_AVAILABLE, PyPoeSlackBot
        
        if SLACK_AVAILABLE:
            # Slack dependencies are installed
            assert PyPoeSlackBot is not None
        else:
            # Slack dependencies not installed, should gracefully handle
            assert SLACK_AVAILABLE is False
            
    except ImportError:
        pytest.fail("slack_bot module should always be importable, even without slack dependencies")

def test_slack_bot_graceful_degradation():
    """Test that Slack bot handles missing dependencies gracefully."""
    from pypoe.slack_bot import SLACK_AVAILABLE
    
    if not SLACK_AVAILABLE:
        # Should be able to import the module but not create the bot
        from pypoe.slack_bot import PyPoeSlackBot
        
        with pytest.raises(ImportError, match="Slack SDK not available"):
            PyPoeSlackBot()

def test_cli_slack_command_import():
    """Test that CLI can handle slack command even without slack dependencies."""
    try:
        from pypoe.cli import main
        # Should not raise import errors
        assert main is not None
    except ImportError:
        pytest.fail("CLI should always be importable") 