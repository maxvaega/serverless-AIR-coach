from .env import *
from .logging_config import logger
import boto3
from botocore.exceptions import ClientError
import time
from typing import Dict, Optional

class DynamoDBConversationHandler:
    def __init__(self, table_name: str = DYNAMODB_TABLE_NAME, region: str = AWS_REGION):
        """
        Inizializza il handler dynamoDB con il nome della tabella e la regione
        """
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)

    def insert_conversation(self, data: Dict) -> Dict:
        """
        Inserisce una conversazione in DynamoDB
        """
        try:
            # Verifica che data non sia None e sia un dizionario
            if not isinstance(data, dict):
                raise ValueError("Error while inserting conversation data to dyamoDB: Data must be a dictionary")

            # Inserimento in DynamoDB
            result = self.table.put_item(
                Item=data,
                ReturnValues='NONE'  # Non restituire l'elemento inserito
            )

            return {
                'success': True,
                'message': 'Conversation inserted successfully',
                'response': result
            }

        except ClientError as e:
            logger.error(f"ClientError: {e.response['Error']['Message']}")
            return {
                'success': False,
                'message': f"DynamoDB ClientError: {e.response['Error']['Message']}",
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Exception: {str(e)}")
            return {
                'success': False,
                'message': f'Error inserting conversation: {str(e)}',
                'error': str(e)
            }
        
    def prepare_data(salf, query: str, response: str, user_id: str) -> dict:
        """
        Prepara i dati nel formato corretto per DynamoDB
        """
        data = {
            'user_id': str(user_id),                   # String semplice
            'timestamp': int(time.time() * 1000),      # Timestamp in millisecondi (migliore per ordinamento in DynamoDB) - deve essere tipo number
            'human': str(query),                       # String semplice
            'system': str(response)                    # String semplice
        }

        return data
    
    def get_data(self, user_id: str, limit: Optional[int] = 10) -> list:
        """
        Recupera i dati da DynamoDB per un utente specifico, ordinati per timestamp
        in ordine ascendente (dal più vecchio al più recente).
        
        Args:
            user_id (str): ID dell'utente di cui recuperare le conversazioni
            limit (Optional[int]): Numero massimo di documenti da restituire
        
        Returns:
            list: Lista di conversazioni ordinate per timestamp ascendente
        """
        try:
            # Query parameters
            query_params = {
                'KeyConditionExpression': '#uid = :user_id',
                'ExpressionAttributeNames': {
                    '#uid': 'user_id'
                },
                'ExpressionAttributeValues': {
                    ':user_id': str(user_id)
                },
                'ScanIndexForward': False  # Per ordinare in ordine decrescente (più recenti prima)
            }

            # Aggiungi il limit se specificato
            query_params['Limit'] = limit

            # Esegui la query
            response = self.table.query(**query_params)
            
            # Estrai gli items
            items = response.get('Items', [])
            
            # Reverse per ottenere ordine ascendente
            items.reverse()
            
            return items

        except ClientError as e:
            logger.error(f"DynamoDB ClientError in get_data: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            logger.error(f"Error in get_data: {str(e)}")
            return []
