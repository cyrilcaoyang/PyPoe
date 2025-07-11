"""
PyPoe Slack Interface

Slack bot integration for PyPoe.
Requires slack-bolt and slack-sdk.
"""

from . import bot

# Always expose SLACK_AVAILABLE
SLACK_AVAILABLE = bot.SLACK_AVAILABLE

if bot.SLACK_AVAILABLE:
    SlackBot = bot.PyPoeSlackBot
    from .runner import run_bot
    __all__ = ['SlackBot', 'run_bot', 'SLACK_AVAILABLE']
else:
    def SlackBot(*args, **kwargs):
        raise ImportError(
            "Slack interface dependencies missing. "
            "Install with: pip install pypoe[web-ui]"
        )
    def run_bot(*args, **kwargs):
        raise ImportError(
            "Slack interface dependencies missing. "
            "Install with: pip install pypoe[web-ui]"
        )
    __all__ = ['SlackBot', 'run_bot', 'SLACK_AVAILABLE'] 