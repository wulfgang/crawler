"""Asynchronous HTTP client for the web crawler with rate limiting and retries."""

import asyncio
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, Optional, Tuple, Union, cast
from urllib.parse import urljoin, urlparse

import httpx
from loguru import logger

from .config import Settings
from .extractor import ContentExtractor, ExtractedContent


@dataclass
class Response:
    """HTTP response wrapper with additional metadata."""

    url: str
    status_code: int
    content: bytes
    headers: Dict[str, str]
    encoding: str
    elapsed: float
    redirected_url: Optional[str] = None
    error: Optional[str] = None
    extracted_content: Optional[ExtractedContent] = None

    @property
    def text(self) -> str:
        """Get response content as text."""
        return self.content.decode(self.encoding or "utf-8", errors="replace")

    @property
    def is_success(self) -> bool:
        """Check if the request was successful (status code 2xx)."""
        return 200 <= self.status_code < 300


class RateLimiter:
    """Rate limiter for controlling request rates."""

    def __init__(self, requests_per_second: float):
        """Initialize rate limiter.

        Args:
            requests_per_second: Maximum number of requests per second
        """
        self.rate = requests_per_second
        self.tokens = self.rate
        self.updated_at = datetime.now()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Acquire a token from the rate limiter."""
        async with self.lock:
            now = datetime.now()
            time_passed = (now - self.updated_at).total_seconds()
            self.updated_at = now

            # Add tokens based on time passed
            self.tokens += time_passed * self.rate
            if self.tokens > self.rate:
                self.tokens = self.rate  # Cap at max tokens

            # If we have enough tokens, take one and proceed
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return

            # Otherwise, wait until we have enough tokens
            wait_time = (1.0 - self.tokens) / self.rate
            self.tokens = 0.0

        # Sleep outside the lock to allow other tasks to acquire the lock
        await asyncio.sleep(wait_time)


class HTTPClient:
    """Asynchronous HTTP client with rate limiting and retries."""

    def __init__(self, settings: Settings):
        """Initialize the HTTP client.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.crawl_settings = settings.crawl
        self.rate_limiter = RateLimiter(1.0 / self.crawl_settings.request_delay)
        self.extractor = ContentExtractor(include_metadata=settings.output.include_metadata)

        # Initialize HTTP client with default headers and timeouts
        self.client = httpx.AsyncClient(
            timeout=self.crawl_settings.timeout,
            follow_redirects=True,
            http2=True,
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=self.crawl_settings.workers * 2,
            ),
            headers={
                "User-Agent": self.crawl_settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        # Robots.txt cache
        self._robots_cache: Dict[str, Tuple[datetime, bool]] = {}
        self._robots_cache_ttl = timedelta(hours=1)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _check_robots_txt(self, url: str) -> bool:
        """Check if a URL is allowed by robots.txt.

        Args:
            url: URL to check

        Returns:
            bool: True if allowed, False if disallowed or error
        """
        if not self.crawl_settings.respect_robots_txt:
            return True

        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = f"{base_url}/robots.txt"

        # Check cache first
        now = datetime.now()
        if base_url in self._robots_cache:
            cached_time, allowed = self._robots_cache[base_url]
            if now - cached_time < self._robots_cache_ttl:
                return allowed

        try:
            # Fetch robots.txt
            response = await self.client.get(robots_url, follow_redirects=False)
            if response.status_code == 200:
                # Simple check - in a real implementation, use a proper robots.txt parser
                if b"Disallow: /" in response.content:
                    self._robots_cache[base_url] = (now, False)
                    return False

            self._robots_cache[base_url] = (now, True)
            return True

        except Exception as e:
            logger.warning(f"Error checking robots.txt for {url}: {str(e)}")
            # If we can't check robots.txt, assume it's allowed
            self._robots_cache[base_url] = (now, True)
            return True

    async def get(
        self, 
        url: str, 
        max_retries: int = 3,
        extract_content: bool = True,
        **kwargs
    ) -> AsyncGenerator[Response, None]:
        """Make an HTTP GET request with retries and rate limiting.

        Args:
            url: URL to fetch
            max_retries: Maximum number of retry attempts
            extract_content: Whether to extract content from HTML responses
            **kwargs: Additional arguments to pass to httpx

        Yields:
            Response object with optional extracted content
        """
        # Check robots.txt first
        if not await self._check_robots_txt(url):
            logger.warning(f"Blocked by robots.txt: {url}")
            response = Response(
                url=url,
                status_code=403,
                content=b"Blocked by robots.txt",
                headers={},
                encoding="utf-8",
                elapsed=0,
                error="Blocked by robots.txt",
            )
            yield response
            return

        # Apply rate limiting
        await self.rate_limiter.acquire()

        # Set default headers
        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", self.crawl_settings.user_agent)

        # Make the request with retries
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                start_time = datetime.now()
                async with self.client.stream("GET", url, headers=headers, **kwargs) as response:
                    # Read the response content
                    content = b""
                    async for chunk in response.aiter_bytes():
                        content += chunk

                    elapsed = (datetime.now() - start_time).total_seconds()

                    # Create response object
                    response_obj = Response(
                        url=str(response.url),
                        status_code=response.status_code,
                        content=content,
                        headers=dict(response.headers),
                        encoding=response.encoding or "utf-8",
                        elapsed=elapsed,
                        redirected_url=(
                            str(response.url) if response.url != url else None
                        ),
                    )

                    # Extract content if requested and the response is HTML
                    if (extract_content and 
                        response_obj.is_success and 
                        "text/html" in response.headers.get("content-type", "").lower()):
                        response_obj.extracted_content = self.extractor.extract(
                            url=url,
                            html_content=response_obj.text
                        )

                    yield response_obj
                    return

            except (httpx.HTTPError, OSError) as e:
                last_error = e
                if attempt < max_retries:
                    # Exponential backoff with jitter
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait_time:.2f}s..."
                    )
                    await asyncio.sleep(wait_time)
                continue

        # If we get here, all retries failed
        error_msg = (
            f"Failed to fetch {url} after {max_retries + 1} attempts: {last_error}"
        )
        logger.error(error_msg)
        yield Response(
            url=url,
            status_code=0,
            content=b"",
            headers={},
            encoding="utf-8",
            elapsed=0,
            error=str(last_error),
        )

    async def get_and_extract(
        self,
        url: str,
        max_retries: int = 3,
        **kwargs
    ) -> AsyncGenerator[Response, None]:
        """Convenience method to get and extract content in one step.
        
        This is equivalent to calling get() with extract_content=True.
        
        Args:
            url: URL to fetch and extract content from
            max_retries: Maximum number of retry attempts
            **kwargs: Additional arguments to pass to get()
            
        Yields:
            Response object with extracted content
        """
        async for response in self.get(url, max_retries=max_retries, extract_content=True, **kwargs):
            yield response
