"""
Unit tests for MongoDBService.update_feedback method.

Tests the database layer in isolation with mocked MongoDB.
"""

import pytest
from unittest.mock import MagicMock, patch
from pymongo import ReturnDocument


@pytest.mark.unit
class TestUpdateFeedback:

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create a MongoDBService with mocked MongoDB client."""
        with patch("src.services.database.database_service.pymongo.MongoClient"):
            from src.services.database.database_service import MongoDBService
            self.service = MongoDBService(database_name="test_db")
            self.mock_collection = MagicMock()
            self.service.db = {"test_collection": self.mock_collection}

    def test_set_positive_feedback(self):
        """update_feedback sets feedback_user to 'positive' via $set."""
        self.mock_collection.find_one_and_update.return_value = {
            "_id": "msg_123",
            "content": "Hello",
            "feedback_user": "positive",
        }

        result = self.service.update_feedback("test_collection", "msg_123", "positive")

        self.mock_collection.find_one_and_update.assert_called_once_with(
            {"_id": "msg_123"},
            {"$set": {"feedback_user": "positive"}},
            return_document=ReturnDocument.AFTER,
        )
        assert result["feedback_user"] == "positive"
        assert result["_id"] == "msg_123"

    def test_set_negative_feedback(self):
        """update_feedback sets feedback_user to 'negative' via $set."""
        self.mock_collection.find_one_and_update.return_value = {
            "_id": "msg_456",
            "content": "Ciao",
            "feedback_user": "negative",
        }

        result = self.service.update_feedback("test_collection", "msg_456", "negative")

        self.mock_collection.find_one_and_update.assert_called_once_with(
            {"_id": "msg_456"},
            {"$set": {"feedback_user": "negative"}},
            return_document=ReturnDocument.AFTER,
        )
        assert result["feedback_user"] == "negative"

    def test_document_not_found_returns_none(self):
        """update_feedback returns None when document does not exist."""
        self.mock_collection.find_one_and_update.return_value = None

        result = self.service.update_feedback("test_collection", "nonexistent_id", "positive")

        assert result is None

    def test_overwrite_existing_feedback(self):
        """update_feedback overwrites a previously set feedback value."""
        self.mock_collection.find_one_and_update.return_value = {
            "_id": "msg_789",
            "feedback_user": "negative",
        }

        result = self.service.update_feedback("test_collection", "msg_789", "negative")

        assert result["feedback_user"] == "negative"
        self.mock_collection.find_one_and_update.assert_called_once_with(
            {"_id": "msg_789"},
            {"$set": {"feedback_user": "negative"}},
            return_document=ReturnDocument.AFTER,
        )
