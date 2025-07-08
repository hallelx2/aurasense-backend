"""
Database Configuration
Neo4j and Redis database setup and connections
"""

from neo4j import GraphDatabase
import redis.asyncio as redis
from typing import Optional
import logging
from .config import settings

logger = logging.getLogger(__name__)


class Neo4jDatabase:
    """
    Neo4j database connection and operations
    """

    def __init__(self):
        self.driver = None
        self.logger = logging.getLogger("database.neo4j")

    async def connect(self):
        """Connect to Neo4j database"""
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            # Verify connection
            await self.is_connected()
            self.logger.info("Connected to Neo4j database")
        except Exception as e:
            self.logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def close(self):
        """Close database connection"""
        if self.driver:
            self.driver.close()
            self.logger.info("Neo4j connection closed")

    async def is_connected(self) -> bool:
        """Check if connected to Neo4j"""
        try:
            if not self.driver:
                return False
            # Try to verify the connection by running a simple query
            with self.driver.session() as session:
                result = session.run("RETURN 1")
                result.single()
            return True
        except Exception as e:
            self.logger.error(f"Neo4j connection check failed: {e}")
            return False

    async def execute_query(self, query: str, parameters: dict = None):
        """Execute a Cypher query"""
        # Implementation will be added
        pass


class RedisCache:
    """
    Redis cache connection and operations
    """

    def __init__(self):
        self.redis_client = None
        self.logger = logging.getLogger("database.redis")

    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL)
            if not await self.is_connected():
                raise Exception("Failed to connect to Redis")
            self.logger.info("Connected to Redis")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            self.logger.info("Redis connection closed")

    async def is_connected(self) -> bool:
        """Check if connected to Redis"""
        try:
            if not self.redis_client:
                return False
            return await self.redis_client.ping()
        except Exception as e:
            self.logger.error(f"Redis connection check failed: {e}")
            return False

    async def set(self, key: str, value: str, ttl: int = None):
        """Set key-value pair in Redis"""
        if not await self.is_connected():
            raise Exception("Redis is not connected")
        await self.redis_client.set(key, value, ex=ttl)

    async def get(self, key: str):
        """Get value from Redis"""
        if not await self.is_connected():
            raise Exception("Redis is not connected")
        return await self.redis_client.get(key)


# Global database instances
neo4j_db = Neo4jDatabase()
redis_cache = RedisCache()
