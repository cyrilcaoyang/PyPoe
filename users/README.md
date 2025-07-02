# PyPoe User Directory

This directory contains user configuration files, examples, and setup utilities for PyPoe.

## 📁 Directory Structure

```
users/
├── pypoe.env.example          # Environment template file
├── basic_usage.py             # Simple usage example
├── setup/                     # One-time setup files
│   └── slack_setup.md         # Complete Slack bot setup guide
│   └── setup_credentials.py   # API key setup utility
└── history/                   # Local database storage (git-ignored)
    └── conversations.db       # SQLite database (created at runtime)
```

## 🚀 Quick Start

### 1. Set Up Environment
```bash
# Copy the template
cp users/pypoe.env.example .env

# Edit with your API key
# POE_API_KEY=your-api-key-here
```

### 2. Install PyPoe
```bash
# Basic installation (CLI + API client)
pip install -e .

# With Slack bot support
pip install -e ".[slackbot]"

# With everything
pip install -e ".[all]"
```

### 3. Set Up Credentials
```bash
python users/setup/setup_credentials.py
```

### 4. Test Basic Usage
```bash
python users/basic_usage.py
```

## 🤖 Slack Bot Setup

For Slack integration, see the comprehensive guide:
- **Setup Guide**: `users/setup/slack_setup.md`
- **Install**: `pip install -e ".[slackbot]"`
- **Run**: `pypoe slack-bot`

## 📊 Database Storage

Conversation history is stored in `users/history/conversations.db`

## 🎯 Available Installation Options

| Package | Command | Features |
|---------|---------|----------|
| **Core** | `pip install -e .` | CLI, API client, history |
| **Slack Bot** | `pip install -e ".[slackbot]"` | + Slack integration |
| **Web UI** | `pip install -e ".[web-ui]"` | + Web interface (coming soon) |
| **Development** | `pip install -e ".[dev]"` | + Testing tools |
| **Everything** | `pip install -e ".[all]"` | All features |

## 📚 Example Files

- **`basic_usage.py`**: Simple API usage example
- **`setup/setup_credentials.py`**: Interactive credential setup
- **`pypoe.env.example`**: Environment template with all options

## 🔧 Configuration

All configuration is done through environment variables:

```env
# Required
POE_API_KEY=your-poe-api-key

# Optional - Slack Integration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token

# Optional - Defaults
DEFAULT_BOT=GPT-4-Turbo
ENABLE_HISTORY=true
SLACK_SOCKET_MODE=true
```

## 🎉 Getting Started

1. **Try the core package**: `python users/basic_usage.py`
2. **Set up Slack bot**: Follow `users/setup/slack_setup.md`
3. **Explore CLI**: `pypoe --help`

Happy chatting! 🤖✨ 
