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
                index_prefix=settings.elasticsearch.index_prefix
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

            logger.debug(f"Saved content from {url} to {self.output_file}")

            # Save to Elasticsearch if specified
            if hasattr(self.settings, 'elasticsearch') and self.settings.elasticsearch:
                try:
                    # Save to Elasticsearch using the storage instance
                    doc_id = await self.elasticsearch.save_document(
                        index=self._get_index_name(url),  # This will be processed by _get_index_name
                        document=data
                    )
                    logger.debug(f"Indexed document {doc_id} for URL: {url}")
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
        """Process a single URL."""
        if depth > self.settings.crawl.depth:
            return

        url_str = self._get_url_string(url)
        if url_str in self.visited_urls:
            return

        self.visited_urls.add(url_str)
        logger.info(f"Crawling: {url_str} (depth: {depth})")

        try:
            response = await self.client.get(url_str)
            response.raise_for_status()
            
            # Extract content
            extracted = self.extractor.extract(str(response.url), response.text)
            if extracted:
                # Save the extracted content
                await self._save_content(url_str, extracted)
                logger.info(f"Extracted content from {url_str}: {extracted.title}")
            
            # Process links for further crawling if we haven't reached max depth
            if depth < self.settings.crawl.depth:
                # Extract links from the page
                links = [link[0] for link in extracted.links] if extracted and hasattr(extracted, 'links') else []
                
                # Process child URLs with increased depth
                tasks = [self._process_url(link, depth + 1) for link in links]
                if tasks:
                    await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"Error processing {url_str}: {str(e)}")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def crawl(self):
        """Start the crawling process."""
        logger.info(f"Starting crawl of {len(self.settings.start_urls)} URLs")
        
        try:
            tasks = [self._process_url(url) for url in self.settings.start_urls]
            await asyncio.gather(*tasks)
        finally:
            await self.close()

async def crawl(settings: Settings):
    """Run the crawler with the given settings."""
    crawler = Crawler(settings)
    
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
                # Get the ElasticsearchStorage instance
                es = crawler.elasticsearch
                
                # Get all relevant configuration parameters
                config_params = {
                    'hosts': es.hosts,
                    'index_prefix': es.index_prefix,
                    'username': es.username if hasattr(es, 'username') else None,
                    'use_ssl': es.use_ssl if hasattr(es, 'use_ssl') else None,
                    'verify_certs': es.verify_certs if hasattr(es, 'verify_certs') else None,
                    'ca_certs': str(es.ca_certs) if hasattr(es, 'ca_certs') and es.ca_certs else None,
                    'timeout': f"{es.timeout}s" if hasattr(es, 'timeout') else None,
                    'max_retries': es.max_retries if hasattr(es, 'max_retries') else None,
                    'bulk_size': es.bulk_size if hasattr(es, 'bulk_size') else None
                }
                
                # Filter out None values for cleaner output
                config_params = {k: v for k, v in config_params.items() if v is not None}
                
                # Format configuration for display
                config_display = "\n  ".join(f"{k}: {v}" for k, v in config_params.items())
                
                error_details = {
                    'attempt': f"{attempt}/{max_retries}",
                    'error_type': e.__class__.__name__,
                    'error_message': str(e),
                    'config': config_display
                }
                
                if attempt == max_retries:
                    error_msg = (
                        "❌ Failed to connect to Elasticsearch after {attempt} attempts\n\n"
                        "🔧 Configuration Used:\n"
                        "  {config}\n\n"
                        "💥 Error Details:\n"
                        "  - Type: {error_type}\n"
                        "  - Message: {error_message}\n\n"
                        "🔍 Troubleshooting Tips:\n"
                        "  1. Verify that your Elasticsearch server is running and accessible\n"
                        "  2. Check if the host and port are correct\n"
                        "  3. If using authentication, verify the username and password\n"
                        "  4. For SSL/TLS connections, ensure the certificates are valid\n"
                        "  5. Check if any firewall is blocking the connection"
                    ).format(**error_details)
                    
                    logger.error(error_msg)
                    await crawler.close()
                    sys.exit(1)
                
                logger.warning(
                    "⚠️  Elasticsearch connection attempt {attempt} failed: {error_type} - {error_message}\n"
                    "   Using config: {config}\n"
                    "   Retrying in {delay}s... (Attempt {current}/{total})".format(
                        attempt=attempt,
                        error_type=error_details['error_type'],
                        error_message=error_details['error_message'],
                        config=config_display,
                        delay=retry_delay,
                        current=attempt,
                        total=max_retries
                    )
                )
                await asyncio.sleep(retry_delay)
    
    try:
        await crawler.crawl()
    finally:
        await crawler.close()
