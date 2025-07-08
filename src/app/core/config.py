from decouple import config, Csv


class Settings:
    APP_NAME = config("APP_NAME", default="Aurasense")
    APP_VERSION = config("APP_VERSION", default="0.1.0")
    DEBUG = config("DEBUG", default=False, cast=bool)
    API_V1_STR = config("API_V1_STR", default="/api/v1")
    HOST = config("HOST", default="0.0.0.0")
    PORT = config("PORT", default=8000, cast=int)
    LOG_LEVEL = config("LOG_LEVEL", default="INFO")

    ENVIRONMENT = config("ENVIRONMENT", default="development")

    NEO4J_HOST = config("NEO4J_HOST", default="localhost")
    NEO4J_PORT = config("NEO4J_PORT", default=7687, cast=int)
    NEO4J_URI = config("NEO4J_URI", default=f"bolt://{NEO4J_HOST}:{NEO4J_PORT}")
    NEO4J_USER = config("NEO4J_USER", default="neo4j")
    NEO4J_PASSWORD = config("NEO4J_PASSWORD", default="test1234")
    DATABASE_URL = f"bolt://{NEO4J_USER}:{NEO4J_PASSWORD}@{NEO4J_HOST}:{NEO4J_PORT}"

    REDIS_URL = config("REDIS_URL", default="redis://localhost:6379")

    GROQ_API_KEY = config("GROQ_API_KEY", default="")
    GOOGLE_PLACES_API_KEY = config("GOOGLE_PLACES_API_KEY", default="")
    FOURSQUARE_API_KEY = config("FOURSQUARE_API_KEY", default="")
    ANTHROPIC_API_KEY = config("ANTHROPIC_API_KEY", default="")
    CLOUD_STORAGE_PROVIDER = config("CLOUD_STORAGE_PROVIDER", default="aws")
    AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
    AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
    AWS_REGION = config("AWS_REGION", default="us-east-1")
    AUDIO_BUCKET_NAME = config("AUDIO_BUCKET_NAME", default="aurasense-audio-files")

    MAX_AUDIO_FILE_SIZE_MB = config("MAX_AUDIO_FILE_SIZE_MB", default=10, cast=int)
    AUDIO_PROCESSING_TIMEOUT = config("AUDIO_PROCESSING_TIMEOUT", default=30, cast=int)

    SECRET_KEY = config("SECRET_KEY", default="your-secret-key-change-this")
    ALGORITHM = config("ALGORITHM", default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = config(
        "ACCESS_TOKEN_EXPIRE_MINUTES", default=30, cast=int
    )

    GRAPHITI_HOST = config("GRAPHITI_HOST", default="localhost")
    GRAPHITI_PORT = config("GRAPHITI_PORT", default=8080, cast=int)
    GRAPHITI_URL = config("GRAPHITI_URL", default="http://localhost:8080")


settings = Settings()
