import aiosqlite
import asyncio
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

class HistoryManager:
    """Manages the SQLite database for chat history."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Creates the database and tables if they don't exist."""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        bot_name TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conversation_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(conversation_id) REFERENCES conversations(id)
                    )
                """)
                await db.commit()

    async def create_conversation(self, title: str, bot_name: str, chat_mode: str = "chatbot") -> str:
        """Creates a new conversation and returns its ID."""
        conversation_id = str(uuid.uuid4())
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO conversations (id, title, bot_name) VALUES (?, ?, ?)",
                    (conversation_id, title, bot_name)
                )
                await db.commit()
        return conversation_id

    async def add_message(self, conversation_id: str, role: str, content: str, bot_name: Optional[str] = None):
        """Adds a message to a conversation."""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                    (conversation_id, role, content)
                )
                await db.commit()

    async def get_conversations(self) -> List[Dict[str, Any]]:
        """Gets all conversations."""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT id, title, bot_name, created_at
                    FROM conversations
                    ORDER BY created_at DESC
                """)
                rows = await cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "title": row[1],
                        "bot_name": row[2],
                        "created_at": row[3]
                    } for row in rows
                ]

    async def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Gets all messages for a conversation."""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT role, content, timestamp
                    FROM messages
                    WHERE conversation_id = ?
                    ORDER BY timestamp ASC
                """, (conversation_id,))
                rows = await cursor.fetchall()
                return [
                    {
                        "role": row[0],
                        "content": row[1],
                        "timestamp": row[2]
                    } for row in rows
                ]

    async def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Alias for get_messages for compatibility with other history managers."""
        return await self.get_messages(conversation_id)

    async def delete_conversation(self, conversation_id: str):
        """Deletes a conversation and all its messages."""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
                await db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
                await db.commit()

    async def close(self):
        """Clean up resources."""
        # No persistent connections to close in this implementation
        pass 