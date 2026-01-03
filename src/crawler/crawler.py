"""Core web crawling functionality."""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

import httpx
from loguru import logger
from pydantic import HttpUrl

from .config import Settings
from .extractor import ContentExtractor, ExtractedContent
from .storage.elasticsearch import ElasticsearchStorage

class Crawler:
    """Asynchronous web crawler implementation."""

    def __init__(self, settings: Settings):
        """Initialize the web crawler.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.visited_urls = set()
        self.extractor = ContentExtractor()
        self.client = self._create_client()
        self.output_file = self._get_output_file()
        self._ensure_output_dir()
        self.elasticsearch = None
        
        # Initialize Elasticsearch storage if configured
        if hasattr(settings, 'elasticsearch') and settings.elasticsearch:
            self.elasticsearch = ElasticsearchStorage(
                **settings.elasticsearch.get_es_connection_params(),
                index_prefix=settings.elasticsearch.index_prefix,
                dedupe_mode=getattr(settings.crawl, 'dedupe_mode', 'skip')
            )
            logger.info(f"Initialized Elasticsearch storage with prefix: {settings.elasticsearch.index_prefix}")
            logger.info(f"Elasticsearch connection parameters: {settings.elasticsearch.get_es_connection_params()}")
    def _create_client(self) -> httpx.AsyncClient:
        """Create and configure the HTTP client."""
        return httpx.AsyncClient(
            timeout=self.settings.crawl.timeout,
            follow_redirects=True,
            http2=True,
            headers={
                "User-Agent": self.settings.crawl.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
        )

    def _ensure_output_dir(self) -> None:
        """Ensure the output directory exists and is writable."""
        output_dir = self.settings.output.output_dir
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            if not os.access(output_dir, os.W_OK):
                raise IOError(f"Cannot write to output directory: {output_dir}")
        except Exception as e:
            logger.error(f"Failed to create output directory {output_dir}: {e}")
            raise

    def _get_output_file(self) -> Path:
        """Get the output file path based on settings."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"crawl_{timestamp}.{self.settings.output.output_format}"
        return self.settings.output.output_dir / filename

    async def _save_content(self, url: str, content: Any) -> None:
        """Save extracted content to the output file.
        
        Args:
            url: The URL the content was extracted from
            content: The extracted content, which can be a Pydantic model or a dictionary
        """
        try:
            # Handle both Pydantic models and dictionaries
            if hasattr(content, 'dict'):
                content_data = content.dict()
            elif isinstance(content, dict):
                content_data = content.copy()
            else:
                content_data = {"content": str(content)}

            # Prepare the data to save
            data = {
                "url": url,
                "timestamp": datetime.utcnow().isoformat(),
                **content_data  # Unpack all content data
            }

            # Ensure the output directory exists
            self.output_file.parent.mkdir(parents=True, exist_ok=True)

            # Save based on output format
            if self.settings.output.output_format == "jsonl":
                with open(self.output_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(data, ensure_ascii=False) + "\n")
            else:  # Default to JSON
                existing_data = []
                if self.output_file.exists():
                    try:
                        with open(self.output_file, "r", encoding="utf-8") as f:
                            existing_data = json.load(f)
                            if not isinstance(existing_data, list):
                                existing_data = [existing_data]
                    except json.JSONDecodeError:
                            existing_data = []
                    
                    existing_data.append(data)
                    with open(self.output_file, "w", encoding="utf-8") as f:
                        json.dump(existing_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved content from {url} to {self.output_file}")

            # Save to Elasticsearch if specified
            if hasattr(self.settings, 'elasticsearch') and self.settings.elasticsearch:
                logger.info(f"Saving content to Elasticsearch for URL: {url}")
                try:
                    # Save to Elasticsearch using the storage instance
                    doc_id = await self.elasticsearch.save_document(
                        index=self._get_index_name(url),  # This will be processed by _get_index_name
                        document=content#data
                    )
                    logger.info(f"Indexed document {doc_id} for URL: {url}")
                except Exception as e:
                    logger.error(f"Failed to index document for {url}: {e}")
                    if hasattr(e, '__traceback__'):
                        logger.error(f"Traceback: {e.__traceback__}")

        except Exception as e:
            logger.error(f"Failed to save content from {url}: {e}")
            if hasattr(e, '__traceback__'):
                logger.error(f"Traceback: {e.__traceback__}")

    def _get_index_name(self, url: str) -> str:
        """Generate a valid index name from the URL."""
        # Implement your logic to generate a valid index name from the URL
        # For example:
        return url.replace("https://", "").replace("http://", "").replace("/", "_")

    def _get_url_string(self, url: Union[str, HttpUrl]) -> str:
        """Convert URL to string if it's a Pydantic HttpUrl object."""
        return str(url) if hasattr(url, '__str__') else url

    async def _process_url(self, url: Union[str, HttpUrl], depth: int = 0):
        """Process a single URL.

        Args:
            url: The URL to process
            depth: Current crawl depth
        """
        url_str = self._get_url_string(url)
        
        # Skip if we've already visited this URL or max depth exceeded
        if (url_str in self.visited_urls or 
            (self.settings.crawl.depth is not None and depth > self.settings.crawl.depth)):
            return

        self.visited_urls.add(url_str)
        logger.info(f"Processing URL: {url_str} (depth: {depth})")

        try:
            # Only check for duplicates if we're at max depth (leaf node)
            is_leaf_node = (self.settings.crawl.depth is not None and 
                          depth >= self.settings.crawl.depth)
            
            if (hasattr(self.settings, 'elasticsearch') and 
                self.elasticsearch and
                hasattr(self.settings.crawl, 'dedupe_mode') and
                is_leaf_node):  # Only check for duplicates on leaf nodes
                
                # Get dedupe mode from settings
                dedupe_mode = self.settings.crawl.dedupe_mode
                
                # Check if we should skip this URL
                if not await self.elasticsearch.should_recrawl(url_str, mode=dedupe_mode):
                    logger.info(f"Skipping duplicate leaf URL: {url_str}")
                    return

            # Make the HTTP request
            response = await self.client.get(url_str)
            response.raise_for_status()

            # Extract content - pass only the HTML content, URL is not needed as it's already set in the ExtractedContent
            content = self.extractor.extract(html_content=response.text, url=url_str)
            
            # Save the extracted content
            await self._save_content(url_str, content)

            # Process links if we haven't reached max depth
            if self.settings.crawl.depth is None or depth < self.settings.crawl.depth:
                # Get links from the extracted content
                links = getattr(content, 'links', [])
                
                # Process links in parallel with a limit on concurrency
                tasks = []
                for link in links[:getattr(self.settings.crawl, 'max_links_per_page', 50)]:
                    link_url = link[0] if isinstance(link, (list, tuple)) else link
                    if isinstance(link_url, str) and link_url not in self.visited_urls:
                        tasks.append(
                            self._process_url(link_url, depth + 1)
                        )
                
                # Process links with concurrency control
                max_concurrent = getattr(self.settings.crawl, 'max_concurrent_requests', 10)
                for i in range(0, len(tasks), max_concurrent):
                    batch = tasks[i:i + max_concurrent]
                    await asyncio.gather(*batch, return_exceptions=True)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for {url_str}: {e.response.status_code} {e.response.reason_phrase}")
            # Save error information if Elasticsearch is enabled
            if hasattr(self, 'elasticsearch') and self.elasticsearch:
                try:
                    error_doc = {
                        "url": url_str,
                        "error": {
                            "status_code": e.response.status_code,
                            "reason": e.response.reason_phrase,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                    await self.elasticsearch.save_document(
                        index=self._get_index_name(url_str),
                        document=error_doc
                    )
                except Exception as es_error:
                    logger.error(f"Failed to save error to Elasticsearch: {es_error}")
                    
        except Exception as e:
            logger.error(f"Error processing {url_str}: {str(e)}")
            if hasattr(e, '__traceback__'):
                logger.error(f"Traceback: {e.__traceback__}")

    async def close(self):
        """Close all resources including HTTP client and Elasticsearch connection."""
        try:
            if hasattr(self, 'client') and self.client:
                await self.client.aclose()
                logger.debug("HTTP client closed successfully")
                
            if hasattr(self, 'elasticsearch') and self.elasticsearch:
                if hasattr(self.elasticsearch, 'close') and callable(self.elasticsearch.close):
                    await self.elasticsearch.close()
                    logger.debug("Elasticsearch client closed successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            raise

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures resources are cleaned up."""
        await self.close()

    async def crawl(self):
        """Start the crawling process."""
        logger.info(f"Starting crawl of {len(self.settings.start_urls)} URLs")
        
        try:
            tasks = [self._process_url(url) for url in self.settings.start_urls]
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error during crawling: {e}")
            raise
        finally:
            # Don't close the client here, let the context manager handle it
            pass

async def crawl(settings: Settings):
    """Run the crawler with the given settings."""
    async with Crawler(settings) as crawler:
        # Check Elasticsearch connection if configured
        if crawler.elasticsearch:
            max_retries = 3
            retry_delay = 2  # seconds
            
            for attempt in range(1, max_retries + 1):
                try:
                    await crawler.elasticsearch.connect()
                    logger.info("Successfully connected to Elasticsearch")
                    break
                except Exception as e:
                    if attempt < max_retries:
                        logger.warning(f"Failed to connect to Elasticsearch (attempt {attempt}/{max_retries}): {e}")
                        await asyncio.sleep(retry_delay * attempt)
                    else:
                        logger.error(f"Failed to connect to Elasticsearch after {max_retries} attempts")
                        raise
        
        # Start the crawl
        await crawler.crawl()