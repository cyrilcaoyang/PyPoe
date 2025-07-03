#!/usr/bin/env python3
"""
PyPoe Slack Bot Runner

Simple script to run the Slack bot from the pypoe package.
The actual implementation is in src/pypoe/slack_bot.py

Usage:
    python src/pypoe/slack_bot_runner.py
    
Or use the CLI:
    pypoe slack-bot
"""

import asyncio
import sys

try:
    from .bot import main
    
    if __name__ == "__main__":
        asyncio.run(main())
        
except ImportError as e:
    print(f"❌ Failed to import PyPoe Slack integration: {e}")
    print("\n💡 Make sure you have installed PyPoe:")
    print("   pip install -e .")
    print("\n💡 And install Slack dependencies:")
    print("   pip install slack-bolt slack-sdk")
    print("\n💡 Or use the CLI command:")
    print("   pypoe slack-bot")
    sys.exit(1) 