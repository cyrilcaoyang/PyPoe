import asyncio
import sys
from pathlib import Path
from typing import AsyncGenerator, List, Dict, Any, Optional
import fastapi_poe as fp

from ..config import get_config, Config

# Add users directory to path for any user scripts
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "users"))

try:
    from .history import HistoryManager
    HISTORY_AVAILABLE = True
except ImportError:
    HISTORY_AVAILABLE = False
    HistoryManager = None

class PoeChatClient:
    """A high-level client for interacting with Poe.com using the official API."""

    def __init__(self, config: Config = None, enable_history: bool = True):
        if config is None:
            config = get_config()
        
        self.config = config
        self.api_key = config.poe_api_key
        self.enable_history = enable_history and HISTORY_AVAILABLE
        
        if self.enable_history:
            self.history = HistoryManager(self.config.database_path)
            self._history_initialized = False
        else:
            self.history = None
            self._history_initialized = True

    async def _ensure_history_initialized(self):
        """Ensure the history database is initialized."""
        if self.enable_history and not self._history_initialized:
            await self.history.initialize()
            self._history_initialized = True

    def _convert_role_for_api(self, role: str) -> str:
        """Convert role names for API compatibility."""
        if role == "assistant":
            return "bot"
        return role

    def _convert_role_for_history(self, role: str) -> str:
        """Convert role names for history storage."""
        if role == "bot":
            return "assistant"
        return role

    async def send_message(
        self, 
        message: str, 
        bot_name: str = "GPT-3.5-Turbo",
        conversation_id: Optional[str] = None,
        save_history: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Send a message to a Poe bot and stream the response.
        
        Args:
            message: The message to send
            bot_name: The bot to send the message to (default: GPT-3.5-Turbo)
            conversation_id: Optional conversation ID for history tracking
            save_history: Whether to save the conversation to history
            
        Yields:
            Partial responses from the bot
            
        Raises:
            ValueError: If the bot is not accessible or available
            Exception: For other API errors
        """
        await self._ensure_history_initialized()
        
        # Create a new conversation if none provided and history is enabled
        if conversation_id is None and save_history and self.enable_history:
            conversation_id = await self.history.create_conversation(
                title=f"Chat with {bot_name}",
                bot_name=bot_name
            )
        
        # Save the user message to history
        if save_history and conversation_id and self.enable_history:
            await self.history.add_message(
                conversation_id=conversation_id,
                role="user",
                content=message
            )
        
        # Prepare the message for the API
        poe_message = fp.ProtocolMessage(role="user", content=message)
        
        # Stream the response with error handling
        full_response = ""
        try:
            async for partial in fp.get_bot_response(
                messages=[poe_message], 
                bot_name=bot_name, 
                api_key=self.api_key
            ):
                if hasattr(partial, 'text') and partial.text:
                    yield partial.text
                    full_response += partial.text
        except Exception as e:
            error_msg = str(e)
            # Handle specific bot access errors
            if "Cannot access private bots" in error_msg:
                available_bots = await self.get_available_bots()
                claude_alternatives = [bot for bot in available_bots if "Claude" in bot]
                
                error_message = f"❌ Bot '{bot_name}' is not accessible (private or deprecated).\n\n"
                if claude_alternatives:
                    error_message += f"🤖 Try these Claude alternatives instead:\n"
                    for alt in claude_alternatives[:3]:  # Show top 3
                        error_message += f"  • {alt}\n"
                else:
                    error_message += f"🤖 Try these available bots instead:\n"
                    for alt in available_bots[:5]:  # Show top 5
                        error_message += f"  • {alt}\n"
                
                raise ValueError(error_message)
            elif "Bot does not exist" in error_msg:
                available_bots = await self.get_available_bots()
                error_message = f"❌ Bot '{bot_name}' does not exist.\n\n"
                error_message += f"🤖 Try these available bots instead:\n"
                for alt in available_bots[:5]:  # Show top 5
                    error_message += f"  • {alt}\n"
                raise ValueError(error_message)
            elif "insufficient" in error_msg.lower() or "quota" in error_msg.lower():
                raise ValueError(f"❌ Insufficient credits or quota exceeded. Please check your Poe subscription.")
            else:
                # Re-raise the original error for other cases
                raise e
        
        # Save the bot response to history
        if save_history and conversation_id and full_response and self.enable_history:
            await self.history.add_message(
                conversation_id=conversation_id,
                role="assistant",  # Save as assistant in history
                content=full_response
            )

    async def send_conversation(
        self, 
        messages: List[Dict[str, str]], 
        bot_name: str = "GPT-3.5-Turbo",
        conversation_id: Optional[str] = None,
        save_history: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Send a multi-turn conversation to a Poe bot.
        
        Args:
            messages: List of messages in format [{"role": "user", "content": "..."}, ...]
            bot_name: The bot to send the conversation to
            conversation_id: Optional conversation ID for history tracking
            save_history: Whether to save the conversation to history
            
        Yields:
            Partial responses from the bot
        """
        await self._ensure_history_initialized()
        
        # Create a new conversation if none provided and history is enabled
        if conversation_id is None and save_history and self.enable_history:
            conversation_id = await self.history.create_conversation(
                title=f"Multi-turn chat with {bot_name}",
                bot_name=bot_name
            )
        
        # Convert messages to Poe format, mapping roles correctly
        poe_messages = [
            fp.ProtocolMessage(
                role=self._convert_role_for_api(msg["role"]), 
                content=msg["content"]
            )
            for msg in messages
        ]
        
        # Save messages to history if needed (with proper role names)
        if save_history and conversation_id and self.enable_history:
            for msg in messages:
                await self.history.add_message(
                    conversation_id=conversation_id,
                    role=self._convert_role_for_history(msg["role"]),
                    content=msg["content"]
                )
        
        # Stream the response
        full_response = ""
        try:
            async for partial in fp.get_bot_response(
                messages=poe_messages, 
                bot_name=bot_name, 
                api_key=self.api_key
            ):
                if hasattr(partial, 'text') and partial.text:
                    yield partial.text
                    full_response += partial.text
        except Exception as e:
            error_msg = str(e)
            # Handle specific bot access errors
            if "Cannot access private bots" in error_msg:
                available_bots = await self.get_available_bots()
                claude_alternatives = [bot for bot in available_bots if "Claude" in bot]
                
                error_message = f"❌ Bot '{bot_name}' is not accessible (private or deprecated).\n\n"
                if claude_alternatives:
                    error_message += f"🤖 Try these Claude alternatives instead:\n"
                    for alt in claude_alternatives[:3]:  # Show top 3
                        error_message += f"  • {alt}\n"
                else:
                    error_message += f"🤖 Try these available bots instead:\n"
                    for alt in available_bots[:5]:  # Show top 5
                        error_message += f"  • {alt}\n"
                
                raise ValueError(error_message)
            elif "Bot does not exist" in error_msg:
                available_bots = await self.get_available_bots()
                error_message = f"❌ Bot '{bot_name}' does not exist.\n\n"
                error_message += f"🤖 Try these available bots instead:\n"
                for alt in available_bots[:5]:  # Show top 5
                    error_message += f"  • {alt}\n"
                raise ValueError(error_message)
            elif "insufficient" in error_msg.lower() or "quota" in error_msg.lower():
                raise ValueError(f"❌ Insufficient credits or quota exceeded. Please check your Poe subscription.")
            else:
                # Re-raise the original error for other cases
                raise e
        
        # Save the bot response to history
        if save_history and conversation_id and full_response and self.enable_history:
            await self.history.add_message(
                conversation_id=conversation_id,
                role="assistant",  # Save as assistant in history
                content=full_response
            )

    async def get_available_bots(self) -> List[str]:
        """
        Get a list of available bots.
        Note: This list contains verified working bots as of January 2025.
        Some bots may require special permissions or subscriptions.
        """
        # Verified working bots on Poe as of January 2025
        return [
            # OpenAI models (all working)
            "GPT-3.5-Turbo",
            "GPT-4",
            "GPT-4o",
            "GPT-4o-mini",
            "o1-preview",
            "o1-mini",
            "o3-mini",
            "o4-mini",
            
            # Anthropic models (confirmed working)
            "Claude-3-Opus",
            "Claude-3-Sonnet", 
            "Claude-3-Haiku",
            "Claude-3.5-Sonnet",
            "Claude-3.7-Sonnet",
            
            # Google models (confirmed working)
            "Gemini-1.5-Pro",
            "Gemini-2.0-Flash",
            
            # Meta models (may work - not all tested)
            "Llama-3-70B-Instruct",
            
            # Other models (may work)
            "DeepSeek-R1",
            "Mistral-7B-Instruct",
            "Mixtral-8x7B-Instruct",
        ]

    async def get_conversations(self) -> List[Dict[str, Any]]:
        """Get all conversations from history."""
        if not self.enable_history:
            return []
        await self._ensure_history_initialized()
        return await self.history.get_conversations()

    async def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get all messages from a specific conversation."""
        if not self.enable_history:
            return []
        await self._ensure_history_initialized()
        return await self.history.get_messages(conversation_id)

    async def delete_conversation(self, conversation_id: str):
        """Delete a conversation and all its messages."""
        if not self.enable_history:
            return
        await self._ensure_history_initialized()
        await self.history.delete_conversation(conversation_id)

    async def close(self):
        """Clean up resources."""
        if self.enable_history and self._history_initialized:
            await self.history.close() 