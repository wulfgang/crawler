"""Web crawler package for extracting content from websites."""
from .version import __version__
from .cli import main
from .config import Settings, CrawlSettings, OutputSettings
from .crawler import crawl, Crawler
from .extractor import ContentExtractor

__all__ = [
    "main",
    "Settings",
    "CrawlSettings",
    "OutputSettings",
    "crawl",
    "Crawler",
    "ContentExtractor",
]
