"""Content extraction utilities for the web crawler."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import trafilatura
from bs4 import BeautifulSoup, FeatureNotFound
from loguru import logger


@dataclass
class ExtractedContent:
    """Structured content extracted from a web page."""
    
    url: str
    title: str
    content: str
    text: str
    language: str = "en"
    metadata: Dict[str, str] = None
    links: List[Tuple[str, str]] = None  # (url, text)
    images: List[Dict[str, str]] = None  # List of image metadata dicts


class ContentExtractor:
    """Extracts and processes content from web pages."""
    
    def __init__(self, include_metadata: bool = True):
        """Initialize the content extractor.
        
        Args:
            include_metadata: Whether to include metadata in the output
        """
        self.include_metadata = include_metadata
        self._init_parser()
    
    def _init_parser(self):
        """Initialize the HTML parser with fallback options."""
        self.parsers = []
        
        # Try different parsers in order of preference
        for parser in ["lxml", "html.parser", "html5lib"]:
            try:
                self.parsers.append(parser)
            except FeatureNotFound:
                logger.debug(f"Parser {parser} not available")
                continue
        
        if not self.parsers:
            raise RuntimeError("No suitable HTML parser found")
    
    def extract(self, url: str, html_content: str) -> Optional[ExtractedContent]:
        """Extract content from HTML.
        
        Args:
            url: The URL the HTML was fetched from
            html_content: Raw HTML content as a string
            
        Returns:
            ExtractedContent object or None if extraction failed
        """
        if not html_content.strip():
            logger.warning(f"Empty HTML content for {url}")
            return None
            
        try:
            # First try trafilatura for main content extraction
            traf_result = self._extract_with_trafilatura(html_content)
            
            # Parse with BeautifulSoup for additional data
            soup = self._parse_html(html_content)
            
            # Extract title with fallbacks
            title = self._extract_title(soup, traf_result)
            
            # Extract links and images
            links = self._extract_links(soup, url)
            images = self._extract_images(soup, url)
            
            # Get language (default to 'en' if not detected)
            language = traf_result.get("language", "en") if traf_result else "en"
            
            # Get main content text
            content = traf_result.get("content", "") if traf_result else self._extract_fallback_content(soup)
            
            # Get metadata if requested
            metadata = {}
            if self.include_metadata:
                metadata = self._extract_metadata(soup, traf_result)
            
            return ExtractedContent(
                url=url,
                title=title,
                content=content,
                text=content,  # For backward compatibility
                language=language,
                metadata=metadata,
                links=links,
                images=images
            )
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}")
            if logger.level("DEBUG"):
                logger.opt(exception=True).debug("Extraction error details:")
            return None
    
    def _parse_html(self, html_content: str) -> BeautifulSoup:
        """Parse HTML with fallback to different parsers."""
        last_error = None
        
        for parser in self.parsers:
            try:
                return BeautifulSoup(html_content, parser)
            except Exception as e:
                last_error = e
                logger.debug(f"Failed to parse with {parser}: {str(e)}")
                continue
        
        logger.error("All HTML parsers failed")
        raise last_error or RuntimeError("HTML parsing failed")
    
    def _extract_with_trafilatura(self, html_content: str) -> Optional[Dict]:
        """Extract content using trafilatura with error handling."""
        try:
            # Configure trafilatura
            config = trafilatura.settings.use_config()
            config.set("DEFAULT", "EXTRACTION_TIMEOUT", "0")  # No timeout
            
            # Extract content
            result = trafilatura.extract(
                html_content,
                include_links=True,
                include_images=True,
                include_tables=True,
                output_format='json',
                config=config
            )
            
            if not result:
                return None
                
            return trafilatura.loads(result)
            
        except Exception as e:
            logger.debug(f"trafilatura extraction failed: {str(e)}")
            return None
    
    def _extract_title(self, soup: BeautifulSoup, traf_result: Optional[Dict]) -> str:
        """Extract the page title with fallbacks."""
        # Try trafilatura title first if available
        if traf_result and traf_result.get("title"):
            return traf_result["title"].strip()
        
        # Try OpenGraph title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()
        
        # Try HTML title tag
        title_tag = soup.find("title")
        if title_tag and title_tag.text.strip():
            return title_tag.text.strip()
        
        # Try h1 tag
        h1 = soup.find("h1")
        if h1 and h1.text.strip():
            return h1.text.strip()
        
        return "Untitled"
    
    def _extract_fallback_content(self, soup: BeautifulSoup) -> str:
        """Fallback content extraction if trafilatura fails."""
        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
        
        # Get text from main, article, or body
        for tag in ["main", "article", "body"]:
            element = soup.find(tag)
            if element:
                return element.get_text(" ", strip=True)
        
        # Last resort: get all text
        return soup.get_text(" ", strip=True)
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Tuple[str, str]]:
        """Extract all links from the page with their anchor text."""
        links = []
        base_domain = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
        
        for a in soup.find_all("a", href=True):
            try:
                href = a["href"].strip()
                text = a.get_text(" ", strip=True)[:500]  # Limit text length
                
                # Skip empty links or non-HTTP links
                if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                    continue
                
                # Make relative URLs absolute
                href = self._make_absolute_url(href, base_url, base_domain)
                if not href:
                    continue
                    
                links.append((href, text))
                
            except Exception as e:
                logger.debug(f"Error processing link: {str(e)}")
                continue
                
        return links
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract images from the page with their metadata."""
        images = []
        base_domain = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
        
        for img in soup.find_all("img", src=True):
            try:
                src = img["src"].strip()
                
                # Skip empty or data URLs
                if not src or src.startswith("data:"):
                    continue
                
                # Make relative URLs absolute
                src = self._make_absolute_url(src, base_url, base_domain)
                if not src:
                    continue
                
                # Get alt text and title
                alt = img.get("alt", "").strip()
                title = img.get("title", alt).strip()
                
                images.append({
                    "url": src,
                    "alt": alt,
                    "title": title
                })
                
            except Exception as e:
                logger.debug(f"Error processing image: {str(e)}")
                continue
                
        return images
    
    def _extract_metadata(self, soup: BeautifulSoup, traf_result: Optional[Dict]) -> Dict[str, str]:
        """Extract metadata from the page."""
        metadata = {}
        
        # Add trafilatura metadata if available
        if traf_result:
            for key, value in traf_result.items():
                if key not in ["text", "title", "raw_text", "content"] and value:
                    metadata[key] = value
        
        # Add OpenGraph metadata
        for meta in soup.find_all("meta"):
            if meta.get("property", "").startswith("og:"):
                content = meta.get("content", "").strip()
                if content:
                    metadata[meta["property"]] = content
        
        # Add standard meta tags
        for meta in soup.find_all("meta"):
            if meta.get("name") and meta.get("content"):
                metadata[meta["name"]] = meta["content"].strip()
        
        return metadata
    
    @staticmethod
    def _make_absolute_url(url: str, base_url: str, base_domain: str) -> Optional[str]:
        """Convert a relative URL to absolute."""
        try:
            if url.startswith("//"):
                return f"https:{url}"  # Protocol-relative URL
            elif url.startswith("/"):
                return f"{base_domain}{url}"  # Root-relative URL
            elif not url.startswith(("http://", "https://")):
                return f"{base_url.rstrip('/')}/{url.lstrip('/')}"  # Path-relative URL
            return url  # Already absolute
        except Exception as e:
            logger.debug(f"Error making URL absolute: {str(e)}")
            return None
