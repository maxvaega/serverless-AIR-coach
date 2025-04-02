
import os
from dotenv import load_dotenv

load_dotenv(override=True)

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

AWS_ACCESS_KEY_ID=os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY=os.getenv("AWS_SECRET_ACCESS_KEY")
BUCKET_NAME=os.getenv("BUCKET_NAME")
CACHE_TTL = 300

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_SECRET = os.getenv("AUTH0_SECRET")

is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"

AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "AIRCoach_conversations_dev")