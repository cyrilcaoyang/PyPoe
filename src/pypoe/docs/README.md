# PyPoe Documentation

Welcome to the PyPoe documentation! This folder contains comprehensive guides for setting up, configuring, and using PyPoe.

## 📚 Documentation Index

### 🚀 Setup & Configuration
- **[README_SETUP.md](README_SETUP.md)** - **START HERE!** Complete setup guide from installation to deployment
  - Prerequisites and installation options
  - Basic and advanced configuration
  - Interface setup (CLI, Web, Slack)
  - Deployment options and troubleshooting

### 🤖 Interface-Specific Guides
- **[README_SLACK.md](README_SLACK.md)** - Slack bot setup and configuration
  - Creating Slack apps and configuring permissions
  - Socket mode setup for development
  - Bot commands and troubleshooting
  
- **[README_DAEMON.md](README_DAEMON.md)** - Background service management
  - Running PyPoe as a daemon/service
  - Network access configuration
  - Health monitoring and troubleshooting

### 🔧 Advanced Features
- **[conversation_management.md](conversation_management.md)** - Conversation history and management
  - Database structure and operations
  - History export and import
  - Cross-interface conversation sharing

- **[bot_locking_feature.md](bot_locking_feature.md)** - Bot locking and model management
  - Preventing accidental model switches
  - Advanced conversation context management
  - Model-specific optimizations

## 🎯 Quick Start

1. **New to PyPoe?** Start with [README_SETUP.md](README_SETUP.md)
2. **Need Slack integration?** See [README_SLACK.md](README_SLACK.md)
3. **Running in production?** Check [README_DAEMON.md](README_DAEMON.md)
4. **Advanced features?** Browse the other documentation files

## 📋 Documentation Structure

```
src/pypoe/docs/
├── README.md                    # This file - documentation index
├── README_SETUP.md             # Complete setup guide (START HERE)
├── README_SLACK.md             # Slack bot setup guide
├── README_DAEMON.md            # Background service guide
├── conversation_management.md   # History and database management
└── bot_locking_feature.md      # Advanced bot features
```

## 🛠️ Getting Help

If you can't find what you're looking for:

1. **Check the main project** [README.md](../../../README.md) for an overview
2. **Search existing documentation** using Ctrl+F in your browser
3. **Look at example scripts** in `src/pypoe/scripts/`
4. **Create an issue** on GitHub with your specific question

## 📝 Contributing to Documentation

Found something unclear or missing? We welcome documentation improvements!

1. **Edit the relevant `.md` file** in this directory
2. **Follow the existing style** and structure
3. **Test any code examples** you add
4. **Submit a pull request** with your improvements

## 🔗 External Resources

- **[Poe API Documentation](https://creator.poe.com/docs/quick-start)** - Official Poe API reference
- **[Slack API Documentation](https://api.slack.com/start/overview)** - Slack app development
- **[FastAPI Documentation](https://fastapi.tiangolo.com/)** - Web interface framework
- **[Click Documentation](https://click.palletsprojects.com/)** - CLI framework

---

**Happy chatting with PyPoe!** 🤖✨ 