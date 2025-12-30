"""
Elasticsearch storage backend for the web crawler.

This module provides an implementation of the StorageBackend interface using Elasticsearch.
"""
import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
from pathlib import Path

from elasticsearch import AsyncElasticsearch, NotFoundError
from elasticsearch.helpers import async_bulk

from .base import StorageBackend

logger = logging.getLogger(__name__)

# Default Elasticsearch index settings
DEFAULT_INDEX_SETTINGS = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1,
        "analysis": {
            "analyzer": {
                "default": {
                    "type": "standard",
                    "stopwords": "_english_"
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "url": {"type": "keyword"},
            "title": {
                "type": "text",
                "fields": {
                    "keyword": {"type": "keyword", "ignore_above": 256}
                }
            },
            "content": {
                "type": "nested",
                "properties": {
                    "text": {"type": "text"},
                    "html": {"type": "keyword", "index": False},
                    "summary": {"type": "text"},
                    "language": {"type": "keyword"}
                }
            },
            "metadata": {
                "type": "object",
                "dynamic": True
            },
            "media": {
                "type": "nested",
                "properties": {
                    "type": {"type": "keyword"},
                    "url": {"type": "keyword"},
                    "alt_text": {"type": "text"},
                    "caption": {"type": "text"},
                    "local_path": {"type": "keyword", "index": False},
                    "file_size": {"type": "long"},
                    "dimensions": {
                        "type": "object",
                        "properties": {
                            "width": {"type": "integer"},
                            "height": {"type": "integer"}
                        }
                    }
                }
            },
            "links": {
                "type": "nested",
                "properties": {
                    "url": {"type": "keyword"},
                    "text": {"type": "text"},
                    "is_internal": {"type": "boolean"}
                }
            },
            "crawl_info": {
                "type": "object",
                "properties": {
                    "crawled_at": {"type": "date"},
                    "status": {"type": "keyword"},
                    "http_status": {"type": "integer"},
                    "error": {"type": "text"},
                    "crawl_depth": {"type": "integer"}
                }
            },
            "fingerprint": {"type": "keyword"}
        }
    }
}


class ElasticsearchStorage(StorageBackend):
    """Elasticsearch storage backend implementation."""

    def __init__(
        self,
        hosts: Union[str, List[str]] = "http://localhost:9200",
        index_prefix: str = "crawler_",
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_ssl: bool = False,
        verify_certs: bool = True,
        ca_certs: Optional[Union[str, Path]] = None,
        timeout: int = 30,
        max_retries: int = 3,
        bulk_size: int = 1000,
        **kwargs
    ):
        """Initialize the Elasticsearch storage backend.

        Args:
            hosts: List of Elasticsearch hosts or a single host as a string.
            index_prefix: Prefix to use for index names.
            username: Username for HTTP basic auth.
            password: Password for HTTP basic auth.
            use_ssl: Whether to use SSL/TLS for the connection.
            verify_certs: Whether to verify SSL certificates.
            ca_certs: Path to CA certificate bundle.
            timeout: Timeout in seconds for Elasticsearch operations.
            max_retries: Maximum number of retries for failed requests.
            bulk_size: Number of documents to index in a single bulk request.
            **kwargs: Additional arguments to pass to AsyncElasticsearch.
        """
        self.hosts = [hosts] if isinstance(hosts, str) else hosts
        self.index_prefix = index_prefix
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.verify_certs = verify_certs
        self.ca_certs = Path(ca_certs) if ca_certs else None
        self.timeout = timeout
        self.max_retries = max_retries
        self.bulk_size = bulk_size
        
        # Store additional kwargs for AsyncElasticsearch
        self._es_kwargs = kwargs
        
        # Initialize client
        self.client = None
        self._index_settings = DEFAULT_INDEX_SETTINGS

    def _get_index_name(self, url: str) -> str:
        """Generate an index name from a URL.

        Args:
            url: The URL to generate an index name for.

        Returns:
            A sanitized index name with the configured prefix.
        """
        # Extract domain from URL
        domain = urlparse(url).netloc
        if not domain:
            domain = "default"
        
        # Replace dots and special characters with underscores
        sanitized = "".join(c if c.isalnum() else "_" for c in domain.lower())
        return f"{self.index_prefix}{sanitized}"

    def _generate_document_id(self, url: str) -> str:
        """Generate a deterministic document ID from a URL.

        Args:
            url: The URL to generate an ID for.

        Returns:
            A SHA-256 hash of the URL.
        """
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    async def connect(self) -> None:
        """Initialize the Elasticsearch client connection."""
        if self.client is None:
            # Prepare connection parameters
            params = {
                "hosts": self.hosts,
                "request_timeout": self.timeout,
                "max_retries": self.max_retries,
                "retry_on_timeout": True,
                **self._es_kwargs  # Allow overriding any parameters
            }
            
            # Add SSL/TLS configuration if needed
            if self.use_ssl:
                # Update hosts to use https if not already specified
                updated_hosts = []
                for host in (self.hosts if isinstance(self.hosts, list) else [self.hosts]):
                    if not (host.startswith('http://') or host.startswith('https://')):
                        host = f"https://{host}"
                    updated_hosts.append(host)
                params["hosts"] = updated_hosts
                
                params.update({
                    "verify_certs": self.verify_certs,
                })
                
                # Add CA certificate if provided
                if self.ca_certs and self.ca_certs.exists():
                    params["ca_certs"] = str(self.ca_certs)
            
            # Add authentication if provided
            if self.username and self.password:
                params["basic_auth"] = (self.username, self.password)
            
            self.client = AsyncElasticsearch(**params)
            
            try:
                # Test the connection
                if not await self.client.ping():
                    raise ConnectionError("Failed to connect to Elasticsearch")
                logger.info("Connected to Elasticsearch")
            except Exception as e:
                logger.error(f"Failed to connect to Elasticsearch: {e}")
                await self.disconnect()
                raise

    async def disconnect(self) -> None:
        """Close the Elasticsearch client connection."""
        if self.client:
            await self.client.close()
            self.client = None
            logger.info("Disconnected from Elasticsearch")

    async def _ensure_index_exists(self, index_name: str) -> None:
        """Ensure that an index exists with the correct mappings.

        Args:
            index_name: The name of the index to ensure exists.
        """
        if not await self.client.indices.exists(index=index_name):
            logger.info(f"Creating index: {index_name}")
            await self.client.indices.create(
                index=index_name,
                body=self._index_settings,
                ignore=400  # Ignore 400 (index already exists) errors
            )

    async def index_document(
        self,
        url: str,
        content: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        media: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Index a document in Elasticsearch.

        Args:
            url: The URL of the document.
            content: The content of the document.
            metadata: Additional metadata for the document.
            media: List of media files associated with the document.

        Returns:
            The ID of the indexed document.
        """
        if not self.client:
            await self.connect()

        index_name = self._get_index_name(url)
        doc_id = self._generate_document_id(url)
        
        # Prepare the document
        document = {
            "url": url,
            "title": content.get("title", ""),
            "content": {
                "text": content.get("text", ""),
                "html": content.get("html", ""),
                "summary": content.get("summary", ""),
                "language": content.get("language", "en")
            },
            "metadata": metadata or {},
            "media": media or [],
            "crawl_info": {
                "crawled_at": datetime.utcnow().isoformat(),
                "status": "success",
                "http_status": 200,
                "crawl_depth": metadata.get("crawl_depth", 0) if metadata else 0
            },
            "fingerprint": self._generate_content_fingerprint(content.get("text", ""))
        }

        # Add links if present
        if "links" in content:
            document["links"] = content["links"]

        # Ensure the index exists
        await self._ensure_index_exists(index_name)

        # Index the document
        try:
            response = await self.client.index(
                index=index_name,
                id=doc_id,
                document=document,
                refresh=True
            )
            logger.debug(f"Indexed document {doc_id} in index {index_name}")
            return response["_id"]
        except Exception as e:
            logger.error(f"Failed to index document {url}: {e}")
            raise

    def _generate_content_fingerprint(self, content: str) -> str:
        """Generate a fingerprint for content to detect duplicates.

        Args:
            content: The content to generate a fingerprint for.

        Returns:
            A SHA-256 hash of the normalized content.
        """
        # Normalize the content (lowercase, remove extra whitespace, etc.)
        normalized = " ".join(content.lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """Search for documents in Elasticsearch.

        Args:
            query: The search query.
            filters: Additional filters to apply to the search.
            page: The page number (1-based).
            page_size: The number of results per page.

        Returns:
            A dictionary containing the search results and metadata.
        """
        if not self.client:
            await self.connect()

        # Build the query
        must_clauses = [{"match": {"_all": query}}] if query else []
        
        # Add filters if provided
        if filters:
            for field, value in filters.items():
                must_clauses.append({"term": {field: value}})

        query_body = {
            "query": {
                "bool": {
                    "must": must_clauses or [{"match_all": {}}]
                }
            },
            "from": (page - 1) * page_size,
            "size": page_size,
            "sort": [{"crawl_info.crawled_at": {"order": "desc"}}]
        }

        try:
            # Search across all indices with the configured prefix
            response = await self.client.search(
                index=f"{self.index_prefix}*",
                body=query_body
            )

            # Process the response
            total = response["hits"]["total"]["value"]
            hits = [
                {
                    "id": hit["_id"],
                    "index": hit["_index"],
                    "score": hit["_score"],
                    **hit["_source"]
                }
                for hit in response["hits"]["hits"]
            ]

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "results": hits
            }
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    async def save_document(self, index: str, document: Dict[str, Any]) -> str:
        """Save a document to the specified index and return its ID.
        
        Args:
            index: The index name (without prefix) to save the document to
            document: The document to save
            
        Returns:
            str: The ID of the saved document
            
        Raises:
            Exception: If there's an error saving the document
        """
        if not self.client:
            await self.connect()
        
        try:
            # Add prefix to index name
            full_index_name = f"{self.index_prefix}{index}"
            
            # Generate a document ID using URL if available, or let ES generate one
            doc_id = None
            if 'url' in document:
                # Use URL hash as document ID for deduplication
                doc_id = self._generate_document_id(document['url'])
            
            # Add timestamp if not present
            if 'timestamp' not in document:
                from datetime import datetime
                document['timestamp'] = datetime.utcnow().isoformat()
            
            # Save the document
            response = await self.client.index(
                index=full_index_name,
                id=doc_id,
                document=document,
                refresh=True  # Make the document immediately searchable
            )
            
            logger.debug(f"Document indexed: {response['_id']} in index {full_index_name}")
            return response['_id']
            
        except Exception as e:
            logger.error(f"Error indexing document: {e}")
            raise

    async def get_document(self, doc_id: str, index_name: str = None) -> Optional[Dict[str, Any]]:
        """Retrieve a document by its ID.

        Args:
            doc_id: The ID of the document to retrieve.
            index_name: Optional index name. If not provided, searches across all indices.

        Returns:
            The document, or None if not found.
        """
        if not self.client:
            await self.connect()

        try:
            index = index_name or f"{self.index_prefix}*"
            response = await self.client.get(index=index, id=doc_id, ignore=404)
            
            if not response.get("found", False):
                return None

            return {
                "id": response["_id"],
                "index": response["_index"],
                **response["_source"]
            }
        except NotFoundError:
            return None
        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
            raise

    async def delete_document(self, doc_id: str, index_name: str = None) -> bool:
        """Delete a document by its ID.

        Args:
            doc_id: The ID of the document to delete.
            index_name: Optional index name. If not provided, deletes from all indices.

        Returns:
            True if the document was deleted, False otherwise.
        """
        if not self.client:
            await self.connect()

        try:
            index = index_name or f"{self.index_prefix}*"
            response = await self.client.delete(
                index=index,
                id=doc_id,
                refresh=True,
                ignore=[404, 400]
            )
            
            if response.get("result") == "deleted":
                logger.debug(f"Deleted document {doc_id} from index {index}")
                return True
            
            logger.warning(f"Document {doc_id} not found in index {index}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            raise

    async def bulk_index(
        self, documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Index multiple documents in a single request.

        Args:
            documents: A list of documents to index.

        Returns:
            A dictionary containing the result of the bulk operation.
        """
        if not self.client:
            await self.connect()

        # Group documents by index
        index_groups = {}
        for doc in documents:
            if "url" not in doc:
                logger.warning("Document missing 'url' field, skipping")
                continue
                
            index_name = self._get_index_name(doc["url"])
            if index_name not in index_groups:
                index_groups[index_name] = []
            
            doc_id = self._generate_document_id(doc["url"])
            index_groups[index_name].append({
                "_op_type": "index",
                "_index": index_name,
                "_id": doc_id,
                "_source": doc
            })

        # Process each index group
        results = {"success": 0, "failed": 0, "errors": []}
        
        for index_name, docs in index_groups.items():
            # Ensure the index exists
            await self._ensure_index_exists(index_name)
            
            try:
                # Use the bulk API for each index
                success, errors = await async_bulk(
                    self.client,
                    docs,
                    refresh=True
                )
                
                results["success"] += success
                if errors:
                    results["failed"] += len(errors)
                    results["errors"].extend(errors)
                    
            except Exception as e:
                logger.error(f"Bulk index failed for index {index_name}: {e}")
                results["failed"] += len(docs)
                results["errors"].append({
                    "index": index_name,
                    "error": str(e)
                })
        
        return results

    async def get_status(self) -> Dict[str, Any]:
        """Get the status of the Elasticsearch cluster.

        Returns:
            A dictionary containing status information.
        """
        if not self.client:
            await self.connect()

        try:
            # Get cluster health
            health = await self.client.cluster.health()
            
            # Get cluster stats
            stats = await self.client.cluster.stats()
            
            # Get index stats for our indices
            indices = await self.client.cat.indices(
                index=f"{self.index_prefix}*",
                format="json"
            )
            
            return {
                "status": health["status"].lower(),
                "node_count": stats["nodes"]["count"]["total"],
                "indices": {
                    "total": len(indices),
                    "documents": sum(int(idx["docs.count"]) for idx in indices if idx.get("docs.count")),
                    "storage_size": sum(int(idx["store.size"]) for idx in indices if idx.get("store.size"))
                },
                "cluster_name": health["cluster_name"],
                "timed_out": health["timed_out"]
            }
        except Exception as e:
            logger.error(f"Failed to get cluster status: {e}")
            return {
                "status": "red",
                "error": str(e)
            }
