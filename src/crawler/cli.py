"""
Web Crawler - A high-performance, asynchronous web crawler for data extraction.

Basic usage:
    crawler crawl [URL] [OUTPUT_DIR]

Example:
    crawler crawl https://example.com ./output
"""

import os
import sys
from pathlib import Path
from typing import List, Optional

import click
from loguru import logger

from .version import __version__
from .config import Settings, OutputSettings, CrawlSettings, ElasticsearchSettings

def setup_logging(level: str = "INFO"):
    """Configure loguru logging."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )
    logger.enable("crawler")

def common_options(f):
    """Common CLI options for commands that interact with Elasticsearch."""
    options = [
        click.option(
            "--es-hosts",
            multiple=True,
            default=["http://localhost:9200"],
            help="Elasticsearch hosts (can be specified multiple times).",
            show_default=True,
        ),
        click.option(
            "--es-index-prefix",
            default="crawler_",
            help="Prefix for Elasticsearch indices.",
            show_default=True,
        ),
        click.option(
            "--es-username",
            help="Username for Elasticsearch authentication.",
            default=None,
        ),
        click.option(
            "--es-password",
            help="Password for Elasticsearch authentication.",
            default=None,
        ),
        click.option(
            "--es-use-ssl/--no-es-use-ssl",
            default=False,
            help="Enable/disable SSL for Elasticsearch connection.",
            show_default=True,
        ),
        click.option(
            "--es-verify-certs/--no-es-verify-certs",
            default=True,
            help="Verify SSL certificates for Elasticsearch.",
            show_default=True,
        ),
        click.option(
            "--es-ca-certs",
            type=click.Path(exists=True, dir_okay=False, path_type=Path),
            help="Path to CA certificate bundle for Elasticsearch.",
            default=None,
        ),
        click.option(
            "--es-bulk-size",
            type=int,
            default=1000,
            help="Number of documents to index in a single bulk request.",
            show_default=True,
        ),
        click.option(
            "--es-timeout",
            type=int,
            default=30,
            help="Timeout in seconds for Elasticsearch operations.",
            show_default=True,
        ),
        click.option(
            "--es-retries",
            type=int,
            default=3,
            help="Maximum number of retries for failed requests.",
            show_default=True,
        ),
    ]
    for option in reversed(options):
        f = option(f)
    return f

@click.group()
@click.version_option(__version__, "-V", "--version", message="%(prog)s %(version)s")
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
@click.pass_context
def cli(ctx: click.Context, log_level: str):
    """Web Crawler - A high-performance, asynchronous web crawler for data extraction."""
    setup_logging(log_level)
    ctx.ensure_object(dict)
    ctx.obj["LOG_LEVEL"] = log_level

@cli.command()
@click.argument("url", type=str, required=True)
@click.argument("output_dir", type=click.Path(file_okay=False, writable=True, path_type=Path), required=True)
@click.option(
    "--use-es",
    is_flag=True,
    help="Enable Elasticsearch storage for crawled content",
)
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
    "--output-format",
    type=click.Choice(["jsonl", "json", "parquet"]),
    default="jsonl",
    show_default=True,
    help="Output format for saved content.",
)
@click.option(
    "--max-concurrent-requests",
    type=click.IntRange(1, 100),
    default=10,
    show_default=True,
    help="Maximum number of concurrent HTTP requests.",
)
@click.option(
    "--max-links-per-page",
    type=click.IntRange(1, 1000),
    default=50,
    show_default=True,
    help="Maximum number of links to follow per page.",
)
@click.option(
    "--dedupe-mode",
    type=click.Choice(["skip", "force", "if-modified"], case_sensitive=False),
    default="skip",
    show_default=True,
    help="Deduplication mode: 'skip' to skip existing, 'force' to recrawl, 'if-modified' to check for changes",
)
@click.option(
    "--cache-ttl",
    type=click.IntRange(0, 86400 * 7),  # 0 to 7 days
    default=3600,  # 1 hour
    show_default=True,
    help="Time-to-live for document cache in seconds (0 = no caching).",
)
@common_options
@click.pass_context
def crawl(
    ctx: click.Context,
    url: str,
    output_dir: Path,
    use_es: bool,
    max_depth: int,
    workers: int,
    output_format: str,
    max_concurrent_requests: int,
    max_links_per_page: int,
    dedupe_mode: str,
    cache_ttl: int,
    **es_kwargs
):
    """Crawl a website and save the extracted content.
    
    URL:        The starting URL to crawl
    OUTPUT_DIR: Directory to save the extracted content
    """
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Prepare settings
        settings = Settings(
            start_urls=[url],
            crawl=CrawlSettings(
                max_depth=max_depth,
                workers=workers,
                max_concurrent_requests=max_concurrent_requests,
                max_links_per_page=max_links_per_page,
                dedupe_mode=dedupe_mode,
                cache_ttl=cache_ttl,
            ),
            output=OutputSettings(
                output_dir=output_dir,
                output_format=output_format,
            ),
        )

        # Configure Elasticsearch if enabled
        if use_es:
            settings.elasticsearch = ElasticsearchSettings(
                **{
                    k[3:]: v 
                    for k, v in es_kwargs.items()
                    if k.startswith("es_") and v is not None
                }
            )

        # Create and run the crawler
        from .crawler import crawl as run_crawler_async
        import asyncio
        
        # Run the async crawl function
        asyncio.run(run_crawler_async(settings))

    except Exception as e:
        logger.error(f"Crawling failed: {e}")
        if ctx.obj and ctx.obj.get("debug"):
            import traceback
            traceback.print_exc()
        sys.exit(1)

@cli.group()
def es():
    """Elasticsearch management commands."""
    pass

@es.command("create-index")
@click.argument("index_name", required=False)
@click.option(
    "--shards",
    type=int,
    default=1,
    help="Number of primary shards.",
    show_default=True,
)
@click.option(
    "--replicas",
    type=int,
    default=1,
    help="Number of replica shards.",
    show_default=True,
)
@common_options
@click.pass_context
def create_index(
    ctx: click.Context,
    index_name: Optional[str],
    shards: int,
    replicas: int,
    **es_kwargs
):
    """Create a new Elasticsearch index."""
    try:
        from .storage.elasticsearch import ElasticsearchStorage
        
        # Initialize Elasticsearch storage
        es = ElasticsearchStorage(
            hosts=es_kwargs["es_hosts"],
            index_prefix=es_kwargs["es_index_prefix"],
            **{
                k[3:]: v for k, v in es_kwargs.items()
                if k not in ["es_hosts", "es_index_prefix"]
            }
        )
        
        import asyncio
        asyncio.run(es.connect())
        
        if not index_name:
            index_name = f"{es_kwargs['es_index_prefix']}default"
        elif not index_name.startswith(es_kwargs['es_index_prefix']):
            index_name = f"{es_kwargs['es_index_prefix']}{index_name}"
        
        # Create the index
        asyncio.run(es._ensure_index_exists(index_name))
        logger.info(f"Created index: {index_name}")
        
    except Exception as e:
        logger.error(f"Failed to create index: {e}")
        if logger.level("DEBUG"):
            import traceback
            logger.debug(traceback.format_exc())
        sys.exit(1)

@es.command("delete-index")
@click.argument("index_name")
@click.option(
    "--force",
    is_flag=True,
    help="Don't ask for confirmation before deleting.",
)
@common_options
@click.pass_context
def delete_index(
    ctx: click.Context,
    index_name: str,
    force: bool,
    **es_kwargs
):
    """Delete an Elasticsearch index."""
    try:
        from .storage.elasticsearch import ElasticsearchStorage
        
        # Initialize Elasticsearch storage
        es = ElasticsearchStorage(
            hosts=es_kwargs["es_hosts"],
            index_prefix=es_kwargs["es_index_prefix"],
            **{
                k[3:]: v for k, v in es_kwargs.items()
                if k not in ["es_hosts", "es_index_prefix"]
            }
        )
        
        import asyncio
        asyncio.run(es.connect())
        
        if not index_name.startswith(es_kwargs['es_index_prefix']):
            index_name = f"{es_kwargs['es_index_prefix']}{index_name}"
        
        if not force:
            click.confirm(
                f"Are you sure you want to delete index '{index_name}'? This cannot be undone.",
                abort=True
            )
        
        # Delete the index
        asyncio.run(es.client.indices.delete(index=index_name, ignore=[400, 404]))
        logger.info(f"Deleted index: {index_name}")
        
    except Exception as e:
        logger.error(f"Failed to delete index: {e}")
        if logger.level("DEBUG"):
            import traceback
            logger.debug(traceback.format_exc())
        sys.exit(1)

@es.command("list-indices")
@common_options
@click.pass_context
def list_indices(ctx: click.Context, **es_kwargs):
    """List all indices with the configured prefix."""
    try:
        from .storage.elasticsearch import ElasticsearchStorage
        
        # Initialize Elasticsearch storage
        es = ElasticsearchStorage(
            hosts=es_kwargs["es_hosts"],
            index_prefix=es_kwargs["es_index_prefix"],
            **{
                k[3:]: v for k, v in es_kwargs.items()
                if k not in ["es_hosts", "es_index_prefix"]
            }
        )
        
        import asyncio
        
        async def list_indices_async():
            await es.connect()
            cat = await es.client.cat.indices(
                index=f"{es_kwargs['es_index_prefix']}*",
                format="json"
            )
            return cat
        
        indices = asyncio.run(list_indices_async())
        
        if not indices:
            logger.info("No indices found.")
            return
        
        # Print a formatted table of indices
        from tabulate import tabulate
        
        headers = ["Index", "Docs", "Size", "Health", "Status"]
        table = []
        
        for idx in indices:
            table.append([
                idx["index"],
                idx.get("docs.count", "N/A"),
                idx.get("store.size", "N/A"),
                idx.get("health", "N/A"),
                idx.get("status", "N/A"),
            ])
        
        click.echo(tabulate(table, headers=headers, tablefmt="grid"))
        
    except Exception as e:
        logger.error(f"Failed to list indices: {e}")
        if logger.level("DEBUG"):
            import traceback
            logger.debug(traceback.format_exc())
        sys.exit(1)

def main():
    """Entry point for the CLI."""
    cli(obj={})

if __name__ == "__main__":
    main()