"""
PyPoe Slack Integration Module

Contains the Slack bot implementation and related components.
"""

# Check if slack dependencies are available
try:
    import slack_bolt
    import slack_sdk
    SLACK_AVAILABLE = True
    
    from .bot import PyPoeSlackBot
    __all__ = ["PyPoeSlackBot", "SLACK_AVAILABLE"]
    
except ImportError:
    SLACK_AVAILABLE = False
    __all__ = ["SLACK_AVAILABLE"] 