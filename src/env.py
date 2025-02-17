
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Setup MongoDB environment
URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

AWS_ACCESS_KEY_ID=os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY=os.getenv("AWS_SECRET_ACCESS_KEY")
BUCKET_NAME=os.getenv("BUCKET_NAME")
CACHE_TTL = 300