"""
Command Line Interface for PyPoe

This CLI provides commands to interact with Poe bots from the terminal.
"""

import click
import asyncio
import os
import sys
import time
from datetime import datetime
from typing import Optional

from .core.client import PoeChatClient
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
    from .core.enhanced_history import EnhancedHistoryManager as HistoryManager
    HISTORY_AVAILABLE = True
except ImportError:
    try:
        from .core.manager import HistoryManager
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

    try:
        from .interfaces.web.runner import run_web_server

        if config.web_username:
            click.echo(f"🔐 Web interface is password protected")
        
        click.echo(f"🌐 Starting web server at http://{host}:{port}")
        run_web_server(host=host, port=port, config=config)
        
    except ImportError:
        click.echo("❌ Web UI dependencies not installed!")
        click.echo("Please install with: pip install pypoe[web-ui]")
    except Exception as e:
        click.echo(f"❌ Error starting web server: {e}", err=True)

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
        from .interfaces import slack
        
        if not slack.SLACK_AVAILABLE:
            click.echo("❌ Slack integration not available.")
            click.echo("💡 Install PyPoe with Slack support:")
            click.echo("   pip install pypoe[web-ui]")
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
            
            bot = slack.SlackBot(enable_history=enable_history)
            
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

@main.group()
def daemon():
    """Manage PyPoe web server daemon"""
    pass

@daemon.command()
@click.option('--host', default='0.0.0.0', envvar='PYPOE_HOST', help='Host to bind the server to')
@click.option('--port', default=8000, envvar='PYPOE_PORT', type=int, help='Port to run the server on')
def start(host, port):
    """Start the PyPoe web server daemon"""
    try:
        from .scripts.setup.daemon_manager import DaemonManager
        manager = DaemonManager()
        manager.start_daemon(host=host, port=port)
    except ImportError:
        # Fallback to inline implementation if module doesn't exist
        _start_daemon_inline(host, port)

@daemon.command()
def stop():
    """Stop the PyPoe web server daemon"""
    try:
        from .scripts.setup.daemon_manager import DaemonManager
        manager = DaemonManager()
        manager.stop_daemon()
    except ImportError:
        _stop_daemon_inline()

@daemon.command()
def status():
    """Check PyPoe web server daemon status"""
    try:
        from .scripts.setup.daemon_manager import DaemonManager
        manager = DaemonManager()
        manager.status_daemon()
    except ImportError:
        _status_daemon_inline()

@daemon.command()
def restart():
    """Restart the PyPoe web server daemon"""
    try:
        from .scripts.setup.daemon_manager import DaemonManager
        manager = DaemonManager()
        manager.restart_daemon()
    except ImportError:
        _restart_daemon_inline()

@daemon.command()
def logs():
    """Show PyPoe web server daemon logs"""
    try:
        from .scripts.setup.daemon_manager import DaemonManager
        manager = DaemonManager()
        manager.show_logs()
    except ImportError:
        _show_logs_inline()

# Inline implementations as fallback
def _start_daemon_inline(host, port):
    """Inline daemon start implementation"""
    import os
    import signal
    import subprocess
    import time
    import platform
    from pathlib import Path
    from datetime import datetime
    
    # Configuration
    DAEMON_NAME = "pypoe-web"
    PID_FILE = Path.home() / f".{DAEMON_NAME}.pid"
    LOG_FILE = Path.home() / f".{DAEMON_NAME}.log"
    ERROR_LOG_FILE = Path.home() / f".{DAEMON_NAME}.error.log"
    
    # Check if already running
    if PID_FILE.exists():
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)  # Check if process exists
            click.echo(f"✅ PyPoe web server is already running (PID: {pid})")
            return
        except (ValueError, ProcessLookupError, OSError):
            PID_FILE.unlink(missing_ok=True)
    
    click.echo("🚀 Starting PyPoe web server daemon...")
    
    # Create log files
    LOG_FILE.touch()
    ERROR_LOG_FILE.touch()
    
    # Start the process in background
    try:
        with open(LOG_FILE, 'a') as log_file, open(ERROR_LOG_FILE, 'a') as error_file:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_file.write(f"\n=== PyPoe Web Server Started: {timestamp} ===\n")
            log_file.flush()
            
            kwargs = {
                'stdout': log_file,
                'stderr': error_file,
                'stdin': subprocess.DEVNULL,
                'env': os.environ.copy(),
            }
            
            if platform.system() != "Windows":
                kwargs['preexec_fn'] = os.setsid
            
            process = subprocess.Popen(
                ['pypoe', 'web', '--host', host, '--port', str(port)],
                **kwargs
            )
            
            with open(PID_FILE, 'w') as f:
                f.write(str(process.pid))
            
            time.sleep(2)
            
            if process.poll() is None:
                click.echo(f"✅ PyPoe web server started successfully!")
                click.echo(f"📁 PID: {process.pid}")
                click.echo(f"📁 Log file: {LOG_FILE}")
                click.echo(f"🌐 Access at: http://{host}:{port}")
            else:
                click.echo("❌ Failed to start PyPoe web server")
                click.echo(f"📁 Check error log: {ERROR_LOG_FILE}")
                PID_FILE.unlink(missing_ok=True)
                
    except Exception as e:
        click.echo(f"❌ Error starting daemon: {e}")
        PID_FILE.unlink(missing_ok=True)

def _stop_daemon_inline():
    """Inline daemon stop implementation"""
    import os
    import signal
    import time
    from pathlib import Path
    from datetime import datetime
    
    DAEMON_NAME = "pypoe-web"
    PID_FILE = Path.home() / f".{DAEMON_NAME}.pid"
    LOG_FILE = Path.home() / f".{DAEMON_NAME}.log"
    
    if not PID_FILE.exists():
        click.echo("⚠️  PyPoe web server is not running")
        return
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        click.echo(f"🛑 Stopping PyPoe web server daemon (PID: {pid})...")
        
        os.kill(pid, signal.SIGTERM)
        
        # Wait for process to stop
        for _ in range(10):
            time.sleep(1)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
        else:
            click.echo("🔨 Force killing process...")
            os.kill(pid, signal.SIGKILL)
        
        PID_FILE.unlink(missing_ok=True)
        
        # Log shutdown
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, 'a') as log_file:
            log_file.write(f"\n=== PyPoe Web Server Stopped: {timestamp} ===\n")
        
        click.echo("✅ PyPoe web server stopped successfully")
        
    except (ValueError, ProcessLookupError):
        click.echo("⚠️  Process was already stopped")
        PID_FILE.unlink(missing_ok=True)
    except Exception as e:
        click.echo(f"❌ Error stopping daemon: {e}")

def _status_daemon_inline():
    """Inline daemon status implementation"""
    import os
    import subprocess
    from pathlib import Path
    
    DAEMON_NAME = "pypoe-web"
    PID_FILE = Path.home() / f".{DAEMON_NAME}.pid"
    LOG_FILE = Path.home() / f".{DAEMON_NAME}.log"
    ERROR_LOG_FILE = Path.home() / f".{DAEMON_NAME}.error.log"
    
    if not PID_FILE.exists():
        click.echo("❌ PyPoe web server is not running")
    else:
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)  # Check if process exists
            click.echo(f"✅ PyPoe web server is running (PID: {pid})")
            
            # Show process info
            try:
                result = subprocess.run(['ps', '-p', str(pid), '-o', 'pid,ppid,etime,cmd'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    click.echo("\n📊 Process Information:")
                    click.echo(result.stdout)
            except Exception:
                pass
                
        except (ValueError, ProcessLookupError, OSError):
            click.echo("❌ PyPoe web server is not running")
            PID_FILE.unlink(missing_ok=True)
    
    click.echo(f"\n📁 Files:")
    click.echo(f"   • PID file: {PID_FILE} {'✅' if PID_FILE.exists() else '❌'}")
    click.echo(f"   • Log file: {LOG_FILE} {'✅' if LOG_FILE.exists() else '❌'}")
    click.echo(f"   • Error log: {ERROR_LOG_FILE} {'✅' if ERROR_LOG_FILE.exists() else '❌'}")

def _restart_daemon_inline():
    """Inline daemon restart implementation"""
    click.echo("🔄 Restarting PyPoe web server daemon...")
    _stop_daemon_inline()
    time.sleep(2)
    _start_daemon_inline('0.0.0.0', 8000)

def _show_logs_inline():
    """Inline show logs implementation"""
    import subprocess
    from pathlib import Path
    
    DAEMON_NAME = "pypoe-web"
    LOG_FILE = Path.home() / f".{DAEMON_NAME}.log"
    ERROR_LOG_FILE = Path.home() / f".{DAEMON_NAME}.error.log"
    
    if not LOG_FILE.exists():
        click.echo("❌ No log file found")
        return
    
    click.echo(f"📋 Showing last 50 lines of {LOG_FILE}:")
    click.echo("-" * 50)
    
    try:
        result = subprocess.run(['tail', '-n', '50', str(LOG_FILE)], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            click.echo(result.stdout)
        else:
            click.echo("❌ Failed to read log file")
    except Exception as e:
        click.echo(f"❌ Error reading log file: {e}")
    
    click.echo("-" * 50)
    click.echo(f"📁 Full log file: {LOG_FILE}")
    click.echo(f"📁 Error log file: {ERROR_LOG_FILE}")

@main.command()
@click.option('--save-results/--no-save-results', default=True, help='Save detailed results to JSON file')
@click.option('--timeout', default=30, help='Timeout per bot test in seconds')
def test_bots(save_results, timeout):
    """Test all available chatbots and report which ones are working"""
    import asyncio
    from pathlib import Path
    
    # Import the test script
    script_path = Path(__file__).parent / "scripts" / "test_all_bots.py"
    if not script_path.exists():
        click.echo("❌ Bot testing script not found!")
        click.echo(f"Expected at: {script_path}")
        return
    
    click.echo("🤖 Running bot compatibility test...")
    click.echo("This will test all available chatbots (excluding image/video/audio bots)")
    click.echo()
    
    try:
        # Run the test script
        async def run_test():
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            
            from pypoe.scripts.test_all_bots import main as test_main
            return await test_main()
        
        result = asyncio.run(run_test())
        
        if result == 0:
            click.echo("\n🎉 All tests completed successfully!")
        else:
            click.echo(f"\n⚠️  Some bots are not working. Check the summary above.")
            
    except KeyboardInterrupt:
        click.echo("\n⚠️  Testing interrupted by user")
    except Exception as e:
        click.echo(f"\n❌ Error running tests: {e}")

if __name__ == '__main__':
    main()