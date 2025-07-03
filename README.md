# PyPoe

A comprehensive Python client for interacting with Poe.com bots using the official Poe API. PyPoe provides three different interfaces to access AI models, all sharing the same conversation history database.

## 🎯 Use Cases

PyPoe offers **three ways** to interact with Poe AI models:

### 1. 🖥️ **Command Line Interface (CLI)**
Perfect for developers, automation, and terminal users:
```bash
# Single message
pypoe chat "Explain quantum computing" --bot GPT-4

# Interactive session  
pypoe interactive --bot Claude-3-Sonnet

# View conversation history
pypoe history --limit 10
```

### 2. 🌐 **Web Interface**
Modern browser-based chat with full history management:
- Two-panel layout: conversation sidebar + chat interface
- Search and filter conversations
- Statistics dashboard  
- Password protection for remote access
- Real-time streaming responses

### 3. 🤖 **Slack Bot**
Team collaboration via Slack workspace integration:
- Direct messages and channel mentions
- Multi-user support with usage tracking
- Model switching mid-conversation  
- Persistent conversation context

## 🗄️ Unified History Database

**All three interfaces share the same SQLite database** (`users/history/pypoe_history.db`), which means:

✅ **Cross-Platform Continuity**: Start a conversation in CLI, continue in Slack, review in web  
✅ **Unified Search**: Search all conversations regardless of origin  
✅ **Centralized Management**: Delete, export, and organize from any interface  
✅ **Complete History**: View all your AI interactions in one place  

## 📦 Installation Options

Choose the installation that fits your needs:

### Option 1: Minimal CLI Only
```bash
git clone https://github.com/your-username/pypoe.git
cd pypoe  
pip install -e .
```
**Includes**: Command line interface only  
**Use for**: Automation scripts and minimal deployments

### Option 2: CLI + Web Interface
```bash
git clone https://github.com/your-username/pypoe.git
cd pypoe
pip install -e ".[web-ui]"
```
**Includes**: Command line tools + web interface  
**Use for**: Personal use with both terminal and browser access  
**Note**: You need to run `pypoe web` to start the web server when you want to use the browser interface

### Option 3: Complete Installation (All Features)
```bash
git clone https://github.com/your-username/pypoe.git  
cd pypoe
pip install -e ".[all]"
```
**Includes**: CLI + Web + Slack bot integration  
**Use for**: Team deployments with all interface options  
**Note**: Slack bot requires the web interface, so this is the only way to get Slack functionality

### Option 4: Development Mode
```bash
git clone https://github.com/your-username/pypoe.git
cd pypoe
pip install -e ".[dev]"
```
**Includes**: Everything + testing tools + development dependencies  
**Use for**: Contributing to PyPoe or custom development

## 🚀 Quick Start

### 1. Get Your API Key
1. Visit [poe.com/api_key](https://poe.com/api_key) (requires Poe subscription)
2. Copy your API key

### 2. Configure PyPoe
Create a `.env` file in the project root:
```bash
cp users/pypoe.env.example .env
```

Edit `.env` and add your API key:
```env
# Required
POE_API_KEY="your-poe-api-key"

# Optional: Web interface authentication
PYPOE_WEB_USERNAME="admin"  
PYPOE_WEB_PASSWORD="your-secure-password"

# Optional: Custom host for Tailscale/remote access
PYPOE_HOST="100.XX.XX.XX"  # Your Tailscale IP
PYPOE_PORT=8000
```

### 3. Test Your Setup
```bash
# Test CLI
pypoe chat "Hello!" --bot GPT-3.5-Turbo

# Test web interface  
pypoe web
# Visit http://localhost:8000

# Test Slack bot (requires additional Slack app setup)
pypoe slack-bot
```

## 📋 CLI Reference

### Chat Commands
```bash
# Single message
pypoe chat "What is machine learning?" --bot GPT-4-Turbo

# Interactive session
pypoe interactive --bot Claude-3-Sonnet --save-history

# Continue existing conversation
pypoe interactive --conversation-id <id>
```

### History Management
```bash
# List conversations
pypoe conversations --limit 20

# View specific conversation
pypoe messages <conversation-id>

# Export history
pypoe history --format json --limit 50

# Delete conversation
pypoe delete <conversation-id>
```

### Bot Management
```bash
# List available bots
pypoe bots

# Check status and configuration
pypoe status
```

### Web Interface
```bash
# Start local web server
pypoe web

# Start with authentication
pypoe web --web-username admin --web-password secret

# Start on Tailscale network
pypoe web --host 100.XX.XX.XX --web-username admin --web-password secret

# Custom port
pypoe web --port 3000
```

### Slack Bot
```bash
# Start Slack bot (requires Slack app configuration)
pypoe slack-bot --enable-history

# Socket mode for development
pypoe slack-bot --socket-mode

# HTTP mode for production
pypoe slack-bot --http-mode
```

## 🌐 Web Interface Features

- **Two-Panel Layout**: Conversation list + active chat
- **Real-time Streaming**: WebSocket-based responses
- **Search & Filter**: Find conversations by content or bot
- **Statistics Dashboard**: Usage analytics and metrics
- **Authentication**: Optional username/password protection
- **Network Access**: Configurable for Tailscale or local networks
- **Responsive Design**: Works on desktop and mobile

## 🤖 Slack Bot Setup

1. **Create Slack App** at [api.slack.com/apps](https://api.slack.com/apps)
2. **Configure Environment Variables**:
   ```env
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   SLACK_SIGNING_SECRET=your-signing-secret  
   SLACK_APP_TOKEN=xapp-your-app-token  # For Socket Mode
   POE_API_KEY=your-poe-api-key
   ```
3. **Start the Bot**:
   ```bash
   pypoe slack-bot
   ```

### Slack Bot Commands
- `/poe help` - Show help message
- `/poe models` - List available AI models  
- `/poe chat <message>` - Send message to bot
- `/poe set-model <model>` - Switch AI model
- `/poe usage` - View usage statistics
- `/poe reset` - Reset conversation context

## 🔧 Configuration Options

### Environment Variables
```env
# Core Configuration
POE_API_KEY="your-api-key"                    # Required
DATABASE_PATH="users/history/pypoe_history.db" # Optional

# Web Interface  
PYPOE_HOST="localhost"                        # Default: localhost
PYPOE_PORT=8000                              # Default: 8000
PYPOE_WEB_USERNAME=""                        # Optional: enable auth
PYPOE_WEB_PASSWORD=""                        # Optional: auth password

# Slack Bot
SLACK_BOT_TOKEN="xoxb-..."                   # Required for Slack
SLACK_SIGNING_SECRET="..."                   # Required for Slack  
SLACK_APP_TOKEN="xapp-..."                   # Required for Socket Mode
SLACK_SOCKET_MODE="true"                     # true=dev, false=prod
```

### Command Line Overrides
All environment variables can be overridden via command line:
```bash
# Override host and authentication
pypoe web --host 0.0.0.0 --port 3000 --web-username admin --web-password secret

# Override database location  
pypoe chat "Hello" --database-path /custom/path/history.db
```

## 📊 Features Overview

| Feature | CLI | Web | Slack |
|---------|-----|-----|-------|
| Chat with AI models | ✅ | ✅ | ✅ |
| Conversation history | ✅ | ✅ | ✅ |
| Model switching | ✅ | ✅ | ✅ |
| Search conversations | ✅ | ✅ | ❌ |
| Real-time streaming | ✅ | ✅ | ❌ |
| Multi-user support | ❌ | ❌ | ✅ |
| Usage analytics | ✅ | ✅ | ✅ |
| Export conversations | ✅ | ✅ | ❌ |
| Authentication | ❌ | ✅ | ✅* |

*Slack authentication handled by Slack workspace permissions

## 🛠️ Development

### Running Tests
```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run specific test
pytest tests/test_client.py -v
```

### Project Structure
```
pypoe/
├── src/pypoe/
│   ├── cli.py          # Command line interface
│   ├── config.py       # Configuration management
│   ├── poe/            # Core Poe API client
│   ├── web/            # Web interface (FastAPI)
│   └── slack/          # Slack bot integration
├── users/              # User examples and data
│   ├── history/        # Shared conversation database
│   └── setup/         # Setup utilities
└── tests/             # Test suite
```

## 🔒 Security Notes

- **API Keys**: Never commit API keys to version control
- **Web Authentication**: Use strong passwords for remote access
- **Network Access**: Be careful when binding to `0.0.0.0` or public IPs
- **Database**: The SQLite database contains all conversation history

## 📝 License

[Your license here]

## 🤝 Contributing

1. Fork the repository
2. Install development dependencies: `pip install -e ".[dev]"`
3. Create a feature branch
4. Make your changes
5. Run tests: `pytest`
6. Submit a pull request

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/your-username/pypoe/issues)
- **Documentation**: Check `users/README.md` for examples
- **API Reference**: [Poe API Documentation](https://creator.poe.com/docs/quick-start)
