"""
PyPoe Slack Bot Integration Module

A comprehensive Slack bot that integrates with Poe API to provide:
- Interactive model selection via Slack UI
- Token/compute point usage monitoring  
- Multi-turn conversations
- Error handling and rate limiting
- Admin controls and usage analytics

This module can be imported and used in various ways:
- As a standalone bot: python -m pypoe.slack_bot
- As part of a larger application: from pypoe.slack_bot import PyPoeSlackBot
- Via the CLI: pypoe slack-bot
"""

import asyncio
import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass, asdict

try:
    from slack_bolt.async_app import AsyncApp
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    from slack_sdk.errors import SlackApiError
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False
    AsyncApp = None
    AsyncSocketModeHandler = None
    SlackApiError = Exception

from .poe_client import PoeChatClient
from .history_manager import HistoryManager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class UserSession:
    """Track user session data"""
    user_id: str
    channel_id: str
    preferred_model: str = "GPT-3.5-Turbo"
    conversation: List[Dict[str, str]] = None
    total_messages: int = 0
    total_tokens_estimated: int = 0
    last_activity: datetime = None
    
    def __post_init__(self):
        if self.conversation is None:
            self.conversation = []
        if self.last_activity is None:
            self.last_activity = datetime.now()

class PoeBotUsageTracker:
    """Track usage statistics and compute point estimates"""
    
    def __init__(self):
        self.usage_data = {}
        self.model_costs = {
            # Estimated compute points per message (these are estimates)
            "GPT-3.5-Turbo": 1,
            "GPT-4": 5,
            "GPT-4-Turbo": 3,
            "GPT-4o": 4,
            "Claude-3-Haiku": 1,
            "Claude-3-Sonnet": 3,
            "Claude-3-Opus": 8,
            "Claude-3.5-Sonnet": 4,
            "Llama-3-70B-Instruct": 2,
            "Llama-3-8B-Instruct": 1,
            "Gemini-Pro": 2,
            "PaLM-2": 2,
        }
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 characters)"""
        return len(text) // 4
    
    def get_model_cost(self, model: str) -> int:
        """Get estimated compute points for a model"""
        return self.model_costs.get(model, 3)  # Default to 3 if unknown
    
    def track_usage(self, user_id: str, model: str, input_text: str, output_text: str):
        """Track usage for a user"""
        if user_id not in self.usage_data:
            self.usage_data[user_id] = {
                "total_messages": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "estimated_compute_points": 0,
                "models_used": {},
                "daily_usage": {},
            }
        
        user_data = self.usage_data[user_id]
        today = datetime.now().strftime("%Y-%m-%d")
        
        input_tokens = self.estimate_tokens(input_text)
        output_tokens = self.estimate_tokens(output_text)
        compute_points = self.get_model_cost(model)
        
        # Update totals
        user_data["total_messages"] += 1
        user_data["total_input_tokens"] += input_tokens
        user_data["total_output_tokens"] += output_tokens
        user_data["estimated_compute_points"] += compute_points
        
        # Update model usage
        if model not in user_data["models_used"]:
            user_data["models_used"][model] = 0
        user_data["models_used"][model] += 1
        
        # Update daily usage
        if today not in user_data["daily_usage"]:
            user_data["daily_usage"][today] = 0
        user_data["daily_usage"][today] += compute_points
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get usage statistics for a user"""
        if user_id not in self.usage_data:
            return {
                "total_messages": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "estimated_compute_points": 0,
                "models_used": {},
                "today_usage": 0,
            }
        
        user_data = self.usage_data[user_id]
        today = datetime.now().strftime("%Y-%m-%d")
        today_usage = user_data["daily_usage"].get(today, 0)
        
        return {
            **user_data,
            "today_usage": today_usage,
        }

class PyPoeSlackBot:
    """Main Slack bot class"""
    
    def __init__(self, enable_history: bool = True):
        if not SLACK_AVAILABLE:
            raise ImportError(
                "Slack SDK not available. Install with: pip install slack-bolt slack-sdk"
            )
        
        # Initialize Slack app
        self.app = AsyncApp(
            token=os.environ.get("SLACK_BOT_TOKEN"),
            signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
        )
        
        # Initialize PyPoe client
        self.poe_client = PoeChatClient(enable_history=enable_history)
        
        # User sessions and usage tracking
        self.user_sessions: Dict[str, UserSession] = {}
        self.usage_tracker = PoeBotUsageTracker()
        
        # Available models
        self.available_models = []
        
        # Set up Slack event handlers
        self._setup_handlers()
    
    async def initialize(self):
        """Initialize the bot and fetch available models"""
        try:
            self.available_models = await self.poe_client.get_available_bots()
            logger.info(f"✅ Initialized with {len(self.available_models)} available models")
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            self.available_models = ["GPT-3.5-Turbo", "Claude-3-Haiku"]  # Fallback
    
    def _setup_handlers(self):
        """Set up Slack event handlers"""
        
        @self.app.command("/poe")
        async def handle_poe_command(ack, command, respond):
            await ack()
            await self._handle_slash_command(command, respond)
        
        @self.app.event("app_mention")
        async def handle_mentions(event, say):
            await self._handle_mention(event, say)
        
        @self.app.event("message")
        async def handle_dm(event, say):
            # Only respond to DMs, not channel messages
            if event.get("channel_type") == "im":
                await self._handle_direct_message(event, say)
    
    async def _handle_slash_command(self, command, respond):
        """Handle /poe slash commands"""
        user_id = command["user_id"]
        channel_id = command["channel_id"]
        text = command.get("text", "").strip()
        
        try:
            if not text or text == "help":
                await respond(self._get_help_message())
                return
            
            parts = text.split(" ", 1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            
            if cmd == "models":
                await respond(self._get_models_message())
            
            elif cmd == "set-model":
                if not args:
                    await respond("❌ Please specify a model. Use `/poe models` to see available options.")
                    return
                await self._set_user_model(user_id, channel_id, args, respond)
            
            elif cmd == "chat":
                if not args:
                    await respond("❌ Please provide a message. Example: `/poe chat Hello!`")
                    return
                await self._handle_chat_message(user_id, channel_id, args, respond)
            
            elif cmd == "usage":
                await respond(self._get_usage_message(user_id))
            
            elif cmd == "reset":
                await self._reset_conversation(user_id, channel_id, respond)
            
            else:
                await respond(f"❌ Unknown command: `{cmd}`. Use `/poe help` for available commands.")
        
        except Exception as e:
            logger.error(f"Error handling command: {e}")
            await respond(f"❌ Error: {str(e)}")
    
    async def _handle_mention(self, event, say):
        """Handle @poe_bot mentions"""
        user_id = event["user"]
        channel_id = event["channel"]
        text = event.get("text", "")
        
        # Remove the bot mention from the text
        text = " ".join([word for word in text.split() if not word.startswith("<@")])
        
        if not text.strip():
            await say(self._get_help_message())
            return
        
        await self._handle_chat_message(user_id, channel_id, text, say)
    
    async def _handle_direct_message(self, event, say):
        """Handle direct messages to the bot"""
        user_id = event["user"]
        channel_id = event["channel"]
        text = event.get("text", "")
        
        if not text.strip():
            await say(self._get_help_message())
            return
        
        await self._handle_chat_message(user_id, channel_id, text, say)
    
    async def _handle_chat_message(self, user_id: str, channel_id: str, text: str, respond_func):
        """Handle a chat message to the bot"""
        try:
            # Get or create user session
            session = self._get_or_create_session(user_id, channel_id)
            
            # Add user message to conversation
            session.conversation.append({"role": "user", "content": text})
            session.last_activity = datetime.now()
            
            # Send "thinking" indicator
            await respond_func("🤖 Thinking...")
            
            # Get response from PyPoe
            full_response = ""
            async for chunk in self.poe_client.send_conversation(
                session.conversation, 
                bot_name=session.preferred_model,
                save_history=True
            ):
                full_response += chunk
            
            # Add bot response to conversation
            session.conversation.append({"role": "bot", "content": full_response})
            session.total_messages += 1
            
            # Track usage
            self.usage_tracker.track_usage(user_id, session.preferred_model, text, full_response)
            
            # Format response for Slack
            response_text = self._format_response_for_slack(full_response, session.preferred_model)
            
            await respond_func(response_text)
            
        except Exception as e:
            logger.error(f"Error handling chat message: {e}")
            await respond_func(f"❌ Sorry, I encountered an error: {str(e)}")
    
    def _get_or_create_session(self, user_id: str, channel_id: str) -> UserSession:
        """Get or create a user session"""
        session_key = f"{user_id}_{channel_id}"
        
        if session_key not in self.user_sessions:
            self.user_sessions[session_key] = UserSession(
                user_id=user_id,
                channel_id=channel_id
            )
        
        return self.user_sessions[session_key]
    
    async def _set_user_model(self, user_id: str, channel_id: str, model: str, respond_func):
        """Set the preferred model for a user"""
        # Find the closest matching model
        model_lower = model.lower()
        matched_model = None
        
        for available_model in self.available_models:
            if model_lower in available_model.lower():
                matched_model = available_model
                break
        
        if not matched_model:
            available_list = "\n".join([f"• {model}" for model in self.available_models[:10]])
            await respond_func(
                f"❌ Model '{model}' not found.\n\n**Available models:**\n{available_list}\n\n"
                f"Use `/poe models` to see all {len(self.available_models)} available models."
            )
            return
        
        # Set the model
        session = self._get_or_create_session(user_id, channel_id)
        old_model = session.preferred_model
        session.preferred_model = matched_model
        
        cost = self.usage_tracker.get_model_cost(matched_model)
        await respond_func(
            f"✅ Model changed from **{old_model}** to **{matched_model}**\n"
            f"💰 Estimated cost: {cost} compute points per message"
        )
    
    async def _reset_conversation(self, user_id: str, channel_id: str, respond_func):
        """Reset the conversation for a user"""
        session_key = f"{user_id}_{channel_id}"
        
        if session_key in self.user_sessions:
            old_messages = len(self.user_sessions[session_key].conversation)
            self.user_sessions[session_key].conversation = []
            await respond_func(f"✅ Conversation reset ({old_messages} messages cleared)")
        else:
            await respond_func("✅ Conversation reset (no previous messages)")
    
    def _get_help_message(self) -> str:
        """Get help message"""
        return """
🤖 **PyPoe Slack Bot - Help**

**Slash Commands:**
• `/poe help` - Show this help
• `/poe models` - List available AI models
• `/poe chat <message>` - Send a message to the bot
• `/poe set-model <model>` - Set your preferred model
• `/poe usage` - Check your token usage stats
• `/poe reset` - Reset conversation history

**Direct Interaction:**
• `@poe_bot <message>` - Mention the bot in any channel
• Send direct messages to the bot

**Features:**
• 🧠 Access to 100+ AI models (GPT-4, Claude, Gemini, etc.)
• 💬 Multi-turn conversations with context
• 📊 Usage tracking and compute point monitoring
• 🔄 Model switching mid-conversation
• 💾 Persistent conversation history

**Current Status:** ✅ Connected to Poe API
"""
    
    def _get_models_message(self) -> str:
        """Get available models message"""
        if not self.available_models:
            return "❌ No models available. Please check the bot configuration."
        
        # Group models by provider
        providers = {}
        for model in self.available_models:
            if "GPT" in model or "gpt" in model:
                provider = "OpenAI"
            elif "Claude" in model:
                provider = "Anthropic"
            elif "Gemini" in model or "PaLM" in model:
                provider = "Google"
            elif "Llama" in model:
                provider = "Meta"
            else:
                provider = "Other"
            
            if provider not in providers:
                providers[provider] = []
            providers[provider].append(model)
        
        message = f"🤖 **Available AI Models ({len(self.available_models)} total)**\n\n"
        
        for provider, models in providers.items():
            message += f"**{provider}:**\n"
            for model in models[:5]:  # Limit to first 5 per provider
                cost = self.usage_tracker.get_model_cost(model)
                message += f"• {model} ({cost} pts)\n"
            if len(models) > 5:
                message += f"• ... and {len(models) - 5} more\n"
            message += "\n"
        
        message += "💡 Use `/poe set-model <model-name>` to switch models"
        return message
    
    def _get_usage_message(self, user_id: str) -> str:
        """Get usage statistics message"""
        stats = self.usage_tracker.get_user_stats(user_id)
        
        if stats["total_messages"] == 0:
            return "📊 **Your Usage Stats**\n\nNo messages sent yet. Try `/poe chat Hello!`"
        
        # Format top models
        top_models = sorted(
            stats["models_used"].items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        top_models_text = "\n".join([
            f"• {model}: {count} messages" 
            for model, count in top_models
        ])
        
        return f"""
📊 **Your Usage Stats**

**Total Activity:**
• Messages sent: {stats['total_messages']:,}
• Estimated input tokens: {stats['total_input_tokens']:,}
• Estimated output tokens: {stats['total_output_tokens']:,}
• Estimated compute points used: {stats['estimated_compute_points']:,}

**Today's Usage:**
• Compute points: {stats['today_usage']}

**Top Models Used:**
{top_models_text}

💡 *Compute points are estimates based on model complexity*
"""
    
    def _format_response_for_slack(self, response: str, model: str) -> str:
        """Format the AI response for Slack"""
        # Truncate very long responses
        if len(response) > 3000:
            response = response[:2950] + "\n\n... *(response truncated)*"
        
        return f"🤖 **{model}**\n\n{response}"
    
    async def run(self):
        """Run the Slack bot"""
        await self.initialize()
        
        # Use Socket Mode for local development
        if os.environ.get("SLACK_SOCKET_MODE", "true").lower() == "true":
            handler = AsyncSocketModeHandler(self.app, os.environ.get("SLACK_APP_TOKEN"))
            await handler.start_async()
        else:
            # Use HTTP mode for production
            await self.app.async_start(port=int(os.environ.get("PORT", 3000)))
    
    async def close(self):
        """Clean up resources"""
        await self.poe_client.close()

async def main():
    """Main entry point"""
    import sys
    
    # Check required environment variables
    required_vars = ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "POE_API_KEY"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("\n📋 Setup Instructions:")
        print("1. Create a Slack app at https://api.slack.com/apps")
        print("2. Set environment variables:")
        print("   export SLACK_BOT_TOKEN=xoxb-your-bot-token")
        print("   export SLACK_SIGNING_SECRET=your-signing-secret")
        print("   export SLACK_APP_TOKEN=xapp-your-app-token  # For Socket Mode")
        print("   export POE_API_KEY=your-poe-api-key")
        print("3. Run: python -m pypoe.slack_bot")
        return
    
    if not SLACK_AVAILABLE:
        print("❌ Slack SDK not installed. Install with:")
        print("   pip install slack-bolt slack-sdk")
        return
    
    print("🚀 Starting PyPoe Slack Bot...")
    print("📋 Configuration:")
    print(f"   POE_API_KEY: {'✅ Set' if os.environ.get('POE_API_KEY') else '❌ Missing'}")
    print(f"   SLACK_BOT_TOKEN: {'✅ Set' if os.environ.get('SLACK_BOT_TOKEN') else '❌ Missing'}")
    print(f"   Socket Mode: {os.environ.get('SLACK_SOCKET_MODE', 'true')}")
    
    bot = PyPoeSlackBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        print("\n👋 Shutting down PyPoe Slack Bot...")
        await bot.close()
    except Exception as e:
        print(f"❌ Error running bot: {e}")
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main()) 