"""Configuration management for the web crawler."""

import os
from pathlib import Path
from typing import List, Optional, Pattern

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CrawlSettings(BaseModel):
    """Configuration for the crawling process."""

    depth: int = Field(
        default=1,
        ge=0,
        description="Maximum depth to crawl (0 means only the start URL)",
    )
    workers: int = Field(
        default=4,
        ge=1,
        le=100,
        description="Number of concurrent workers for crawling",
    )
    request_delay: float = Field(
        default=1.0,
        ge=0,
        description="Delay between requests in seconds",
    )
    timeout: float = Field(
        default=30.0,
        gt=0,
        description="Request timeout in seconds",
    )
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (compatible; WebCrawler/1.0; "
            "+https://github.com/yourusername/web-crawler)"
        ),
        description="User-Agent string to use for requests",
    )
    include_patterns: List[str] = Field(
        default_factory=list,
        description="Regex patterns of URLs to include in the crawl",
    )
    exclude_patterns: List[str] = Field(
        default_factory=list,
        description="Regex patterns of URLs to exclude from the crawl",
    )
    respect_robots_txt: bool = Field(
        default=True,
        description="Whether to respect robots.txt rules",
    )


class OutputSettings(BaseModel):
    """Configuration for output settings."""

    output_dir: Path = Field(
        default=Path("output"),
        description="Directory to save output files",
    )
    output_format: str = Field(
        default="jsonl",
        pattern=r"^(jsonl|parquet|csv)$",
        description="Output format (jsonl, parquet, or csv)",
    )
    chunk_size: int = Field(
        default=1000,
        gt=0,
        description="Number of tokens per chunk when splitting content",
    )
    chunk_overlap: int = Field(
        default=100,
        ge=0,
        description="Number of overlapping tokens between chunks",
    )
    include_metadata: bool = Field(
        default=True,
        description="Whether to include metadata in the output",
    )

    @field_validator('output_dir')
    @classmethod
    def validate_output_dir(cls, v: Path) -> Path:
        """Ensure output directory exists and is writable."""
        try:
            v = v.resolve()
            v.mkdir(parents=True, exist_ok=True)
            if not os.access(v, os.W_OK):
                raise ValueError(f"Cannot write to output directory: {v}")
            return v
        except Exception as e:
            raise ValueError(f"Invalid output directory '{v}': {str(e)}")


class Settings(BaseSettings):
    """Main settings class for the web crawler."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        env_prefix="WEB_CRAWLER_",
        extra="ignore",
    )

    start_urls: List[HttpUrl] = Field(
        ...,
        description="List of starting URLs to crawl",
    )
    crawl: CrawlSettings = Field(
        default_factory=CrawlSettings,
        description="Crawling configuration",
    )
    output: OutputSettings = Field(
        default_factory=OutputSettings,
        description="Output configuration",
    )

    @field_validator('start_urls')
    @classmethod
    def validate_start_urls(cls, v: List[HttpUrl]) -> List[HttpUrl]:
        """Ensure at least one start URL is provided."""
        if not v:
            raise ValueError("At least one start URL must be provided")
        return v

    @model_validator(mode='after')
    def validate_paths(self) -> 'Settings':
        """Validate all file paths in the settings."""
        # The OutputSettings validator will handle output directory validation
        return self


# Example usage:
# settings = Settings(start_urls=["https://example.com"])
