from typing import Dict, Any, List, Optional
import logging
from graphiti import Client
from src.app.core.config import settings
from src.app.models.user import User

logger = logging.getLogger(__name__)


class MemoryService:
    def __init__(self):
        self.logger = logging.getLogger("memory_service")
        self.graphiti_client = None
        self.initialize_graphiti()

    def initialize_graphiti(self):
        try:
            graphiti_host = getattr(settings, 'GRAPHITI_HOST', 'localhost')
            graphiti_port = getattr(settings, 'GRAPHITI_PORT', 8080)
            
            self.graphiti_client = Client(host=f"{graphiti_host}:{graphiti_port}")
            self.logger.info(f"Graphiti memory service initialized at {graphiti_host}:{graphiti_port}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Graphiti: {e}")
            self.graphiti_client = None

    async def store_user_memory(self, user_id: str, memory_data: Dict[str, Any]) -> bool:
        if not self.graphiti_client:
            self.logger.warning("Graphiti not initialized, skipping memory storage")
            return False

        try:
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
        if not self.graphiti_client:
            self.logger.warning("Graphiti not initialized, returning empty memories")
            return []

        try:
            if query:
                memories = await self.graphiti_client.search(
                    query=query,
                    context={"user_id": user_id},
                    limit=limit
                )
            else:
                memories = []
            
            self.logger.info(f"Retrieved {len(memories)} memories for user {user_id}")
            return memories
        except Exception as e:
            self.logger.error(f"Failed to retrieve memories for user {user_id}: {e}")
            return []

    async def store_user_registration(self, user: User) -> bool:
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
        memory_data = {
            "content": f"User {user_id} logged out",
            "metadata": {
                "event_type": "user_logout",
                "user_id": user_id,
                "logout_timestamp": None
            }
        }
        
        return await self.store_user_memory(user_id, memory_data)

    async def get_user_context(self, user_id: str) -> Dict[str, Any]:
        memories = await self.retrieve_user_memories(user_id, limit=20)
        
        context = {
            "user_id": user_id,
            "recent_activities": [],
            "preferences": {},
            "historical_data": memories
        }
        
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


memory_service = MemoryService()