"""
Web Crawler - A high-performance, asynchronous web crawler for data extraction.

Basic usage:
    crawler [URL] [OUTPUT_DIR]

Example:
    crawler https://example.com ./output
"""

import os
import sys
from pathlib import Path
from typing import List

import click
from loguru import logger

from .version import __version__
from .config import Settings, OutputSettings, CrawlSettings

def setup_logging(level: str = "INFO"):
    """Configure loguru logging."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )
    logger.enable("crawler")

@click.command()
@click.version_option(__version__, "-V", "--version", message="%(prog)s %(version)s")
@click.argument("url", type=str, required=True)
@click.argument("output_dir", type=click.Path(file_okay=False, writable=True, path_type=Path), required=True)
@click.option(
    "-d", "--max-depth",
    type=click.IntRange(0, 10),
    default=1,
    show_default=True,
    help="Maximum depth to crawl (0 = only the start URL).",
)
@click.option(
    "-w", "--workers",
    type=click.IntRange(1, 100),
    default=4,
    show_default=True,
    help="Number of concurrent workers for crawling.",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"],
        case_sensitive=False,
    ),
    default="INFO",
    show_default=True,
    help="Set the logging level.",
)
def main(url: str, output_dir: Path, max_depth: int, workers: int, log_level: str):
    """Crawl a website and save the extracted content.
    
    URL:        The starting URL to crawl
    OUTPUT_DIR: Directory to save the extracted content
    """
    setup_logging(log_level)
    
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        settings = Settings(
            start_urls=[url],
            output=OutputSettings(output_dir=output_dir),
            crawl=CrawlSettings(
                max_depth=max_depth,
                workers=workers,
                request_delay=1.0,
                respect_robots_txt=True,
            ),
        )
        
        from .crawler import crawl
        import asyncio
        asyncio.run(crawl(settings))
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if log_level == "DEBUG":
            import traceback
            logger.debug(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()