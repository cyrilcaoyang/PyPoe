import asyncio
import json
import secrets
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Request, Form, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from ...config import get_config, Config
from ...core.client import PoeChatClient
from ...logging_db import logger

# TODO: Add support for remote access of the webpage with username and password protection
# This would involve:
# - Adding authentication middleware (e.g., HTTP Basic Auth, session-based auth, or JWT)
# - User management system with secure password storage
# - Login/logout endpoints and templates
# - Session management and CSRF protection
# - Rate limiting and security headers
# - Optional: Multi-user support with user-specific conversation isolation

# Check if web dependencies are available
try:
    import fastapi
    import jinja2
    WEB_AVAILABLE = True
except ImportError:
    WEB_AVAILABLE = False

if not WEB_AVAILABLE:
    raise ImportError(
        "Web UI dependencies not installed. Please install with: pip install -e '.[web-ui]'"
    )

# Pydantic models for request bodies
class ConversationCreate(BaseModel):
    title: str
    bot_name: str
    chat_mode: Optional[str] = "chatbot"  # chatbot, group, debate

class MessageSend(BaseModel):
    message: str
    bot_name: Optional[str] = None
    chat_mode: Optional[str] = None

class WebApp:
    """FastAPI web application for PyPoe chat interface."""
    
    def __init__(self, config: Config = None):
        if config is None:
            config = get_config()
        
        self.config = config
        self.app = FastAPI(title="PyPoe Web Interface", version="2.0.0")
        
        # Add CORS middleware for React frontend
        self.app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|100\.64\.\d{1,3}\.\d{1,3}):(3000|5173|8000)",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self.client = PoeChatClient(config=config)
        
        # Setup templates and static files
        self.templates_dir = Path(__file__).parent / "templates"
        self.static_dir = Path(__file__).parent / "static"
        
        # Create directories if they don't exist
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.static_dir.mkdir(parents=True, exist_ok=True)
        
        self.templates = Jinja2Templates(directory=str(self.templates_dir))
        
        # Mount static files
        self.app.mount("/static", StaticFiles(directory=str(self.static_dir)), name="static")
        
        # Security
        self.security = HTTPBasic() if self.config.web_username else None
        
        # Active WebSocket connections for real-time chat
        self.active_connections: List[WebSocket] = []
        
        self._setup_routes()
        
        # Log system startup
        logger.log_system_event(
            event_type="startup",
            component="backend",
            action="start",
            new_value={
                "version": "2.0.0",
                "authentication_enabled": bool(self.config.web_username),
                "cors_enabled": True,
                "websocket_enabled": True
            },
            metadata={
                "config_file": str(self.config.config_file) if hasattr(self.config, 'config_file') else None,
                "database_path": str(self.config.database_path)
            }
        )
    
    def _check_credentials(self, credentials: HTTPBasicCredentials = Depends(HTTPBasic())):
        if not self.config.web_username:
            return
        correct_username = secrets.compare_digest(credentials.username, self.config.web_username)
        correct_password = secrets.compare_digest(credentials.password, self.config.web_password)
        if not (correct_username and correct_password):
            raise HTTPException(
                status_code=401,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Basic"},
            )
    
    def _setup_routes(self):
        """Setup all the routes for the web application."""
        
        dependencies = [Depends(self._check_credentials)] if self.security else []

        @self.app.get("/", response_class=HTMLResponse, dependencies=dependencies)
        async def index(request: Request):
            """Main chat interface."""
            try:
                conversations = await self.client.get_conversations()
                available_bots = await self.client.get_available_bots()
                return self.templates.TemplateResponse(
                    "index.html", 
                    {
                        "request": request,
                        "conversations": conversations,
                        "available_bots": available_bots
                    }
                )
            except Exception as e:
                return HTMLResponse(f"Error loading interface: {str(e)}", status_code=500)
        
        @self.app.get("/history", response_class=HTMLResponse, dependencies=dependencies)
        async def conversation_history(request: Request):
            """Conversation history browser."""
            try:
                conversations = await self.client.get_conversations()
                
                # Add message counts and last message info for each conversation
                for conv in conversations:
                    messages = await self.client.get_conversation_messages(conv['id'])
                    conv['message_count'] = len(messages)
                    conv['last_message'] = messages[-1] if messages else None
                
                return self.templates.TemplateResponse(
                    "history.html",
                    {
                        "request": request,
                        "conversations": conversations
                    }
                )
            except Exception as e:
                return HTMLResponse(f"Error loading history: {str(e)}", status_code=500)
        
        @self.app.get("/conversation/{conversation_id}", response_class=HTMLResponse, dependencies=dependencies)
        async def view_conversation(request: Request, conversation_id: str):
            """View a specific conversation in detail."""
            try:
                # Get conversation details
                conversations = await self.client.get_conversations()
                conversation = next((c for c in conversations if c['id'] == conversation_id), None)
                
                if not conversation:
                    raise HTTPException(status_code=404, detail="Conversation not found")
                
                # Get messages
                messages = await self.client.get_conversation_messages(conversation_id)
                
                # Add some metadata
                conversation['message_count'] = len(messages)
                conversation['word_count'] = sum(len(msg['content'].split()) for msg in messages)
                
                return self.templates.TemplateResponse(
                    "conversation_detail.html",
                    {
                        "request": request,
                        "conversation": conversation,
                        "messages": messages
                    }
                )
            except Exception as e:
                if isinstance(e, HTTPException):
                    raise e
                return HTMLResponse(f"Error loading conversation: {str(e)}", status_code=500)
        
        @self.app.get("/settings", response_class=HTMLResponse, dependencies=dependencies)
        async def settings(request: Request):
            """Settings and backend configuration page."""
            try:
                return self.templates.TemplateResponse(
                    "settings.html",
                    {
                        "request": request
                    }
                )
            except Exception as e:
                return HTMLResponse(f"Error loading settings: {str(e)}", status_code=500)

        @self.app.get("/storage", response_class=HTMLResponse, dependencies=dependencies)
        async def storage_management(request: Request):
            """Storage monitoring and management page."""
            try:
                return self.templates.TemplateResponse(
                    "storage.html",
                    {
                        "request": request
                    }
                )
            except Exception as e:
                return HTMLResponse(f"Error loading storage management: {str(e)}", status_code=500)
        
        @self.app.post("/api/conversation/new", dependencies=dependencies)
        async def create_conversation(conversation_data: ConversationCreate):
            """Create a new conversation."""
            try:
                conversation_id = await self.client.history.create_conversation(
                    title=conversation_data.title,
                    bot_name=conversation_data.bot_name
                )
                return JSONResponse({"conversation_id": conversation_id})
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/conversations", dependencies=dependencies)
        async def get_conversations():
            """Get all conversations with enhanced metadata."""
            try:
                conversations = await self.client.get_conversations()
                
                # Add metadata for each conversation
                for conv in conversations:
                    messages = await self.client.get_conversation_messages(conv['id'])
                    conv['message_count'] = len(messages)
                    conv['last_message'] = messages[-1] if messages else None
                    
                    # Add locking information based on conversation state
                    user_messages = [msg for msg in messages if msg.get('role') == 'user']
                    conv['has_messages'] = len(user_messages) > 0
                    conv['bot_locked'] = len(user_messages) > 0  # Bot is locked after first user message
                    conv['chat_mode_locked'] = len(user_messages) > 0  # Chat mode is locked after first user message
                
                # Sort by last updated (most recent first)
                conversations.sort(key=lambda x: x.get('updated_at', x.get('created_at', '')), reverse=True)
                
                return JSONResponse(conversations)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/conversation/{conversation_id}/messages", dependencies=dependencies)
        async def get_conversation_messages(conversation_id: str):
            """Get messages for a specific conversation."""
            try:
                messages = await self.client.get_conversation_messages(conversation_id)
                return JSONResponse(messages)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/api/conversation/{conversation_id}", dependencies=dependencies)
        async def delete_conversation(conversation_id: str):
            """Delete a conversation with enhanced media cleanup tracking."""
            try:
                # Check if enhanced history is available for media tracking
                media_cleanup_info = {"enhanced_storage": False, "media_files_deleted": 0}
                
                if hasattr(self.client.history, 'get_media_stats'):
                    # Enhanced storage available - get media stats before deletion
                    stats_before = await self.client.history.get_media_stats()
                    media_cleanup_info["enhanced_storage"] = True
                    media_cleanup_info["stats_before"] = stats_before
                
                # Delete the conversation
                await self.client.delete_conversation(conversation_id)
                
                if media_cleanup_info["enhanced_storage"]:
                    # Get stats after deletion to calculate cleanup
                    stats_after = await self.client.history.get_media_stats()
                    media_cleanup_info["stats_after"] = stats_after
                    media_cleanup_info["media_files_deleted"] = (
                        stats_before.get('total_files', 0) - stats_after.get('total_files', 0)
                    )
                    media_cleanup_info["storage_freed_mb"] = (
                        (stats_before.get('total_size_bytes', 0) - stats_after.get('total_size_bytes', 0)) 
                        / 1024 / 1024
                    )
                
                return JSONResponse({
                    "success": True,
                    "message": "Conversation deleted successfully",
                    "media_cleanup": media_cleanup_info
                })
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/storage/stats", dependencies=dependencies)
        async def get_storage_stats():
            """Get comprehensive storage statistics."""
            try:
                # Basic conversation stats (always available)
                conversations = await self.client.get_conversations()
                total_conversations = len(conversations)
                
                basic_stats = {
                    "total_conversations": total_conversations,
                    "database_path": str(self.config.database_path),
                    "enhanced_storage_available": hasattr(self.client.history, 'get_media_stats')
                }
                
                # Enhanced storage stats (if available)
                if hasattr(self.client.history, 'get_media_stats'):
                    media_stats = await self.client.history.get_media_stats()
                    
                    # Calculate database size
                    import os
                    db_size = 0
                    if os.path.exists(self.config.database_path):
                        db_size = os.path.getsize(self.config.database_path)
                    
                    # Get media directory info
                    media_dir_size = 0
                    media_dir_path = "N/A"
                    if hasattr(self.client.history, 'media_dir'):
                        media_dir_path = str(self.client.history.media_dir)
                        if os.path.exists(media_dir_path):
                            media_dir_size = sum(
                                os.path.getsize(os.path.join(dirpath, filename))
                                for dirpath, dirnames, filenames in os.walk(media_dir_path)
                                for filename in filenames
                            )
                    
                    enhanced_stats = {
                        "media_files": {
                            "total_files": media_stats.get('total_files', 0),
                            "total_size_bytes": media_stats.get('total_size_bytes', 0),
                            "total_size_mb": media_stats.get('total_size_bytes', 0) / 1024 / 1024,
                            "by_type": media_stats.get('by_type', {})
                        },
                        "storage_locations": {
                            "database": {
                                "path": str(self.config.database_path),
                                "size_bytes": db_size,
                                "size_mb": db_size / 1024 / 1024
                            },
                            "media_directory": {
                                "path": media_dir_path,
                                "size_bytes": media_dir_size,
                                "size_mb": media_dir_size / 1024 / 1024
                            }
                        },
                        "total_storage": {
                            "size_bytes": db_size + media_dir_size,
                            "size_mb": (db_size + media_dir_size) / 1024 / 1024
                        }
                    }
                    
                    return JSONResponse({**basic_stats, **enhanced_stats})
                
                return JSONResponse(basic_stats)
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/storage/cleanup", dependencies=dependencies)
        async def cleanup_orphaned_media():
            """Clean up orphaned media files."""
            try:
                if not hasattr(self.client.history, 'cleanup_orphaned_media'):
                    return JSONResponse({
                        "success": False,
                        "message": "Enhanced storage not available",
                        "files_cleaned": 0
                    })
                
                # Get stats before cleanup
                stats_before = await self.client.history.get_media_stats()
                
                # Run cleanup
                await self.client.history.cleanup_orphaned_media()
                
                # Get stats after cleanup
                stats_after = await self.client.history.get_media_stats()
                
                files_cleaned = stats_before.get('total_files', 0) - stats_after.get('total_files', 0)
                storage_freed = (stats_before.get('total_size_bytes', 0) - stats_after.get('total_size_bytes', 0)) / 1024 / 1024
                
                return JSONResponse({
                    "success": True,
                    "message": f"Cleaned up {files_cleaned} orphaned files",
                    "files_cleaned": files_cleaned,
                    "storage_freed_mb": storage_freed,
                    "stats_before": stats_before,
                    "stats_after": stats_after
                })
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/storage/conversations", dependencies=dependencies)
        async def get_conversations_with_storage_info():
            """Get conversations with enhanced storage information."""
            try:
                conversations = await self.client.get_conversations()
                
                # If enhanced storage is available, add media info
                if hasattr(self.client.history, 'get_conversations'):
                    enhanced_conversations = await self.client.history.get_conversations()
                    
                    # Create a lookup for enhanced data
                    enhanced_lookup = {conv['id']: conv for conv in enhanced_conversations}
                    
                    # Enhance the conversation data
                    for conv in conversations:
                        enhanced_data = enhanced_lookup.get(conv['id'], {})
                        conv.update({
                            'media_count': enhanced_data.get('media_count', 0),
                            'has_media': enhanced_data.get('has_media', False),
                            'message_count': enhanced_data.get('message_count', 0)
                        })
                
                return JSONResponse(conversations)
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/health")
        async def health_check():
            """Health check endpoint for React frontend."""
            try:
                # Check if client is working
                await self.client.get_available_bots()
                return JSONResponse({"status": "healthy", "version": "2.0.0"})
            except Exception as e:
                return JSONResponse({"status": "unhealthy", "error": str(e)}, status_code=503)

        @self.app.post("/api/conversation/{conversation_id}/send", dependencies=dependencies)
        async def send_message(conversation_id: str, message_data: MessageSend):
            """Send a message to a conversation (non-streaming)."""
            try:
                # Get the conversation to determine the bot
                conversations = await self.client.get_conversations()
                conversation = next((c for c in conversations if c['id'] == conversation_id), None)
                
                if not conversation:
                    raise HTTPException(status_code=404, detail="Conversation not found")
                
                # Get existing messages to check if conversation has started
                existing_messages = await self.client.get_conversation_messages(conversation_id)
                conversation_bot = conversation.get('bot_name', 'GPT-3.5-Turbo')
                conversation_chat_mode = conversation.get('chat_mode', 'chatbot')
                
                # Validation for conversations with existing messages
                if existing_messages:
                    user_messages = [msg for msg in existing_messages if msg.get('role') == 'user']
                    
                    # Bot locking: prevent changing bot mid-conversation
                    if user_messages and message_data.bot_name and message_data.bot_name != conversation_bot:
                        raise HTTPException(
                            status_code=400, 
                            detail=f"Cannot change bot mid-conversation. This conversation is locked to {conversation_bot}. "
                                   f"Current conversation has {len(user_messages)} user messages."
                        )
                    
                    # Chat mode locking: prevent changing chat mode mid-conversation
                    if user_messages and message_data.chat_mode and message_data.chat_mode != conversation_chat_mode:
                        raise HTTPException(
                            status_code=400, 
                            detail=f"Cannot change chat mode mid-conversation. This conversation is locked to {conversation_chat_mode} mode. "
                                   f"Current conversation has {len(user_messages)} user messages."
                        )
                    
                    bot_name = conversation_bot
                else:
                    # New conversation - allow bot and chat mode selection
                    bot_name = message_data.bot_name or conversation_bot
                
                # Collect the full response
                full_response = ""
                async for partial_response in self.client.send_message(
                    message=message_data.message,
                    bot_name=bot_name,
                    conversation_id=conversation_id,
                    save_history=True
                ):
                    full_response += partial_response
                
                return JSONResponse({
                    "message": full_response,
                    "role": "assistant",
                    "bot_name": bot_name,
                    "conversation_id": conversation_id
                })
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/bots", dependencies=dependencies)
        async def get_available_bots(conversation_id: str = None):
            """Get list of available bots with locking information for a specific conversation."""
            try:
                bots = await self.client.get_available_bots()
                
                # If conversation_id is provided, add locking information
                if conversation_id:
                    conversations = await self.client.get_conversations()
                    conversation = next((c for c in conversations if c['id'] == conversation_id), None)
                    
                    if conversation:
                        messages = await self.client.get_conversation_messages(conversation_id)
                        user_messages = [msg for msg in messages if msg.get('role') == 'user']
                        has_user_messages = len(user_messages) > 0
                        
                        conversation_bot = conversation.get('bot_name', 'GPT-3.5-Turbo')
                        conversation_chat_mode = conversation.get('chat_mode', 'chatbot')
                        
                        # Add locking metadata for the frontend
                        locking_info = {
                            "conversation_locked": has_user_messages,
                            "locked_bot": conversation_bot if has_user_messages else None,
                            "locked_chat_mode": conversation_chat_mode if has_user_messages else None,
                            "available_chat_modes": ["chatbot", "group", "debate"]
                        }
                        
                        return JSONResponse({
                            "bots": bots,
                            "locking": locking_info
                        })
                
                # Default response without locking information
                return JSONResponse({
                    "bots": bots,
                    "locking": {
                        "conversation_locked": False,
                        "locked_bot": None,
                        "locked_chat_mode": None,
                        "available_chat_modes": ["chatbot", "group", "debate"]
                    }
                })
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/conversations/search", dependencies=dependencies)
        async def search_conversations(
            q: str = "", 
            bot: str = "", 
            chat_mode: str = "",
            has_messages: bool = None,
            limit: int = 50,
            sort_by: str = "updated_at",  # updated_at, created_at, message_count, title
            sort_order: str = "desc"      # asc, desc
        ):
            """Advanced search and filtering for conversations."""
            try:
                conversations = await self.client.get_conversations()
                
                # Add metadata first (we'll need this for filtering and sorting)
                for conv in conversations:
                    messages = await self.client.get_conversation_messages(conv['id'])
                    conv['message_count'] = len(messages)
                    conv['last_message'] = messages[-1] if messages else None
                    
                    # Add locking information
                    user_messages = [msg for msg in messages if msg.get('role') == 'user']
                    conv['has_messages'] = len(user_messages) > 0
                    conv['bot_locked'] = len(user_messages) > 0
                    conv['chat_mode_locked'] = len(user_messages) > 0
                    
                    # Add search-friendly content for full-text search
                    conv['searchable_content'] = ' '.join([
                        conv.get('title', ''),
                        ' '.join([msg.get('content', '') for msg in messages])
                    ]).lower()
                
                # Apply filters
                filtered_conversations = []
                
                for conv in conversations:
                    # Filter by bot
                    if bot and conv.get('bot_name', '').lower() != bot.lower():
                        continue
                    
                    # Filter by chat mode
                    if chat_mode and conv.get('chat_mode', '').lower() != chat_mode.lower():
                        continue
                    
                    # Filter by message presence
                    if has_messages is not None:
                        if has_messages and not conv['has_messages']:
                            continue
                        if not has_messages and conv['has_messages']:
                            continue
                    
                    # Search by query (title and content)
                    if q and q.lower() not in conv['searchable_content']:
                        continue
                    
                    filtered_conversations.append(conv)
                
                # Sort conversations
                reverse_order = sort_order.lower() == "desc"
                
                if sort_by == "message_count":
                    filtered_conversations.sort(key=lambda x: x['message_count'], reverse=reverse_order)
                elif sort_by == "title":
                    filtered_conversations.sort(key=lambda x: x.get('title', '').lower(), reverse=reverse_order)
                elif sort_by == "created_at":
                    filtered_conversations.sort(key=lambda x: x.get('created_at', ''), reverse=reverse_order)
                else:  # default to updated_at
                    filtered_conversations.sort(key=lambda x: x.get('updated_at', x.get('created_at', '')), reverse=reverse_order)
                
                # Limit results
                filtered_conversations = filtered_conversations[:limit]
                
                # Clean up search field before returning
                for conv in filtered_conversations:
                    del conv['searchable_content']
                
                return JSONResponse({
                    "conversations": filtered_conversations,
                    "total_found": len(filtered_conversations),
                    "filters_applied": {
                        "query": q if q else None,
                        "bot": bot if bot else None,
                        "chat_mode": chat_mode if chat_mode else None,
                        "has_messages": has_messages,
                        "sort_by": sort_by,
                        "sort_order": sort_order,
                        "limit": limit
                    }
                })
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/stats", dependencies=dependencies)
        async def get_stats():
            """Get comprehensive conversation statistics."""
            try:
                conversations = await self.client.get_conversations()
                
                total_conversations = len(conversations)
                total_messages = 0
                total_user_messages = 0
                total_assistant_messages = 0
                total_words = 0
                total_user_words = 0
                total_assistant_words = 0
                bot_usage = {}
                chat_mode_usage = {}
                active_conversations = 0  # Conversations with messages
                
                for conv in conversations:
                    messages = await self.client.get_conversation_messages(conv['id'])
                    conversation_message_count = len(messages)
                    total_messages += conversation_message_count
                    
                    if conversation_message_count > 0:
                        active_conversations += 1
                    
                    user_messages_count = 0
                    assistant_messages_count = 0
                    
                    for msg in messages:
                        content = msg.get('content', '')
                        words = len(content.split())
                        total_words += words
                        
                        if msg.get('role') == 'user':
                            total_user_messages += 1
                            total_user_words += words
                            user_messages_count += 1
                        elif msg.get('role') == 'assistant':
                            total_assistant_messages += 1
                            total_assistant_words += words
                            assistant_messages_count += 1
                    
                    # Count bot usage
                    bot_name = conv.get('bot_name', 'Unknown')
                    bot_usage[bot_name] = bot_usage.get(bot_name, 0) + 1
                    
                    # Count chat mode usage
                    chat_mode = conv.get('chat_mode', 'chatbot')
                    chat_mode_usage[chat_mode] = chat_mode_usage.get(chat_mode, 0) + 1
                
                return JSONResponse({
                    "total_conversations": total_conversations,
                    "active_conversations": active_conversations,
                    "total_messages": total_messages,
                    "total_user_messages": total_user_messages,
                    "total_assistant_messages": total_assistant_messages,
                    "total_words": total_words,
                    "total_user_words": total_user_words,
                    "total_assistant_words": total_assistant_words,
                    "bot_usage": bot_usage,
                    "chat_mode_usage": chat_mode_usage,
                    "avg_messages_per_conversation": total_messages / total_conversations if total_conversations > 0 else 0,
                    "avg_messages_per_active_conversation": total_messages / active_conversations if active_conversations > 0 else 0,
                    "avg_words_per_message": total_words / total_messages if total_messages > 0 else 0,
                    "avg_user_words_per_message": total_user_words / total_user_messages if total_user_messages > 0 else 0,
                    "avg_assistant_words_per_message": total_assistant_words / total_assistant_messages if total_assistant_messages > 0 else 0
                })
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/network-status", dependencies=dependencies)
        async def get_network_status():
            """Get current network interface status (dynamic detection)."""
            try:
                import subprocess
                import platform
                from datetime import datetime
                
                network_interfaces = {}
                detected_ips = set()
                
                # Use the same comprehensive detection logic
                system = platform.system().lower()
                
                if system == "darwin":  # macOS
                    try:
                        result = subprocess.run(['ifconfig'], capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            lines = result.stdout.split('\n')
                            for line in lines:
                                if 'inet ' in line and 'inet 127.' not in line and 'inet 169.254.' not in line:
                                    parts = line.split()
                                    if len(parts) >= 2:
                                        ip = parts[1]
                                        if '.' in ip and not ip.startswith('127.') and not ip.startswith('169.254.'):
                                            detected_ips.add(ip)
                    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                        pass
                
                elif system == "linux":
                    try:
                        result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            lines = result.stdout.split('\n')
                            for line in lines:
                                if 'inet ' in line and '/127.' not in line and '/169.254.' not in line:
                                    parts = line.strip().split()
                                    for part in parts:
                                        if '.' in part and '/' in part:
                                            ip = part.split('/')[0]
                                            if not ip.startswith('127.') and not ip.startswith('169.254.'):
                                                detected_ips.add(ip)
                    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                        pass
                
                # Fallback detection methods
                test_connections = [('8.8.8.8', 80), ('1.1.1.1', 80)]
                for host, port in test_connections:
                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                            s.connect((host, port))
                            local_ip = s.getsockname()[0]
                            if not local_ip.startswith('127.') and not local_ip.startswith('169.254.'):
                                detected_ips.add(local_ip)
                    except:
                        continue
                
                print(f"[Network Status] Found IPs: {sorted(detected_ips)}")
                
                # Categorize and test detected IPs
                for ip in detected_ips:
                    category = None
                    if ip.startswith('100.64.'):
                        category = 'tailscale'
                    elif ip.startswith('172.29.'):
                        category = 'compsci_vpn'
                    elif ip.startswith('172.31.'):
                        category = 'compsci_wifi'
                    elif ip.startswith('192.168.') or ip.startswith('10.'):
                        category = 'local'
                    
                    if category:
                        # Test connectivity instead of binding (more reliable)
                        is_reachable = False
                        try:
                            # Try to connect to ourselves on this interface (if backend is running)
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_sock:
                                test_sock.settimeout(1)  # Quick timeout
                                result = test_sock.connect_ex((ip, 8000))
                                is_reachable = (result == 0)  # 0 means connection successful
                        except:
                            # If connection test fails, assume interface is reachable
                            # (backend might not be bound to this interface yet)
                            is_reachable = True
                        
                        # Always add detected interfaces (if we can detect them, they're likely usable)
                        status = 'active' if is_reachable else 'detected'
                        network_interfaces[category] = {
                            'ip': ip,
                            'frontend_url': f'http://{ip}:5173',
                            'backend_url': f'http://{ip}:8000',
                            'status': status,
                            'last_checked': str(datetime.now())
                        }
                        print(f"[Network Status] {category} network detected: {ip} (status: {status})")
                        
                        # Log network detection event
                        logger.log_network_event(
                            event_type="detection",
                            network_type=category,
                            ip_address=ip,
                            status=status,
                            frontend_url=f'http://{ip}:5173',
                            backend_url=f'http://{ip}:8000',
                            metadata={
                                "detection_method": "network-status-endpoint",
                                "is_reachable": is_reachable,
                                "detected_ips_count": len(detected_ips)
                            }
                        )
                
                return JSONResponse({
                    "network_interfaces": network_interfaces,
                    "total_interfaces": len(network_interfaces),
                    "timestamp": str(datetime.now())
                })
            except Exception as e:
                print(f"[Network Status] Error: {str(e)}")
                return JSONResponse({
                    "network_interfaces": {"error": f"Failed to detect interfaces: {str(e)}"},
                    "total_interfaces": 0,
                    "timestamp": str(datetime.now())
                })

        @self.app.get("/api/config", dependencies=dependencies)
        async def get_config_info():
            """Get backend configuration information."""
            try:
                import socket
                from datetime import datetime
                
                available_bots = await self.client.get_available_bots()
                
                # Get network interfaces using comprehensive detection
                network_interfaces = {}
                try:
                    import subprocess
                    import platform
                    
                    detected_ips = set()
                    
                    # Method 1: Use platform-specific commands for comprehensive interface detection
                    system = platform.system().lower()
                    
                    if system == "darwin":  # macOS
                        try:
                            # Get all interface IPs using ifconfig
                            result = subprocess.run(['ifconfig'], capture_output=True, text=True, timeout=5)
                            if result.returncode == 0:
                                lines = result.stdout.split('\n')
                                for line in lines:
                                    if 'inet ' in line and 'inet 127.' not in line and 'inet 169.254.' not in line:
                                        # Extract IP using split
                                        parts = line.split()
                                        if len(parts) >= 2:
                                            ip = parts[1]
                                            # Validate it's a proper IP
                                            if '.' in ip and not ip.startswith('127.') and not ip.startswith('169.254.'):
                                                detected_ips.add(ip)
                        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                            pass
                    
                    elif system == "linux":
                        try:
                            # Try ip command first
                            result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True, timeout=5)
                            if result.returncode == 0:
                                lines = result.stdout.split('\n')
                                for line in lines:
                                    if 'inet ' in line and '/127.' not in line and '/169.254.' not in line:
                                        # Extract IP using split
                                        parts = line.strip().split()
                                        for part in parts:
                                            if '.' in part and '/' in part:
                                                ip = part.split('/')[0]
                                                if not ip.startswith('127.') and not ip.startswith('169.254.'):
                                                    detected_ips.add(ip)
                        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                            # Fallback to ifconfig on Linux
                            try:
                                result = subprocess.run(['ifconfig'], capture_output=True, text=True, timeout=5)
                                if result.returncode == 0:
                                    lines = result.stdout.split('\n')
                                    for line in lines:
                                        if 'inet ' in line and 'inet 127.' not in line:
                                            parts = line.split()
                                            if len(parts) >= 2:
                                                ip = parts[1]
                                                if '.' in ip and not ip.startswith('127.') and not ip.startswith('169.254.'):
                                                    detected_ips.add(ip)
                            except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                                pass
                    
                    # Method 2: Fallback to socket-based detection for any missed interfaces
                    test_connections = [
                        ('8.8.8.8', 80),  # Google DNS
                        ('1.1.1.1', 80),  # Cloudflare DNS
                    ]
                    
                    for host, port in test_connections:
                        try:
                            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                                s.connect((host, port))
                                local_ip = s.getsockname()[0]
                                if not local_ip.startswith('127.') and not local_ip.startswith('169.254.'):
                                    detected_ips.add(local_ip)
                        except:
                            continue
                    
                    # Method 3: Also try connecting to common local network gateways
                    local_gateways = ['192.168.1.1', '192.168.0.1', '10.0.0.1', '172.16.0.1']
                    for gateway in local_gateways:
                        try:
                            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                                s.settimeout(1)
                                s.connect((gateway, 53))  # DNS port
                                local_ip = s.getsockname()[0]
                                if not local_ip.startswith('127.') and not local_ip.startswith('169.254.'):
                                    detected_ips.add(local_ip)
                        except:
                            continue
                    
                    print(f"[Network Detection] Found IPs: {sorted(detected_ips)}")
                    
                    # Categorize and test connectivity of detected IPs
                    for ip in detected_ips:
                        category = None
                        if ip.startswith('100.64.'):
                            category = 'tailscale'
                        elif ip.startswith('172.29.'):
                            category = 'compsci_vpn'
                        elif ip.startswith('172.31.'):
                            category = 'compsci_wifi'
                        elif ip.startswith('192.168.') or ip.startswith('10.'):
                            category = 'local'
                        
                        if category:
                            # Always add detected interfaces (if we can detect them, they're likely usable)
                            network_interfaces[category] = {
                                'ip': ip,
                                'frontend_url': f'http://{ip}:5173',
                                'backend_url': f'http://{ip}:8000',
                                'status': 'detected'
                            }
                            print(f"[Network Detection] {category} network detected: {ip}")
                            
                            # Log network detection event
                            logger.log_network_event(
                                event_type="detection",
                                network_type=category,
                                ip_address=ip,
                                status='detected',
                                frontend_url=f'http://{ip}:5173',
                                backend_url=f'http://{ip}:8000',
                                metadata={
                                    "detection_method": "config-endpoint",
                                    "detected_ips_count": len(detected_ips)
                                }
                            )
                    
                except Exception as e:
                    print(f"[Network Detection] Error: {str(e)}")
                    network_interfaces = {"error": f"Failed to detect interfaces: {str(e)}"}
                
                config_info = {
                    "backend_version": "2.0.0",
                    "database_path": str(self.config.database_path),
                    "authentication_enabled": bool(self.config.web_username),
                    "username": self.config.web_username if self.config.web_username else None,
                    "available_bots": available_bots,
                    "total_bots": len(available_bots),
                    "network_interfaces": network_interfaces,
                    "api_endpoints": [
                        "/api/health",
                        "/api/conversations",  # Enhanced with metadata and locking info
                        "/api/conversations/search",  # Advanced search with filtering/sorting
                        "/api/bots",  # Enhanced with conversation-specific locking
                        "/api/stats",  # Comprehensive statistics
                        "/api/storage/stats",  # Storage monitoring and analytics
                        "/api/storage/cleanup",  # Media cleanup operations
                        "/api/storage/conversations",  # Conversations with storage info
                        "/api/account/status",  # Account status and usage monitoring
                        "/api/network-status",  # Dynamic network interface detection
                        "/api/logs/network",  # Network activity logs
                        "/api/logs/system",  # System activity logs
                        "/api/config",
                        "/api/conversation/new",
                        "/api/conversation/{id}/messages",
                        "/api/conversation/{id}/send",
                        "/ws/chat/{id}"
                    ],
                    "cors_enabled": True,
                    "websocket_enabled": True,
                    "features": {
                        "real_time_streaming": True,
                        "conversation_history": True,
                        "multi_bot_support": True,
                        "advanced_search": True,  # Enhanced search with filtering/sorting
                        "conversation_metadata": True,  # Message counts, locking info, etc.
                        "comprehensive_stats": True,  # Detailed statistics including word counts
                        "dynamic_locking": True,  # Context-aware bot/mode locking
                        "account_monitoring": True,  # API key status and usage tracking
                        "authentication": bool(self.config.web_username),
                        "websocket_chat": True,
                        "api_only_mode": False,
                        "bot_locking": True,
                        "chat_mode_locking": True,
                        "database_consistency": True,
                        "backend_business_logic": True  # All logic handled in backend
                    }
                }
                
                return JSONResponse(config_info)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/logs/network", dependencies=dependencies)
        async def get_network_logs(
            limit: int = 100,
            network_type: str = None,
            since: str = None
        ):
            """Get network activity logs."""
            try:
                logs = logger.get_network_logs(
                    limit=limit,
                    network_type=network_type,
                    since=since
                )
                summary = logger.get_network_summary()
                
                return JSONResponse({
                    "logs": logs,
                    "summary": summary,
                    "total_logs": len(logs),
                    "filters": {
                        "limit": limit,
                        "network_type": network_type,
                        "since": since
                    }
                })
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/logs/system", dependencies=dependencies)
        async def get_system_logs(
            limit: int = 100,
            component: str = None,
            since: str = None
        ):
            """Get system activity logs."""
            try:
                logs = logger.get_system_logs(
                    limit=limit,
                    component=component,
                    since=since
                )
                
                return JSONResponse({
                    "logs": logs,
                    "total_logs": len(logs),
                    "filters": {
                        "limit": limit,
                        "component": component,
                        "since": since
                    }
                })
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/account/status", dependencies=dependencies)
        async def get_account_status():
            """Get comprehensive account status information."""
            try:
                import time
                from datetime import datetime, timedelta
                
                status_data = {
                    "timestamp": datetime.now().isoformat(),
                    "api_key_configured": bool(self.config.poe_api_key),
                    "api_key_status": "unknown",
                    "connectivity": {
                        "status": "unknown",
                        "response_time_ms": None,
                        "last_checked": None
                    },
                    "storage_usage": {
                        "database_size_mb": 0,
                        "total_conversations": 0
                    }
                }
                
                # Test API key and connectivity
                if self.config.poe_api_key:
                    try:
                        start_time = time.time()
                        
                        # Quick connectivity test - try to get available bots
                        await self.client.get_available_bots()
                        
                        end_time = time.time()
                        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
                        
                        status_data["api_key_status"] = "valid"
                        status_data["connectivity"]["status"] = "connected"
                        status_data["connectivity"]["response_time_ms"] = round(response_time, 2)
                        status_data["connectivity"]["last_checked"] = datetime.now().isoformat()
                        
                    except Exception as api_error:
                        error_msg = str(api_error).lower()
                        if "invalid" in error_msg or "unauthorized" in error_msg:
                            status_data["api_key_status"] = "invalid"
                        elif "insufficient" in error_msg or "quota" in error_msg:
                            status_data["api_key_status"] = "quota_exceeded"
                        else:
                            status_data["api_key_status"] = "error"
                        
                        status_data["connectivity"]["status"] = "error"
                        status_data["connectivity"]["error"] = str(api_error)
                else:
                    status_data["api_key_status"] = "not_configured"
                
                # Get storage information
                try:
                    import os
                    if os.path.exists(self.config.database_path):
                        db_size = os.path.getsize(self.config.database_path)
                        status_data["storage_usage"]["database_size_mb"] = round(db_size / 1024 / 1024, 2)
                    
                    conversations = await self.client.get_conversations()
                    status_data["storage_usage"]["total_conversations"] = len(conversations)
                    
                except Exception as storage_error:
                    status_data["storage_usage"]["error"] = str(storage_error)
                
                return JSONResponse(status_data)
                
            except Exception as e:
                return JSONResponse({
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                    "api_key_configured": bool(self.config.poe_api_key),
                    "api_key_status": "error"
                }, status_code=500)

        @self.app.websocket("/ws/chat/{conversation_id}")
        async def websocket_chat(websocket: WebSocket, conversation_id: str):
            """WebSocket endpoint for real-time chat."""
            await websocket.accept()
            self.active_connections.append(websocket)
            
            try:
                while True:
                    # Receive message from client
                    data = await websocket.receive_text()
                    message_data = json.loads(data)
                    
                    user_message = message_data.get("message", "")
                    requested_bot = message_data.get("bot_name", "GPT-3.5-Turbo")
                    requested_chat_mode = message_data.get("chat_mode", "chatbot")
                    
                    if not user_message:
                        continue
                    
                    # Get conversation info and validate bot/chat mode selection
                    try:
                        conversations = await self.client.get_conversations()
                        conversation = next((c for c in conversations if c['id'] == conversation_id), None)
                        
                        if not conversation:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "content": "Conversation not found"
                            }))
                            continue
                        
                        # Get existing messages to check if conversation has started
                        existing_messages = await self.client.get_conversation_messages(conversation_id)
                        conversation_bot = conversation.get('bot_name', 'GPT-3.5-Turbo')
                        conversation_chat_mode = conversation.get('chat_mode', 'chatbot')
                        
                        # Validation for conversations with existing messages
                        if existing_messages:
                            user_messages = [msg for msg in existing_messages if msg.get('role') == 'user']
                            
                            # Bot locking: prevent changing bot mid-conversation
                            if user_messages and requested_bot != conversation_bot:
                                await websocket.send_text(json.dumps({
                                    "type": "error",
                                    "content": f"Cannot change bot mid-conversation. This conversation is locked to {conversation_bot}. "
                                              f"Current conversation has {len(user_messages)} user messages."
                                }))
                                continue
                            
                            # Chat mode locking: prevent changing chat mode mid-conversation
                            if user_messages and requested_chat_mode != conversation_chat_mode:
                                await websocket.send_text(json.dumps({
                                    "type": "error",
                                    "content": f"Cannot change chat mode mid-conversation. This conversation is locked to {conversation_chat_mode} mode. "
                                              f"Current conversation has {len(user_messages)} user messages."
                                }))
                                continue
                            
                            bot_name = conversation_bot
                        else:
                            # New conversation - allow bot and chat mode selection
                            bot_name = requested_bot
                        
                    except Exception as e:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "content": f"Error validating conversation: {str(e)}"
                        }))
                        continue
                    
                    # Send user message back to confirm receipt
                    await websocket.send_text(json.dumps({
                        "type": "user_message",
                        "content": user_message,
                        "role": "user"
                    }))
                    
                    # Send bot response start indicator
                    await websocket.send_text(json.dumps({
                        "type": "bot_response_start",
                        "role": "assistant"
                    }))
                    
                    # Stream bot response (filtering already handled in client.py)
                    full_response = ""
                    
                    async for partial_response in self.client.send_message(
                        message=user_message,
                        bot_name=bot_name,
                        conversation_id=conversation_id,
                        save_history=True
                    ):
                        # Only send non-empty chunks (client.py already filters generating messages)
                        if partial_response:
                            full_response += partial_response
                            await websocket.send_text(json.dumps({
                                "type": "bot_response_chunk",
                                "content": partial_response,
                                "role": "assistant"
                            }))
                    
                    # Send bot response end indicator
                    await websocket.send_text(json.dumps({
                        "type": "bot_response_end",
                        "role": "assistant"
                    }))
                    
            except WebSocketDisconnect:
                self.active_connections.remove(websocket)
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "content": f"Error: {str(e)}"
                }))
                self.active_connections.remove(websocket)
    
    async def close(self):
        """Clean up resources."""
        # Log system shutdown
        logger.log_system_event(
            event_type="shutdown",
            component="backend",
            action="stop",
            metadata={
                "active_connections": len(self.active_connections),
                "graceful_shutdown": True
            }
        )
        await self.client.close()

def create_app(config: Config = None) -> FastAPI:
    """Factory function to create the FastAPI app."""
    if not WEB_AVAILABLE:
        raise RuntimeError("Web UI dependencies not installed.")
    
    web_app = WebApp(config)
    return web_app.app

def run_server(host: str = "localhost", port: int = 8000, config: Config = None):
    """Run the web server."""
    if not WEB_AVAILABLE:
        print("Web UI dependencies not installed. Please install with: pip install -e '.[web-ui]'")
        return
    
    app = create_app(config)
    
    # Enhanced uvicorn configuration for production
    uvicorn_config = {
        "app": app,
        "host": host,
        "port": port,
        "log_level": "info",
        "access_log": True,
        "server_header": False,  # Hide server header for security
        "date_header": False,    # Hide date header for security
    }
    
    # Add graceful shutdown handling
    import signal
    import asyncio
    
    def signal_handler(sig, frame):
        print(f"\n👋 Received signal {sig}, shutting down gracefully...")
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        uvicorn.run(**uvicorn_config)
    except KeyboardInterrupt:
        print("\n👋 Server shutdown complete")
    except Exception as e:
        print(f"❌ Server error: {e}")
        raise 