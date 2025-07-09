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

from ..config import get_config, Config
from ..poe.client import PoeChatClient

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
            allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|100\.64\.\d{1,3}\.\d{1,3}):(3000|5173|8000)",
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
            """Delete a conversation."""
            try:
                await self.client.delete_conversation(conversation_id)
                return JSONResponse({"success": True})
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

        @self.app.get("/api/config", dependencies=dependencies)
        async def get_config_info():
            """Get backend configuration information."""
            try:
                import socket
                
                available_bots = await self.client.get_available_bots()
                
                # Get network interfaces using socket
                network_interfaces = {}
                try:
                    # Get local IP addresses by connecting to external addresses
                    test_connections = [
                        ('8.8.8.8', 80),  # Google DNS
                        ('1.1.1.1', 80),  # Cloudflare DNS
                    ]
                    
                    local_ips = set()
                    for host, port in test_connections:
                        try:
                            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                                s.connect((host, port))
                                local_ip = s.getsockname()[0]
                                if not local_ip.startswith('127.'):
                                    local_ips.add(local_ip)
                        except:
                            continue
                    
                    # Categorize the IPs
                    for ip in local_ips:
                        if ip.startswith('100.64.'):
                            network_interfaces['tailscale'] = {
                                'ip': ip,
                                'frontend_url': f'http://{ip}:5173',
                                'backend_url': f'http://{ip}:8000'
                            }
                        elif ip.startswith('172.31.'):
                            network_interfaces['compsci'] = {
                                'ip': ip,
                                'frontend_url': f'http://{ip}:5173',
                                'backend_url': f'http://{ip}:8000'
                            }
                        elif ip.startswith('192.168.') or ip.startswith('10.'):
                            network_interfaces['local'] = {
                                'ip': ip,
                                'frontend_url': f'http://{ip}:5173',
                                'backend_url': f'http://{ip}:8000'
                            }
                    
                except Exception as e:
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
                    
                    # Stream bot response
                    full_response = ""
                    async for partial_response in self.client.send_message(
                        message=user_message,
                        bot_name=bot_name,
                        conversation_id=conversation_id,
                        save_history=True
                    ):
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