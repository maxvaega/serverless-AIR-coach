from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from .env import URI
from .logging_config import logger

if not URI:
    raise ValueError("No MongoDB URI found. Please set the MONGODB_URI environment variable.")

try:
    # Create a new client and connect to the server
    client = MongoClient(URI, server_api=ServerApi('1'))
    # logger.info("Connected to MongoDB successfully.") # Antonio sistemalo
except Exception as e:
    print(f"An error occurred while connecting to MongoDB: {e}")
    
def get_collection(database_name, collection_name):
        """
        Get a collection from the MongoDB database.
        
        :param database_name: Name of the database
        :param collection_name: Name of the collection
        :return: Collection object
        """
        db = client[database_name]
        collection = db[collection_name]
        return collection

def insert_data(database_name, collection_name, data):
    """
    Insert data into a MongoDB collection.
    
    :param database_name: Name of the database
    :param collection_name: Name of the collection
    :param data: Data to be inserted (dictionary or list of dictionaries)
    :return: Inserted IDs
    """
    collection = get_collection(database_name, collection_name)
    if isinstance(data, list):
        result = collection.insert_many(data)
    else:
        result = collection.insert_one(data)
    return result.inserted_ids if isinstance(data, list) else result.inserted_id

def create_collection(database_name, collection_name):
    """
    Create a new collection in the MongoDB database.
    
    :param database_name: Name of the database
    :param collection_name: Name of the collection
    :return: Collection object
    """
    db = client[database_name]
    collection = db.create_collection(collection_name)
    return collection

def drop_collection(database_name, collection_name):
    """
    Drop a collection from the MongoDB database.
    
    :param database_name: Name of the database
    :param collection_name: Name of the collection
    :return: True if successful, False otherwise
    """
    db = client[database_name]
    try:
        db.drop_collection(collection_name)
        return True
    except Exception as e:
        print(f"An error occurred while dropping the collection: {e}")
        return False
    
def get_data(database_name, collection_name, filters=None, keys=None, limit=None):
    """
    Get data from a MongoDB collection based on multiple key-value pairs and specify which keys to include in the result.
    
    :param database_name: Name of the database
    :param collection_name: Name of the collection
    :param filters: Dictionary of key-value pairs to filter the data (optional)
    :param keys: Dictionary specifying which keys to include or exclude in the result (optional)
    :param limit: Number of documents to return (optional)
    :return: List of documents ordered by timestamp ascending (oldest first)
    """
    collection = get_collection(database_name, collection_name)
    query = filters if filters else {}
    projection = keys if keys else None
    
    # Get documents with limit and sort in a single query
    # Using hint() to ensure the use of timestamp index if available
    cursor = collection.find(
        query, 
        projection
    ).sort(
        "timestamp", -1  # First sort descending
    ).limit(
        limit if limit else 0  # Apply limit in the query
    ).hint("timestamp_-1") if limit else collection.find(
        query, 
        projection
    ).sort("timestamp", -1)
    
    # Convert to list and reverse to get ascending order (oldest first)
    documents = list(cursor)
    documents.reverse()
    
    return documents

# Funzione attualmente non utilizzata, serve per garantire che l'indice venga creato sul db (ma non serve ripeterlo ogni volta)
def ensure_indexes(database_name, collection_name): 
    """
    La funzione ensure_indexes serve a garantire che un indice specifico 
    (in questo caso sull'attributo timestamp in ordine decrescente) esista su una collezione MongoDB. 
    L'operazione è definitiva e non deve essere ripetuta ogni volta, 
    ma può essere utile richiamarla durante l'inizializzazione dell'applicazione per assicurarsi che 
    gli indici siano correttamente configurati.
    """
    collection = get_collection(database_name, collection_name)
    try:
        index_name = collection.create_index([("timestamp", -1)], background=True)
        logger.info(f"MongoDB: Index '{index_name}' created successfully on collection {collection_name}")
    except Exception as e:
        logger.error(f"MongoDB: Error creating index on collection {collection_name}: {e}")


