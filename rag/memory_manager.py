"""
rag/memory_manager.py

Short-term conversation memory for continuity and context.
"""

from typing import List, Dict, Optional
from collections import deque
import asyncio
import logging

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Manages short-term conversation history.
    Thread-safe, maintains last N exchanges.
    """
    
    def __init__(self, max_turns: int = 5):
        """
        Args:
            max_turns: Maximum conversation turns to remember (each turn = 2 messages)
        """
        self.max_messages = max_turns * 2
        self.messages: deque[Dict[str, str]] = deque(maxlen=self.max_messages)
        self._lock = asyncio.Lock()
    
    async def add_message(self, role: str, content: str) -> None:
        """
        Add message to history.
        
        Args:
            role: 'user' or 'assistant'
            content: Message content
        """
        async with self._lock:
            self.messages.append({
                "role": role,
                "content": content
            })
            logger.debug(f"Added {role} message, history size: {len(self.messages)}")
    
    async def get_history(self) -> List[Dict[str, str]]:
        """Get full conversation history."""
        async with self._lock:
            return list(self.messages)
    
    async def get_recent(self, n: int = 6) -> List[Dict[str, str]]:
        """
        Get last N messages.
        
        Args:
            n: Number of recent messages (default 6 = last 3 turns)
        """
        async with self._lock:
            recent = list(self.messages)[-n:] if len(self.messages) > n else list(self.messages)
            return recent
    
    async def clear(self) -> None:
        """Clear conversation history."""
        async with self._lock:
            self.messages.clear()
            logger.info("Conversation history cleared")
    
    async def get_context_summary(self) -> str:
        """Get brief text summary of conversation for logging."""
        async with self._lock:
            if not self.messages:
                return "[Empty conversation]"
            
            lines = []
            for msg in list(self.messages)[-4:]:  # Last 2 turns
                role = "User" if msg["role"] == "user" else "Assistant"
                content = msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"]
                lines.append(f"{role}: {content}")
            
            return " | ".join(lines)
    
    # Sync wrappers for backward compatibility
    def add_message_sync(self, role: str, content: str) -> None:
        """Synchronous add_message."""
        asyncio.run(self.add_message(role, content))
    
    def get_history_sync(self) -> List[Dict[str, str]]:
        """Synchronous get_history."""
        return asyncio.run(self.get_history())
    
    def get_recent_sync(self, n: int = 6) -> List[Dict[str, str]]:
        """Synchronous get_recent."""
        return asyncio.run(self.get_recent(n))
    
    def clear_sync(self) -> None:
        """Synchronous clear."""
        asyncio.run(self.clear())


class MemoryManager:
    """
    Manages multiple conversation sessions.
    Each session has its own memory.
    """
    
    def __init__(self):
        self.sessions: Dict[str, ConversationMemory] = {}
        self._lock = asyncio.Lock()
    
    async def get_session(self, session_id: str = "default") -> ConversationMemory:
        """
        Get or create conversation memory for session.
        
        Args:
            session_id: Unique session identifier
        """
        async with self._lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = ConversationMemory(max_turns=5)
                logger.info(f"Created new session: {session_id}")
            return self.sessions[session_id]
    
    async def clear_session(self, session_id: str) -> None:
        """Clear specific session."""
        async with self._lock:
            if session_id in self.sessions:
                await self.sessions[session_id].clear()
                del self.sessions[session_id]
                logger.info(f"Cleared session: {session_id}")
    
    async def clear_all(self) -> None:
        """Clear all sessions."""
        async with self._lock:
            self.sessions.clear()
            logger.info("Cleared all sessions")
