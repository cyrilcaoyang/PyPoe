# PyPoe

A Python client for interacting with Poe.com bots using the official Poe API.

## Installation

```bash
git clone https://github.com/your-username/pypoe.git
cd pypoe
pip install -e .
```

## Setup

1. Get your API key from [poe.com/api_key](https://poe.com/api_key) (requires Poe subscription)
2. Run: `python users/setup/setup_credentials.py`

## CLI Commands

### Chat Commands

```bash
# Send a single message
pypoe chat "What is machine learning?" --bot GPT-4-Turbo

# Interactive chat session
pypoe interactive --bot Claude-3-Sonnet

# Interactive chat with history saving
pypoe interactive --bot GPT-4-Turbo --save-history
```

### Bot Management

```bash
# List available bots
pypoe bots

# Check API status and configuration
pypoe status
```

### History Commands

```bash
# View conversation history (table format)
pypoe history --limit 10 --format table

# View conversation history (JSON format)
pypoe history --format json

# View all conversations with detailed statistics
pypoe history
```

### Web Interface

```bash
# Start web interface on http://localhost:8000
pypoe web --port 8000

# Start web interface on custom port
pypoe web --port 3000
```

### CLI Options Reference

#### Global Options
- `--config-file PATH`: Specify custom configuration file
- `--verbose`: Enable verbose logging
- `--quiet`: Suppress output except errors

#### Chat Options
- `--bot BOT_NAME`: Specify which bot to use (default: GPT-3.5-Turbo)
- `--save-history`: Save conversation to history database
- `--conversation-id ID`: Continue existing conversation

#### History Options
- `--limit N`: Limit number of conversations shown (default: 20)
- `--format FORMAT`: Output format - `table` or `json` (default: table)

#### Web Options
- `--port PORT`: Port number for web server (default: 8000)
- `--host HOST`: Host address to bind to (default: localhost)

## Recent Changes

### v2.0.0 - Web Interface & Enhanced History

#### 🌐 **New Web Interface**
- **Tabbed Interface**: Chat and History tabs in single page application
- **Real-time Chat**: WebSocket-based streaming responses
- **Conversation History**: Browse, search, and filter past conversations
- **Statistics Dashboard**: Total conversations, messages, and word counts
- **Modal Conversation Viewer**: Detailed view with navigation controls
- **Export Functionality**: Download conversations as text files
- **Mobile Responsive**: Works on all devices

#### 🖱️ **Enhanced Scrolling**
- **Auto-scroll**: Automatically scrolls to latest messages
- **Navigation Controls**: Visual up/down buttons and keyboard shortcuts (Home/End)
- **Smooth Scrolling**: CSS and JavaScript optimizations for better UX
- **Fixed Layouts**: Header and input areas stay in place while messages scroll

#### 📊 **Improved History Management**
- **Enhanced CLI**: New `pypoe history` command with table/JSON output formats
- **Search & Filter**: Find conversations by content or bot type
- **Conversation Management**: Delete, export, and continue conversations
- **Statistics**: Message counts, word counts, and creation dates
- **Unified Database**: Shared history across CLI and web interface

#### 🔧 **Technical Improvements**
- **Better Error Handling**: More informative error messages
- **Performance Optimizations**: Faster message loading and rendering
- **Code Organization**: Modular structure with clear separation of concerns
- **Testing Tools**: Debug scripts for troubleshooting

#### 🎨 **UI/UX Enhancements**
- **Modern Design**: Clean, responsive interface with FontAwesome icons
- **Loading States**: Visual feedback during message streaming
- **Keyboard Navigation**: Comprehensive keyboard shortcuts
- **Visual Feedback**: Clear status indicators and progress feedback

### Configuration

Create a `.env` file or use environment variables:

```env
POE_API_KEY=your_api_key_here
DEFAULT_BOT=GPT-4-Turbo
ENABLE_HISTORY=true
```
