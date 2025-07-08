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

class MessageSend(BaseModel):
    message: str
    bot_name: Optional[str] = None

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
            """Get all conversations."""
            try:
                conversations = await self.client.get_conversations()
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
                
                bot_name = message_data.bot_name or conversation.get('bot_name', 'GPT-3.5-Turbo')
                
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
        async def get_available_bots():
            """Get list of available bots."""
            try:
                bots = await self.client.get_available_bots()
                return JSONResponse(bots)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/conversations/search", dependencies=dependencies)
        async def search_conversations(q: str = "", bot: str = "", limit: int = 50):
            """Search conversations by title, content, or bot."""
            try:
                conversations = await self.client.get_conversations()
                
                # Filter by bot if specified
                if bot:
                    conversations = [c for c in conversations if c.get('bot_name', '').lower() == bot.lower()]
                
                # Search by query in title or content
                if q:
                    filtered_conversations = []
                    for conv in conversations:
                        # Search in title
                        if q.lower() in conv.get('title', '').lower():
                            filtered_conversations.append(conv)
                            continue
                        
                        # Search in message content
                        messages = await self.client.get_conversation_messages(conv['id'])
                        for msg in messages:
                            if q.lower() in msg.get('content', '').lower():
                                filtered_conversations.append(conv)
                                break
                    
                    conversations = filtered_conversations
                
                # Limit results
                conversations = conversations[:limit]
                
                # Add metadata
                for conv in conversations:
                    messages = await self.client.get_conversation_messages(conv['id'])
                    conv['message_count'] = len(messages)
                    conv['last_message'] = messages[-1] if messages else None
                
                return JSONResponse(conversations)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/stats", dependencies=dependencies)
        async def get_stats():
            """Get conversation statistics."""
            try:
                conversations = await self.client.get_conversations()
                
                total_conversations = len(conversations)
                total_messages = 0
                total_words = 0
                bot_usage = {}
                
                for conv in conversations:
                    messages = await self.client.get_conversation_messages(conv['id'])
                    total_messages += len(messages)
                    
                    for msg in messages:
                        total_words += len(msg.get('content', '').split())
                    
                    # Count bot usage
                    bot_name = conv.get('bot_name', 'Unknown')
                    bot_usage[bot_name] = bot_usage.get(bot_name, 0) + 1
                
                return JSONResponse({
                    "total_conversations": total_conversations,
                    "total_messages": total_messages,
                    "total_words": total_words,
                    "bot_usage": bot_usage,
                    "avg_messages_per_conversation": total_messages / total_conversations if total_conversations > 0 else 0
                })
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/config", dependencies=dependencies)
        async def get_config_info():
            """Get backend configuration information."""
            try:
                available_bots = await self.client.get_available_bots()
                
                config_info = {
                    "backend_version": "2.0.0",
                    "database_path": str(self.config.database_path),
                    "authentication_enabled": bool(self.config.web_username),
                    "username": self.config.web_username if self.config.web_username else None,
                    "available_bots": available_bots,
                    "total_bots": len(available_bots),
                    "api_endpoints": [
                        "/api/health",
                        "/api/conversations", 
                        "/api/bots",
                        "/api/stats",
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
                        "search_conversations": True,
                        "authentication": bool(self.config.web_username),
                        "websocket_chat": True,
                        "api_only_mode": False
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
                    bot_name = message_data.get("bot_name", "GPT-3.5-Turbo")
                    
                    if not user_message:
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
    uvicorn.run(app, host=host, port=port) 