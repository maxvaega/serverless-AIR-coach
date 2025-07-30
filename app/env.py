
import os
from dotenv import load_dotenv
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings

load_dotenv(override=True)

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Setup MongoDB environment
URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

AWS_ACCESS_KEY_ID=os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY=os.getenv("AWS_SECRET_ACCESS_KEY")
BUCKET_NAME=os.getenv("BUCKET_NAME")
CACHE_TTL = 300

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_SECRET = os.getenv("AUTH0_SECRET")

is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
# print(f"Running in {'production' if is_production else 'development'} mode")

auth0_domain = os.getenv("AUTH0_DOMAIN", "your-auth0-domain")
auth0_api_audience = os.getenv("AUTH0_API_AUDIENCE", "your-auth0-api-audience")
auth0_issuer = os.getenv("AUTH0_ISSUER", "https://your-auth0-domain/")
auth0_algorithms = os.getenv("AUTH0_ALGORITHMS", "RS256").split(",")

FORCED_MODEL = os.getenv("FORCED_MODEL") if os.getenv("FORCED_MODEL") else "models/gemini-2.5-flash"

from pydantic import field_validator

class Settings(BaseSettings):
    auth0_domain: str
    auth0_api_audience: str
    auth0_issuer: str
    auth0_algorithms: List[str] = ["RS256"]

    class Config:
        env_file = ".env"
        env_parse = True
        extra = "ignore"

@lru_cache()
def get_settings():
    return Settings()
