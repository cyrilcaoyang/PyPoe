# PyPoe

A Python client for interacting with Poe.com bots using the official Poe API. PyPoe provides both a programmatic interface and command-line tools for chatting with AI models like GPT-4, Claude, and others through Poe's platform.

## Features

- 🤖 **Official API Integration**: Uses Poe's official API with your subscriber API key
- 🔄 **Async/Streaming Support**: Real-time streaming responses for better UX
- 💾 **Built-in History Management**: SQLite-based conversation history (database stored in `user_scripts/history/`)
- 🖥️ **CLI Interface**: Full-featured command-line interface
- 🔧 **Easy Configuration**: Simple setup with environment variables
- 📦 **Clean Architecture**: Source code in `src/` directory, examples in `user_scripts/`

## Installation

### Basic Installation (CLI + API Client)

```bash
# From source
git clone https://github.com/your-username/pypoe.git
cd pypoe
pip install -e .

# Or from PyPI (when published)
# pip install pypoe
```

### Optional Features

PyPoe offers additional features through optional extras:

```bash
# Slack Bot Integration
pip install -e ".[slackbot]"
# Includes: slack-bolt, slack-sdk, gunicorn, uvicorn

# Web UI Interface
pip install -e ".[web-ui]"
# Includes: fastapi, jinja2, uvicorn, python-multipart

# Development dependencies
pip install -e ".[dev]"
# Includes: pytest, pytest-asyncio

# Install everything
pip install -e ".[all]"
```

This modular approach keeps the core lightweight while allowing you to install only the features you need.

## Quick Start

### 1. Get Your API Key

1. Go to [poe.com/api_key](https://poe.com/api_key)
2. Copy your API key (requires Poe subscription)
3. Run the setup script:

```bash
python user_scripts/setup_credentials.py
```

### 2. Basic Usage

```python
import asyncio
from pypoe import PoeChatClient

async def main():
    client = PoeChatClient(enable_history=True)
    
    # Send a single message
    async for chunk in client.send_message("Hello!", bot_name="GPT-3.5-Turbo"):
        print(chunk, end="", flush=True)
    
    await client.close()

asyncio.run(main())
```

### 3. Command Line Usage

```bash
# Send a single message
pypoe chat "What is machine learning?"

# Interactive chat session
pypoe interactive --bot GPT-4-Turbo

# List available bots
pypoe bots

# Check status
pypoe status
```

## Configuration

Create a `.env` file in the project root:

```env
# Required: Your Poe API key
POE_API_KEY=your_api_key_here

# Optional: Default bot to use
DEFAULT_BOT=GPT-4-Turbo

# Optional: Enable history by default
ENABLE_HISTORY=true
```

## Project Structure

```
PyPoe/
├── src/
│   └── pypoe/              # Main package source code
│       ├── __init__.py     # Main package exports
│       ├── config.py       # Configuration management
│       ├── cli.py          # Command-line interface
│       │
│       ├── poe/            # 🤖 Core POE functionality
│       │   ├── client.py   # Main POE API client
│       │   ├── history.py  # Simple history manager
│       │   └── manager.py  # Advanced history manager
│       │
│       ├── web/            # 🌐 Web interface module
│       │   ├── app.py      # FastAPI web application
│       │   ├── templates/  # HTML templates
│       │   └── static/     # CSS, JavaScript assets
│       │
│       └── slack/          # 💬 Slack bot integration
│           ├── bot.py      # Slack bot implementation
│           └── runner.py   # Slack bot runner
├── users/                  # User examples and utilities
│   ├── basic_usage.py      # Basic usage example
│   ├── web_sample.py       # Web interface example
│   ├── setup/              # Setup scripts and guides
│   └── history/            # 🗄️ Database storage directory
│       └── pypoe_history.db  # SQLite database (created at runtime)
├── tests/                  # Test suite
├── pyproject.toml          # Package configuration
└── README.md
```

### Modular Architecture

PyPoe is organized into distinct modules for better maintainability:

- **`pypoe.poe`**: Core POE API functionality (always available)
- **`pypoe.web`**: Web interface with modern chat UI (optional)
- **`pypoe.slack`**: Slack bot integration (optional)
- **Shared Database**: All modules use the same SQLite database for conversation history

## API Reference

### PoeChatClient

The main client class for interacting with Poe bots.

```python
from pypoe import PoeChatClient

# Initialize with optional history
client = PoeChatClient(enable_history=True)

# Send a single message
async for chunk in client.send_message(
    message="Hello!",
    bot_name="GPT-3.5-Turbo",
    save_history=True
):
    print(chunk, end="")

# Send a conversation
conversation = [
    {"role": "user", "content": "What's 2+2?"},
    {"role": "bot", "content": "2+2 equals 4."},
    {"role": "user", "content": "What about 2+2+2?"}
]

async for chunk in client.send_conversation(conversation):
    print(chunk, end="")

# Get available bots
bots = await client.get_available_bots()
print(bots)  # ['GPT-3.5-Turbo', 'GPT-4-Turbo', 'Claude-3-Haiku', ...]

# Close the client
await client.close()
```

### History Management

History management is now built into the core package:

```python
from pypoe import HistoryManager

manager = HistoryManager()
await manager.initialize()

# Create a conversation
conv_id = await manager.save_conversation("My Chat")

# Save messages
await manager.save_message(conv_id, "user", "Hello!")
await manager.save_message(conv_id, "assistant", "Hi there!")

# Get conversations
conversations = await manager.get_conversations()

# Get messages from a conversation
messages = await manager.get_conversation_messages(conv_id)

# Database is automatically stored in user_scripts/history/conversations.db
print(f"Database location: {manager.get_db_path()}")
```

## Command Line Interface

### Basic Commands

```bash
# Send a single message
pypoe chat "Explain quantum computing" --bot GPT-4-Turbo

# Interactive chat
pypoe interactive --bot Claude-3-Sonnet --save-history

# List available bots
pypoe bots

# Show configuration status
pypoe status
```

### History Commands

```bash
# List conversations
pypoe conversations --limit 20

# Show messages from a conversation
pypoe messages <conversation-id>

# Delete a conversation
pypoe delete <conversation-id>
```

### Web Interface

```bash
# Start the web interface
pypoe web

# Run on custom host/port  
pypoe web --host 0.0.0.0 --port 3000
```

## Available Bots

PyPoe supports all bots available through the Poe API:

- **OpenAI**: GPT-3.5-Turbo, GPT-4, GPT-4-Turbo, GPT-4o
- **Anthropic**: Claude-3-Haiku, Claude-3-Sonnet, Claude-3-Opus, Claude-3.5-Sonnet
- **Meta**: Llama-3-70B-Instruct, Llama-3-8B-Instruct
- **Google**: Gemini-Pro, PaLM-2
- **And more**: Check `pypoe bots` for the complete current list

## Why Async/Streaming?

PyPoe uses async streaming for several benefits:

- **Real-time responses**: See output as it's generated
- **Better UX**: No waiting for complete responses
- **Slack bot friendly**: Perfect for real-time chat applications
- **Resource efficient**: Lower memory usage for long responses

## Error Handling

```python
try:
    client = PoeChatClient()
    async for chunk in client.send_message("Hello!"):
        print(chunk, end="")
except ValueError as e:
    if "POE_API_KEY is not set" in str(e):
        print("Please set up your API key: python user_scripts/setup_credentials.py")
except Exception as e:
    print(f"Error: {e}")
finally:
    await client.close()
```

## Development

### Running Tests

```bash
# Install development dependencies
pip install -e .[dev]

# Run tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=pypoe
```

### Project Structure Philosophy

- **`src/pypoe/`**: Core package code including HistoryManager
- **`user_scripts/`**: Examples and utilities
- **`user_scripts/history/`**: Database storage directory (keeps user data separate)
- **`tests/`**: Test suite with pytest configuration

This structure keeps the core functionality in the main package while storing user data (databases) in a separate directory.

## Slack Bot Integration

PyPoe includes a comprehensive Slack bot integration that brings AI chat directly to your workspace:

### Features
- 🤖 **Model Selection**: Choose from 100+ AI models (GPT-4, Claude, Gemini, etc.)
- 📊 **Usage Monitoring**: Track compute points and token usage per user
- 💬 **Multi-turn Conversations**: Persistent conversation context
- 🔄 **Real-time Switching**: Change models mid-conversation
- 📈 **Analytics**: Daily usage reports and model preferences

### Quick Setup
```bash
# Install PyPoe with Slack integration
pip install -e ".[slackbot]"

# Set environment variables
export POE_API_KEY="your-poe-api-key"
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_SIGNING_SECRET="your-signing-secret"
export SLACK_APP_TOKEN="xapp-your-app-token"  # For Socket Mode

# Run the bot
pypoe slack-bot
```

### Commands in Slack
- `/poe help` - Show help and available commands
- `/poe models` - List all available AI models
- `/poe set-model Claude-3-Sonnet` - Switch to specific model  
- `/poe chat Hello!` - Send a message to the AI
- `/poe usage` - Check your usage statistics
- `/poe reset` - Reset conversation history
- `@poe_bot <message>` - Mention the bot in any channel

See [users/setup/slack_setup.md](users/setup/slack_setup.md) for complete setup instructions.

## Web Interface

PyPoe includes a modern web interface for chatting with AI bots through your browser:

### Features
- 🌐 **Modern UI**: Clean, responsive chat interface with real-time streaming
- 🤖 **Bot Selection**: Choose from any available Poe bot mid-conversation
- 💬 **Conversation Management**: Create, view, and delete conversation history
- 📱 **Responsive Design**: Works on desktop, tablet, and mobile devices
- 🔄 **Real-time Chat**: WebSocket-based streaming responses
- 💾 **Shared Database**: Uses the same SQLite database as CLI and Slack bot

### Quick Start
```bash
# Install PyPoe with web UI support
pip install -e ".[web-ui]"

# Run the web interface
pypoe web

# Or run programmatically
python users/web_sample.py
```

### Web Interface Features

**Chat Interface:**
- Real-time streaming responses with typing indicators
- Message history with timestamps
- Bot switching during conversations
- Auto-expanding text input

**Conversation Management:**
- Sidebar with all conversations
- Create new conversations with custom titles
- Delete conversations with confirmation
- Persistent history across sessions

**Responsive Design:**
- Mobile-friendly interface
- Clean, modern styling
- Smooth animations and transitions
- Accessible design patterns

### API Endpoints

The web interface exposes RESTful endpoints:

```python
# Run the web app programmatically
from pypoe.web.app import create_app, run_server

# Create FastAPI app
app = create_app()

# Or run the server directly
run_server(host="localhost", port=8000)
```

**Available Endpoints:**
- `GET /` - Main chat interface
- `GET /api/conversations` - List all conversations
- `POST /api/conversation/new` - Create new conversation
- `GET /api/conversation/{id}/messages` - Get conversation messages
- `DELETE /api/conversation/{id}` - Delete conversation
- `GET /api/bots` - List available bots
- `WebSocket /ws/chat/{id}` - Real-time chat interface

### Configuration

The web interface uses the same configuration as the CLI:

```bash
# Required: Set your Poe API key
export POE_API_KEY="your-api-key-here"

# Optional: Custom database path
export DATABASE_PATH="users/history/pypoe_history.db"

# Run on custom host/port
pypoe web --host 0.0.0.0 --port 3000
```

**Database Integration:**
- Uses the same SQLite database as CLI and Slack bot
- Conversations created in web UI appear in CLI history
- Full compatibility across all PyPoe interfaces

## Terms of Service Compliance

✅ **FULLY COMPLIANT**: This implementation uses Poe's official API and complies with all Terms of Service:

- Uses legitimate `fastapi_poe` library and official API endpoints
- Requires valid Poe subscription and API key from poe.com/api_key  
- Respects all rate limits and usage restrictions
- No reverse engineering or unauthorized access
- Proper attribution of AI-generated content

**Rate Limits**: All limits respected ✅ (5s initial, 600s total, 512K chars, 10K events)

## Requirements

- Python 3.8+
- Poe subscription (for API access)
- Dependencies: `fastapi_poe`, `aiosqlite`, `python-dotenv`, `click`
- Optional: `slack-bolt`, `slack-sdk` (for Slack integration)

## License

MIT License - see LICENSE file for details.

## Support

- 📚 **Documentation**: Check the docstrings and examples in `user_scripts/`
- 🐛 **Issues**: Report bugs on GitHub Issues
- 💡 **Features**: Request features on GitHub Issues
- 📖 **Poe API Docs**: https://creator.poe.com/docs

## Changelog

### v2.0.0
- Complete rewrite using official Poe API
- Async/streaming architecture
- Built-in history management with HistoryManager in core package
- CLI interface with Click
- Src layout for clean package structure
- Comprehensive test suite
- Database storage in user_scripts/history/ for data separation
