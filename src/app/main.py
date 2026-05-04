"""
Main Application
FastAPI application setup and configuration
"""

import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.agents.base import setup_checkpointer_indexes
from src.app.services.graphiti import close_graphiti, setup_graphiti

from .core.config import settings
from .core.database import neo4j_db, redis_cache
from .core.logging import configure_logging, request_id_var
from .services.memory_service import memory_service
from .api.routes import (
    voice_router,
    food_router,
    travel_router,
    social_router,
    auth_router,
    onboarding_ws_router,
    agent_ws_router,
    users_router,
)

from scalar_fastapi import get_scalar_api_reference

# Configure structured (JSON-by-default) logging. Use `LOG_FORMAT=text`
# in dev for human-readable lines.
configure_logging(
    level=str(settings.LOG_LEVEL).upper(),
    fmt=os.getenv("LOG_FORMAT", "json"),
    log_dir="logs",
    log_file="app.log",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Starting Aurasense application...")
    try:
        await neo4j_db.connect()
        await redis_cache.connect()
        logger.info("Database connections established")
        # Initialize LangGraph checkpointer indexes (idempotent).
        await setup_checkpointer_indexes()
        # Initialize Graphiti (build indices/constraints, idempotent).
        # Graphiti now runs in-process via graphiti-core, not as a
        # standalone container — see services/graphiti/client.py.
        await setup_graphiti()
        logger.info("Graphiti SDK indices/constraints ready")
    except Exception as e:
        logger.error(f"Failed during startup: {str(e)}", exc_info=True)
        raise

    yield

    # Shutdown
    logger.info("Shutting down Aurasense application...")
    try:
        await neo4j_db.close()
        await redis_cache.close()
        await close_graphiti()
        await memory_service.cleanup()
        logger.info("All connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}", exc_info=True)


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Voice-first agentic lifestyle companion",
    lifespan=lifespan,
)


# Request logging middleware — sets the per-request correlation id on a
# ContextVar so structured log records pick it up automatically.
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_var.set(request_id)
    request.state.request_id = request_id

    start = datetime.utcnow()
    try:
        logger.info(
            "request.start",
            extra={"method": request.method, "path": request.url.path},
        )
        response = await call_next(request)
        duration = (datetime.utcnow() - start).total_seconds()
        logger.info(
            "request.end",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_s": round(duration, 4),
            },
        )
        # Echo the request id back so clients can correlate too.
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_var.reset(token)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS.split(",") if settings.CORS_ALLOW_METHODS != "*" else ["*"],
    allow_headers=settings.CORS_ALLOW_HEADERS.split(",") if settings.CORS_ALLOW_HEADERS != "*" else ["*"],
)

# Include API routes
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)
app.include_router(voice_router, prefix=settings.API_V1_STR)
app.include_router(food_router, prefix=settings.API_V1_STR)
app.include_router(travel_router, prefix=settings.API_V1_STR)
app.include_router(social_router, prefix=settings.API_V1_STR)
app.include_router(onboarding_ws_router, prefix=settings.API_V1_STR)
app.include_router(agent_ws_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Aurasense API",
        "version": settings.APP_VERSION,
        "status": "operational",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Actually check the services
        neo4j_status = "connected" if await neo4j_db.is_connected() else "disconnected"
        redis_status = "connected" if await redis_cache.is_connected() else "disconnected"

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "neo4j": neo4j_status,
                "redis": redis_status,
                "groq": "available"
            },
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@app.get("/scalar")
async def get_scalar_docs():
    """Get API documentation"""
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(
        f"Unhandled exception: {exc}\n"
        f"Path: {request.url.path}\n"
        f"Method: {request.method}\n"
        f"Headers: {dict(request.headers)}",
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower(),
    )
