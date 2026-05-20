import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
from typing import List, Optional
from functools import lru_cache

# Load environment variables from .env file
load_dotenv(override=True)

class Settings(BaseSettings):
    # LLM Configuration (DeepSeek via OpenRouter)
    OPENROUTER_API_KEY: str = os.getenv('OPENROUTER_API_KEY', '')
    OPENROUTER_BASE_URL: str = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    FORCED_MODEL: str = os.getenv("FORCED_MODEL", "deepseek/deepseek-v4-flash")  # Modello LLM forzato se variabile non presente

    CACHE_DEBUG_LOGGING: bool = os.getenv("CACHE_DEBUG_LOGGING", "false").lower() == "true"
    
    # MongoDB Configuration
    URI: str = os.getenv("MONGODB_URI", '')
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", '')
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", '')
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", '')
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", '')
    BUCKET_NAME: str = os.getenv("BUCKET_NAME", '')
    CACHE_TTL: int = 300
    
    # Auth0 Configuration
    AUTH0_SECRET: Optional[str] = os.getenv("AUTH0_SECRET")
    auth0_domain: str = os.getenv("AUTH0_DOMAIN", "your-auth0-domain")
    auth0_api_audience: str = os.getenv("AUTH0_API_AUDIENCE", "your-auth0-api-audience")
    auth0_issuer: str = os.getenv("AUTH0_ISSUER", "https://your-auth0-domain/")
    auth0_algorithms: List[str] = os.getenv("AUTH0_ALGORITHMS", "RS256").split(",")
    
    # Application Configuration
    is_production: bool = os.getenv("ENVIRONMENT", "development").lower() == "production"
    HISTORY_LIMIT: int = int(os.getenv("HISTORY_LIMIT", "10"))

    # Monitoring Configuration
    ENABLE_TOKEN_LOGGING: bool = os.getenv("ENABLE_TOKEN_LOGGING", "true").lower() == "true"

    class Config:
        env_file = ".env"
        env_parse = True
        extra = "ignore"

@lru_cache()
def get_settings():
    return Settings()

# Create global settings object
settings = Settings()

# Backward compatibility - keep existing variable names for gradual migration
OPENROUTER_API_KEY = settings.OPENROUTER_API_KEY
OPENROUTER_BASE_URL = settings.OPENROUTER_BASE_URL
URI = settings.URI
DATABASE_NAME = settings.DATABASE_NAME
COLLECTION_NAME = settings.COLLECTION_NAME
AWS_ACCESS_KEY_ID = settings.AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = settings.AWS_SECRET_ACCESS_KEY
BUCKET_NAME = settings.BUCKET_NAME
CACHE_TTL = settings.CACHE_TTL
AUTH0_DOMAIN = settings.auth0_domain  # Backward compatibility - maps to auth0_domain
AUTH0_SECRET = settings.AUTH0_SECRET
is_production = settings.is_production
auth0_domain = settings.auth0_domain
auth0_api_audience = settings.auth0_api_audience
auth0_issuer = settings.auth0_issuer
auth0_algorithms = settings.auth0_algorithms
FORCED_MODEL = settings.FORCED_MODEL
HISTORY_LIMIT = settings.HISTORY_LIMIT

CACHE_DEBUG_LOGGING = settings.CACHE_DEBUG_LOGGING

# Monitoring Configuration
ENABLE_TOKEN_LOGGING = settings.ENABLE_TOKEN_LOGGING
