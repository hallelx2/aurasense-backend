"""
Graphiti Client Implementation
"""

import aiohttp
import json
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class Client:
    """
    Graphiti Memory Service Client

    Handles communication with the Graphiti memory service for storing and retrieving memories.
    """

    def __init__(self, host: str = "localhost:8080"):
        """
        Initialize the Graphiti client

        Args:
            host: The host address of the Graphiti service (default: "localhost:8080")
        """
        self.base_url = f"http://{host}"
        self.logger = logging.getLogger("graphiti.client")
        self.session = None

    async def _ensure_session(self):
        """Ensure an aiohttp session exists"""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close the client session"""
        if self.session:
            await self.session.close()
            self.session = None

    async def add_memory(self, data: str, context: Dict[str, Any]) -> bool:
        """
        Add a new memory

        Args:
            data: The memory content
            context: Additional context for the memory

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            await self._ensure_session()

            payload = {
                "content": data,
                "metadata": context
            }

            async with self.session.post(
                f"{self.base_url}/memories",
                json=payload
            ) as response:
                if response.status == 201:
                    self.logger.info("Memory added successfully")
                    return True
                else:
                    self.logger.error(f"Failed to add memory: {response.status}")
                    return False

        except Exception as e:
            self.logger.error(f"Error adding memory: {e}")
            return False

    async def search(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search memories

        Args:
            query: Search query string
            context: Optional context to filter memories
            limit: Maximum number of results to return

        Returns:
            List of matching memories
        """
        try:
            await self._ensure_session()

            params = {
                "q": query,
                "limit": limit
            }

            if context:
                params["context"] = json.dumps(context)

            async with self.session.get(
                f"{self.base_url}/memories/search",
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.logger.info(f"Retrieved {len(data)} memories")
                    return data
                else:
                    self.logger.error(f"Failed to search memories: {response.status}")
                    return []

        except Exception as e:
            self.logger.error(f"Error searching memories: {e}")
            return []

    async def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific memory by ID

        Args:
            memory_id: The ID of the memory to retrieve

        Returns:
            The memory data if found, None otherwise
        """
        try:
            await self._ensure_session()

            async with self.session.get(
                f"{self.base_url}/memories/{memory_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.logger.info(f"Retrieved memory {memory_id}")
                    return data
                elif response.status == 404:
                    self.logger.warning(f"Memory {memory_id} not found")
                    return None
                else:
                    self.logger.error(f"Failed to get memory: {response.status}")
                    return None

        except Exception as e:
            self.logger.error(f"Error getting memory: {e}")
            return None
