"""
History Management for PyPoe

This module provides local conversation history management using SQLite.
The database files are stored in users/history/ to keep user data
separate from the core package.

Classes:
    HistoryManager: Manages conversation history with SQLite storage

Usage:
    from pypoe.manager import HistoryManager
    
    manager = HistoryManager()
    await manager.initialize()
    
    # Save a conversation
    conv_id = await manager.save_conversation("My Chat")
    await manager.save_message(conv_id, "user", "Hello!")
"""

import aiosqlite
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any

class HistoryManager:
    """
    Manages conversation history with SQLite storage.
    
    The database is stored in users/history/ to keep user data
    separate from the core package files.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the history manager.
        
        Args:
            db_path: Custom database path. If None, uses default location
                    in users/history/ directory.
        """
        if db_path is None:
            # Find the project root (where user_scripts is located)
            # Start from this file's location and go up to find user_scripts
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = current_dir
            
            # Go up directories until we find users or reach the root
            for _ in range(5):  # Limit search depth
                project_root = os.path.dirname(project_root)
                users_path = os.path.join(project_root, 'users')
                if os.path.exists(users_path):
                    break
            else:
                # Fallback: use current working directory
                project_root = os.getcwd()
            
            # Store database in users/history/
            history_dir = os.path.join(project_root, 'users', 'history')
            db_path = os.path.join(history_dir, "conversations.db")
        
        self.db_path = db_path
        self._initialized = False
    
    async def initialize(self):
        """Initialize the database and create tables if they don't exist."""
        if self._initialized:
            return
            
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Create conversations table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create messages table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            """)
            
            await db.commit()
        
        self._initialized = True
    
    async def save_conversation(self, title: str) -> str:
        """
        Save a new conversation and return its ID.
        
        Args:
            title: The conversation title
            
        Returns:
            The conversation ID
        """
        await self.initialize()
        
        conversation_id = str(uuid.uuid4())
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO conversations (id, title) VALUES (?, ?)",
                (conversation_id, title)
            )
            await db.commit()
        
        return conversation_id
    
    async def save_message(self, conversation_id: str, role: str, content: str) -> int:
        """
        Save a message to a conversation.
        
        Args:
            conversation_id: The conversation ID
            role: The message role ('user' or 'assistant')
            content: The message content
            
        Returns:
            The message ID
        """
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conversation_id, role, content)
            )
            await db.commit()
            return cursor.lastrowid
    
    async def get_conversations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get a list of conversations.
        
        Args:
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversation dictionaries
        """
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT id, title, created_at, updated_at
                FROM conversations
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages for a conversation.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            List of message dictionaries with 'role' and 'content' keys
        """
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT role, content, timestamp
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """, (conversation_id,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation and all its messages.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            True if the conversation was deleted, False if it didn't exist
        """
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Delete messages first
            await db.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (conversation_id,)
            )
            
            # Delete conversation
            cursor = await db.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conversation_id,)
            )
            
            await db.commit()
            return cursor.rowcount > 0
    
    async def update_conversation_timestamp(self, conversation_id: str):
        """
        Update the conversation's updated_at timestamp.
        
        Args:
            conversation_id: The conversation ID
        """
        await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (conversation_id,)
            )
            await db.commit()
    
    async def get_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """
        Get conversation history in the format expected by the Poe API.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            List of messages with 'role' and 'content' keys
        """
        messages = await self.get_conversation_messages(conversation_id)
        
        # Convert to the format expected by the API
        history = []
        for msg in messages:
            # Map 'assistant' role to 'bot' for API compatibility
            role = msg['role']
            if role == 'assistant':
                role = 'bot'
            
            history.append({
                'role': role,
                'content': msg['content']
            })
        
        return history
    
    def get_db_path(self) -> str:
        """Get the path to the database file."""
        return self.db_path 