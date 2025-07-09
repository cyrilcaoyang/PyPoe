"""
Command Line Interface for PyPoe

This CLI provides commands to interact with Poe bots from the terminal.
"""

import click
import asyncio
import os
import sys
from datetime import datetime
from typing import Optional

from .poe.client import PoeChatClient
from .config import get_config

def _create_history_manager():
    """Create a HistoryManager with proper parameters for enhanced features."""
    config = get_config()
    from pathlib import Path
    
    # Check if we're using EnhancedHistoryManager or basic HistoryManager
    if hasattr(HistoryManager, '__module__') and 'enhanced_history' in HistoryManager.__module__:
        # Using EnhancedHistoryManager - pass media_dir
        media_dir = Path(config.database_path).parent / "media"
        return HistoryManager(
            db_path=str(config.database_path),
            media_dir=str(media_dir)
        )
    else:
        # Using basic HistoryManager - only pass db_path
        return HistoryManager(db_path=str(config.database_path))

# Import history manager from core package
try:
    from .poe.enhanced_history import EnhancedHistoryManager as HistoryManager
    HISTORY_AVAILABLE = True
except ImportError:
    try:
        from .poe.manager import HistoryManager
        HISTORY_AVAILABLE = True
    except ImportError:
        HISTORY_AVAILABLE = False
        HistoryManager = None

@click.group()
@click.version_option()
def main():
    """PyPoe - Command line interface for Poe.com bots"""
    pass

@main.command()
@click.argument('message')
@click.option('--bot', '-b', default='GPT-3.5-Turbo', help='Bot to use for the conversation')
@click.option('--stream/--no-stream', default=True, help='Stream the response in real-time')
@click.option('--save-history/--no-save-history', default=False, help='Save conversation to local history')
def chat(message: str, bot: str, stream: bool, save_history: bool):
    """Send a single message to a Poe bot"""
    asyncio.run(_chat(message, bot, stream, save_history))

async def _chat(message: str, bot: str, stream: bool, save_history: bool):
    """Async implementation of chat command"""
    try:
        client = PoeChatClient(enable_history=save_history and HISTORY_AVAILABLE)
        
        click.echo(f"🤖 Chatting with {bot}")
        if save_history and HISTORY_AVAILABLE:
            click.echo("💾 History saving enabled")
        elif save_history and not HISTORY_AVAILABLE:
            click.echo("⚠️  History requested but not available")
        click.echo(f"👤 You: {message}")
        click.echo("🤖 Bot: ", nl=False)
        
        if stream:
            async for chunk in client.send_message(message, bot_name=bot, save_history=save_history):
                click.echo(chunk, nl=False)
        else:
            response = ""
            async for chunk in client.send_message(message, bot_name=bot, save_history=save_history):
                response += chunk
            click.echo(response)
        
        click.echo("\n")
        await client.close()
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        if "POE_API_KEY is not set" in str(e):
            click.echo("💡 Run: python user_scripts/setup_credentials.py", err=True)

@main.command()
@click.option('--bot', '-b', default='GPT-3.5-Turbo', help='Bot to use for the conversation')
@click.option('--save-history/--no-save-history', default=True, help='Save conversation to local history')
def interactive(bot: str, save_history: bool):
    """Start an interactive chat session"""
    asyncio.run(_interactive(bot, save_history))

async def _interactive(bot: str, save_history: bool):
    """Async implementation of interactive command"""
    if save_history and not HISTORY_AVAILABLE:
        click.echo("⚠️  History requested but not available. Continuing without history.")
        save_history = False
    
    try:
        client = PoeChatClient(enable_history=save_history)
        conversation = []
        
        click.echo(f"🤖 Interactive chat with {bot}")
        if save_history:
            click.echo("💾 History saving enabled")
        click.echo("Type 'quit', 'exit', or press Ctrl+C to end the conversation")
        click.echo("-" * 50)
        
        while True:
            try:
                message = click.prompt("You", type=str)
                
                if message.lower() in ['quit', 'exit']:
                    break
                
                conversation.append({"role": "user", "content": message})
                
                click.echo("Bot: ", nl=False)
                bot_response = ""
                async for chunk in client.send_conversation(conversation, bot_name=bot, save_history=save_history):
                    click.echo(chunk, nl=False)
                    bot_response += chunk
                
                conversation.append({"role": "bot", "content": bot_response})
                click.echo("\n")
                
            except (KeyboardInterrupt, EOFError):
                break
        
        click.echo("\n👋 Goodbye!")
        await client.close()
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)

@main.command()
@click.option('--limit', '-l', default=10, help='Number of conversations to show')
def conversations(limit: int):
    """List conversation history"""
    asyncio.run(_conversations(limit))

async def _conversations(limit: int):
    """Async implementation of conversations command"""
    if not HISTORY_AVAILABLE:
        click.echo("❌ History manager not available")
        click.echo("💡 Make sure the history module is available")
        return
    
    try:
        manager = _create_history_manager()
        await manager.initialize()
        convs = await manager.get_conversations()
        
        # Apply limit client-side since enhanced manager returns all
        convs = convs[:limit]
        
        if not convs:
            click.echo("📭 No conversations found")
            return
        
        click.echo(f"📚 Last {len(convs)} conversations:")
        click.echo("-" * 60)
        
        for conv in convs:
            created = datetime.fromisoformat(conv['created_at'].replace('Z', '+00:00'))
            click.echo(f"🆔 {conv['id'][:8]}... | 📝 {conv['title'][:40]}")
            click.echo(f"📅 {created.strftime('%Y-%m-%d %H:%M:%S')}")
            click.echo("-" * 60)
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)

@main.command()
@click.argument('conversation_id')
def messages(conversation_id: str):
    """Show messages from a conversation"""
    asyncio.run(_messages(conversation_id))

async def _messages(conversation_id: str):
    """Async implementation of messages command"""
    if not HISTORY_AVAILABLE:
        click.echo("❌ History manager not available")
        return
    
    try:
        manager = _create_history_manager()
        await manager.initialize()
        msgs = await manager.get_conversation_messages(conversation_id)
        
        if not msgs:
            click.echo(f"📭 No messages found for conversation {conversation_id[:8]}...")
            return
        
        click.echo(f"💬 Messages from conversation {conversation_id[:8]}...")
        click.echo("-" * 60)
        
        for msg in msgs:
            role_emoji = "👤" if msg['role'] == 'user' else "🤖"
            timestamp = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
            
            click.echo(f"{role_emoji} {msg['role'].title()} [{timestamp.strftime('%H:%M:%S')}]:")
            click.echo(f"   {msg['content']}")
            click.echo()
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)

@main.command()
@click.argument('conversation_id')
@click.confirmation_option(prompt='Are you sure you want to delete this conversation?')
def delete(conversation_id: str):
    """Delete a conversation"""
    asyncio.run(_delete(conversation_id))

async def _delete(conversation_id: str):
    """Async implementation of delete command"""
    if not HISTORY_AVAILABLE:
        click.echo("❌ History manager not available")
        return
    
    try:
        manager = _create_history_manager()
        await manager.initialize()
        await manager.delete_conversation(conversation_id)
        success = True
        
        if success:
            click.echo(f"✅ Deleted conversation {conversation_id[:8]}...")
        else:
            click.echo(f"❌ Conversation {conversation_id[:8]}... not found")
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)

@main.command()
def bots():
    """List available bots"""
    asyncio.run(_bots())

async def _bots():
    """Async implementation of bots command"""
    try:
        client = PoeChatClient()
        available_bots = await client.get_available_bots()
        
        click.echo("🤖 Available bots:")
        click.echo("-" * 30)
        for bot in available_bots:
            click.echo(f"  • {bot}")
        
        await client.close()
        
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)

@main.command()
def status():
    """Show PyPoe status and configuration"""
    click.echo("PyPoe Status")
    click.echo("=" * 20)
    
    # Load environment before checking API key
    from pathlib import Path
    from dotenv import load_dotenv
    
    # Try to find and load .env file from multiple locations
    possible_env_paths = [
        Path.cwd() / ".env",  # Current directory
        Path(__file__).parent.parent.parent / ".env",  # Project root
        Path.home() / ".pypoe" / ".env",  # User directory
    ]
    
    for env_path in possible_env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            break
    
    # Check API key
    api_key = os.getenv('POE_API_KEY')
    if api_key:
        masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "***"
        click.echo(f"✅ API Key: {masked_key}")
    else:
        click.echo("❌ API Key: Not set")
        click.echo("💡 Run: python user_scripts/setup_credentials.py")
    
    # Check history availability
    if HISTORY_AVAILABLE:
        click.echo("✅ History: Available")
        
        # Show database path
        manager = _create_history_manager()
        db_path = str(manager.db_path)
        if os.path.exists(db_path):
            size = os.path.getsize(db_path)
            click.echo(f"📁 Database: {db_path} ({size} bytes)")
        else:
            click.echo(f"📁 Database: {db_path} (not created yet)")
    else:
        click.echo("❌ History: Not available")
        click.echo("💡 Check history manager import")

@main.command()
@click.option('--host', default='localhost', envvar='PYPOE_HOST', help='Host to bind the server to. Can be set with PYPOE_HOST env var.')
@click.option('--port', default=8000, envvar='PYPOE_PORT', type=int, help='Port to run the server on. Can be set with PYPOE_PORT env var.')
@click.option('--web-username', envvar='PYPOE_WEB_USERNAME', help='Username for web UI basic auth. Can be set with PYPOE_WEB_USERNAME env var.')
@click.option('--web-password', envvar='PYPOE_WEB_PASSWORD', help='Password for web UI basic auth. Can be set with PYPOE_WEB_PASSWORD env var.')
def web(host, port, web_username, web_password):
    """Start the PyPoe web interface"""
    # Ensure environment is loaded before getting config
    from pathlib import Path
    from dotenv import load_dotenv
    
    # Try to find and load .env file from multiple locations
    possible_env_paths = [
        Path.cwd() / ".env",  # Current directory
        Path(__file__).parent.parent.parent / ".env",  # Project root
        Path.home() / ".pypoe" / ".env",  # User directory
    ]
    
    env_loaded = False
    for env_path in possible_env_paths:
        if env_path.exists():
            click.echo(f"🔧 Loading environment from: {env_path}")
            load_dotenv(env_path)
            env_loaded = True
            break
    
    if not env_loaded:
        click.echo("⚠️  No .env file found, using environment variables only")
    
    config = get_config()
    if web_username:
        config.web_username = web_username
    if web_password:
        config.web_password = web_password

    if 'src.pypoe.web.runner' in sys.modules:
        from src.pypoe.web.runner import run_web_server
    else:
        # Fallback for different execution environments
        from .web.runner import run_web_server

    if config.web_username:
        click.echo(f"🔐 Web interface is password protected")
    
    click.echo(f"🌐 Starting web server at http://{host}:{port}")
    run_web_server(host=host, port=port, config=config)

@main.command()
@click.option('--format', 'export_format', default='table', type=click.Choice(['table', 'json']), help='Output format')
@click.option('--limit', default=10, help='Number of conversations to show')
def history(export_format, limit):
    """Show conversation history"""
    asyncio.run(_history(export_format, limit))

async def _history(export_format: str, limit: int):
    """Show conversation history with enhanced formatting"""
    if not HISTORY_AVAILABLE:
        click.echo("❌ History manager not available")
        return
    
    try:
        manager = _create_history_manager()
        await manager.initialize()
        conversations = await manager.get_conversations()
        
        if not conversations:
            click.echo("📭 No conversations found.")
            click.echo("💡 Start a chat with --save-history to create conversation history")
            return
        
        # Limit results
        conversations = conversations[:limit]
        
        if export_format == 'json':
            import json
            click.echo(json.dumps(conversations, indent=2))
        else:
            # Enhanced table format
            total_count = len(conversations) if limit >= len(conversations) else "many"
            click.echo(f"\n📚 Conversation History (showing {len(conversations[:limit])} of {total_count})")
            click.echo("=" * 80)
            click.echo(f"{'ID':<10} {'Title':<30} {'Bot':<20} {'Created':<20}")
            click.echo("-" * 80)
            
            for conv in conversations:
                # Get message count for each conversation
                messages = await manager.get_conversation_messages(conv['id'])
                msg_count = len(messages)
                
                conv_id = conv['id'][:8] + "..."
                title = conv.get('title', 'Untitled')[:28] + ('...' if len(conv.get('title', '')) > 28 else '')
                bot = conv.get('bot_name', 'Unknown')[:18] + ('...' if len(conv.get('bot_name', '')) > 18 else '')
                created = conv.get('created_at', 'Unknown')[:18]
                
                click.echo(f"{conv_id:<10} {title:<30} {bot:<20} {created:<20}")
                click.echo(f"{'':>10} 💬 {msg_count} messages")
                click.echo()
            
            click.echo(f"💡 Use 'pypoe messages <conversation_id>' to view specific conversation")
            click.echo(f"💡 Use 'pypoe web' to browse conversations in your browser")
                    
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)

@main.command()
@click.option('--enable-history/--no-history', default=True, help='Enable conversation history')
@click.option('--socket-mode/--http-mode', default=True, help='Use Socket Mode (dev) vs HTTP mode (prod)')
def slack_bot(enable_history, socket_mode):
    """Run the PyPoe Slack bot integration"""
    import os
    import asyncio
    
    try:
        from .slack.bot import PyPoeSlackBot, SLACK_AVAILABLE
        
        if not SLACK_AVAILABLE:
            click.echo("❌ Slack integration not available.")
            click.echo("💡 Install PyPoe with Slack support:")
            click.echo("   pip install -e \".[slack]\"")
            click.echo("   # or: pip install slack-bolt slack-sdk")
            return
        
        # Check required environment variables
        required_vars = ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "POE_API_KEY"]
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        
        if missing_vars:
            click.echo(f"❌ Missing environment variables: {', '.join(missing_vars)}")
            click.echo("\n📋 Setup Instructions:")
            click.echo("1. Create a Slack app at https://api.slack.com/apps")
            click.echo("2. Set environment variables:")
            click.echo("   export SLACK_BOT_TOKEN=xoxb-your-bot-token")
            click.echo("   export SLACK_SIGNING_SECRET=your-signing-secret")
            click.echo("   export SLACK_APP_TOKEN=xapp-your-app-token  # For Socket Mode")
            click.echo("   export POE_API_KEY=your-poe-api-key")
            click.echo("3. Run: pypoe slack-bot")
            return
        
        # Set socket mode preference
        if socket_mode:
            os.environ["SLACK_SOCKET_MODE"] = "true"
        else:
            os.environ["SLACK_SOCKET_MODE"] = "false"
        
        async def run_bot():
            click.echo("🚀 Starting PyPoe Slack Bot...")
            click.echo("📋 Configuration:")
            click.echo(f"   POE_API_KEY: {'✅ Set' if os.environ.get('POE_API_KEY') else '❌ Missing'}")
            click.echo(f"   SLACK_BOT_TOKEN: {'✅ Set' if os.environ.get('SLACK_BOT_TOKEN') else '❌ Missing'}")
            click.echo(f"   Socket Mode: {socket_mode}")
            click.echo(f"   History Enabled: {enable_history}")
            
            bot = PyPoeSlackBot(enable_history=enable_history)
            
            try:
                await bot.run()
            except KeyboardInterrupt:
                click.echo("\n👋 Shutting down PyPoe Slack Bot...")
                await bot.close()
            except Exception as e:
                click.echo(f"❌ Error running bot: {e}")
                await bot.close()
        
        asyncio.run(run_bot())
        
    except ImportError as e:
        click.echo(f"❌ Failed to import Slack integration: {e}")
        click.echo("Install Slack dependencies with: pip install slack-bolt slack-sdk")

if __name__ == '__main__':
    main()