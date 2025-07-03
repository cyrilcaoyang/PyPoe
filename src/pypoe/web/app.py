import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Request, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from ..config import get_config, Config
from ..poe.client import PoeChatClient

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

class WebApp:
    """FastAPI web application for PyPoe chat interface."""
    
    def __init__(self, config: Config = None):
        if config is None:
            config = get_config()
        
        self.config = config
        self.app = FastAPI(title="PyPoe Web Interface", version="2.0.0")
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
        
        # Active WebSocket connections for real-time chat
        self.active_connections: List[WebSocket] = []
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup all the routes for the web application."""
        
        @self.app.get("/", response_class=HTMLResponse)
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
        
        @self.app.post("/api/conversation/new")
        async def create_conversation(
            title: str = Form(...),
            bot_name: str = Form(...)
        ):
            """Create a new conversation."""
            try:
                conversation_id = await self.client.history.create_conversation(
                    title=title,
                    bot_name=bot_name
                )
                return JSONResponse({"conversation_id": conversation_id})
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/conversations")
        async def get_conversations():
            """Get all conversations."""
            try:
                conversations = await self.client.get_conversations()
                return JSONResponse(conversations)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/conversation/{conversation_id}/messages")
        async def get_conversation_messages(conversation_id: str):
            """Get messages for a specific conversation."""
            try:
                messages = await self.client.get_conversation_messages(conversation_id)
                return JSONResponse(messages)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/api/conversation/{conversation_id}")
        async def delete_conversation(conversation_id: str):
            """Delete a conversation."""
            try:
                await self.client.delete_conversation(conversation_id)
                return JSONResponse({"success": True})
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/bots")
        async def get_available_bots():
            """Get list of available bots."""
            try:
                bots = await self.client.get_available_bots()
                return JSONResponse(bots)
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
    web_app = WebApp(config)
    return web_app.app

def run_server(host: str = "localhost", port: int = 8000, config: Config = None):
    """Run the web server."""
    if not WEB_AVAILABLE:
        print("Web UI dependencies not installed. Please install with: pip install -e '.[web-ui]'")
        return
    
    app = create_app(config)
    uvicorn.run(app, host=host, port=port) 