"""
Memory Service
Graphiti integration for memory management
"""

from typing import Dict, Any, List, Optional
import logging
from graphiti import Client
from src.app.core.config import settings
from src.app.models.user import User

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Graphiti memory service for storing and retrieving user memories
    """

    def __init__(self):
        self.logger = logging.getLogger("memory_service")
        self.graphiti_client = None
        self.initialize_graphiti()

    def initialize_graphiti(self):
        """Initialize Graphiti connection"""
        try:
            # For now, disable Graphiti initialization until properly configured
            # self.graphiti_client = Client(host="localhost")  # Add proper host configuration
            self.graphiti_client = None
            self.logger.info("Graphiti memory service disabled (not configured)")
        except Exception as e:
            self.logger.error(f"Failed to initialize Graphiti: {e}")
            self.graphiti_client = None

    async def store_user_memory(self, user_id: str, memory_data: Dict[str, Any]) -> bool:
        """
        Store user memory in Graphiti
        """
        if not self.graphiti_client:
            self.logger.warning("Graphiti not initialized, skipping memory storage")
            return False

        try:
            # Store memory with user context
            await self.graphiti_client.add_memory(
                data=memory_data.get("content", ""),
                context={"user_id": user_id, **memory_data.get("metadata", {})}
            )
            self.logger.info(f"Memory stored for user {user_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to store memory for user {user_id}: {e}")
            return False

    async def retrieve_user_memories(self, user_id: str, query: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve user memories from Graphiti
        """
        if not self.graphiti_client:
            self.logger.warning("Graphiti not initialized, returning empty memories")
            return []

        try:
            # Search memories for the user
            if query:
                memories = await self.graphiti_client.search(
                    query=query,
                    context={"user_id": user_id},
                    limit=limit
                )
            else:
                # For now, return empty list if no query provided
                # In a real implementation, you might want to retrieve recent memories
                memories = []
            
            self.logger.info(f"Retrieved {len(memories)} memories for user {user_id}")
            return memories
        except Exception as e:
            self.logger.error(f"Failed to retrieve memories for user {user_id}: {e}")
            return []

    async def store_user_registration(self, user: User) -> bool:
        """
        Store user registration information in Graphiti memory
        """
        memory_data = {
            "content": f"User {user.first_name} {user.last_name} registered with email {user.email}",
            "metadata": {
                "event_type": "user_registration",
                "user_id": user.uid,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "registration_date": user.created_at.isoformat() if user.created_at else None
            }
        }
        
        return await self.store_user_memory(user.uid, memory_data)

    async def store_user_login(self, user: User) -> bool:
        """
        Store user login information in Graphiti memory
        """
        memory_data = {
            "content": f"User {user.first_name} {user.last_name} logged in",
            "metadata": {
                "event_type": "user_login",
                "user_id": user.uid,
                "email": user.email,
                "login_timestamp": user.last_active.isoformat() if user.last_active else None
            }
        }
        
        return await self.store_user_memory(user.uid, memory_data)

    async def store_user_logout(self, user_id: str) -> bool:
        """
        Store user logout information in Graphiti memory
        """
        memory_data = {
            "content": f"User {user_id} logged out",
            "metadata": {
                "event_type": "user_logout",
                "user_id": user_id,
                "logout_timestamp": None  # Will be set by Graphiti
            }
        }
        
        return await self.store_user_memory(user_id, memory_data)

    async def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """
        Get user context from memories for agents
        """
        memories = await self.retrieve_user_memories(user_id, limit=20)
        
        context = {
            "user_id": user_id,
            "recent_activities": [],
            "preferences": {},
            "historical_data": memories
        }
        
        # Process memories to extract context
        for memory in memories:
            metadata = memory.get("metadata", {})
            event_type = metadata.get("event_type")
            
            if event_type in ["user_login", "user_logout", "user_registration"]:
                context["recent_activities"].append({
                    "type": event_type,
                    "timestamp": metadata.get("timestamp"),
                    "content": memory.get("content")
                })
        
        return context


# Global memory service instance
memory_service = MemoryService()