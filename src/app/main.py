"""
Main Application
FastAPI application setup and configuration
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from logging.handlers import RotatingFileHandler
import os
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from .core.config import settings
from .core.database import neo4j_db, redis_cache
from .services.memory_service import memory_service
from .api.routes import (
    voice_router,
    onboarding_router,
    food_router,
    travel_router,
    social_router,
    auth_router,
    onboarding_ws_router,
)

from scalar_fastapi import get_scalar_api_reference

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # Console handler
        logging.StreamHandler(),
        # File handler with rotation
        RotatingFileHandler(
            'logs/app.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
    ]
)

# Get logger for this module
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
    except Exception as e:
        logger.error(f"Failed to establish database connections: {str(e)}", exc_info=True)
        raise

    yield

    # Shutdown
    logger.info("Shutting down Aurasense application...")
    try:
        await neo4j_db.close()
        await redis_cache.close()
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


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Generate request ID
    request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))

    # Log request
    logger.info(f"Request {request_id}: {request.method} {request.url}")
    logger.debug(f"Request {request_id} headers: {dict(request.headers)}")

    # Get response
    start_time = datetime.now()
    response = await call_next(request)
    duration = (datetime.now() - start_time).total_seconds()

    # Log response
    logger.info(
        f"Response {request_id}: Status {response.status_code}, "
        f"Duration: {duration:.3f}s"
    )

    return response


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(voice_router, prefix=settings.API_V1_STR)
app.include_router(onboarding_router, prefix=settings.API_V1_STR)
app.include_router(food_router, prefix=settings.API_V1_STR)
app.include_router(travel_router, prefix=settings.API_V1_STR)
app.include_router(social_router, prefix=settings.API_V1_STR)
app.include_router(onboarding_ws_router, prefix=settings.API_V1_STR)


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
