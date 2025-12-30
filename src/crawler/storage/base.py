"""
Base storage interface for the web crawler.

This module defines the abstract base class that all storage backends must implement.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pathlib import Path


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def connect(self) -> None:
        """Initialize the storage backend connection."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the storage backend connection."""
        pass

    @abstractmethod
    async def index_document(
        self,
        url: str,
        content: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        media: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Index a document in the storage backend.

        Args:
            url: The URL of the document.
            content: The content of the document.
            metadata: Additional metadata for the document.
            media: List of media files associated with the document.

        Returns:
            The ID of the indexed document.
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """Search for documents in the storage backend.

        Args:
            query: The search query.
            filters: Additional filters to apply to the search.
            page: The page number (1-based).
            page_size: The number of results per page.

        Returns:
            A dictionary containing the search results and metadata.
        """
        pass

    @abstractmethod
    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document by its ID.

        Args:
            doc_id: The ID of the document to retrieve.

        Returns:
            The document, or None if not found.
        """
        pass

    @abstractmethod
    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document by its ID.

        Args:
            doc_id: The ID of the document to delete.

        Returns:
            True if the document was deleted, False otherwise.
        """
        pass

    @abstractmethod
    async def bulk_index(
        self, documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Index multiple documents in a single request.

        Args:
            documents: A list of documents to index.

        Returns:
            A dictionary containing the result of the bulk operation.
        """
        pass

    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """Get the status of the storage backend.

        Returns:
            A dictionary containing status information.
        """
        pass
