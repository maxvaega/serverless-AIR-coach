import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
from typing import List, Optional
from functools import lru_cache

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    GOOGLE_API_KEY : str = os.getenv('GOOGLE_API_KEY')

    # Setup MongoDB environment
    URI : str = os.getenv("MONGODB_URI")
    DATABASE_NAME : str = os.getenv("DATABASE_NAME")
    COLLECTION_NAME : str = os.getenv("COLLECTION_NAME")

    AWS_ACCESS_KEY_ID : str =os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY : str =os.getenv("AWS_SECRET_ACCESS_KEY")
    BUCKET_NAME : str =os.getenv("BUCKET_NAME")
    CACHE_TTL : int = 300

    AUTH0_DOMAIN : str = os.getenv("AUTH0_DOMAIN")
    AUTH0_SECRET : Optional[str] = os.getenv("AUTH0_SECRET")

    is_production : bool = os.getenv("ENVIRONMENT", "development").lower() == "production"
    # print(f"Running in {'production' if is_production else 'development'} mode")

    auth0_domain : str = os.getenv("AUTH0_DOMAIN", "your-auth0-domain")
    auth0_api_audience : str = os.getenv("AUTH0_API_AUDIENCE", "your-auth0-api-audience")
    auth0_issuer : str = os.getenv("AUTH0_ISSUER", "https://your-auth0-domain/")
    auth0_algorithms : List[str] = os.getenv("AUTH0_ALGORITHMS", "RS256").split(",")

    FORCED_MODEL : str = os.getenv("FORCED_MODEL") if os.getenv("FORCED_MODEL") else "models/gemini-2.5-flash"

    class Config:
        env_file = ".env"
        env_parse = True
        extra = "ignore"

@lru_cache()
def get_settings():
    return Settings()

# Create global settings object
settings = Settings()