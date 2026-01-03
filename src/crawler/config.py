"""Configuration management for the web crawler."""

import os
from pathlib import Path
from typing import List, Optional, Pattern, Dict, Any

from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator, model_validator
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
    max_concurrent_requests: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of concurrent requests",
    )
    max_links_per_page: int = Field(
        default=50,
        ge=1,
        description="Maximum number of links to follow per page",
    )
    dedupe_mode: str = Field(
        default="skip",
        pattern=r"^(skip|force|if-modified)$",
        description="Deduplication mode: 'skip' to skip existing, 'force' to recrawl, 'if-modified' to check for changes",
    )
    cache_ttl: int = Field(
        default=3600,
        ge=0,
        description="Time-to-live for document cache in seconds",
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


class ElasticsearchSettings(BaseModel):
    """Elasticsearch configuration settings."""

    hosts: List[str] = Field(
        default_factory=lambda: ["http://localhost:9200"],
        description="List of Elasticsearch nodes to connect to"
    )
    index_prefix: str = Field(
        default="crawler_",
        description="Prefix to use for all indices created by the crawler"
    )
    username: Optional[str] = Field(
        default=None,
        description="Username for HTTP basic auth"
    )
    password: Optional[SecretStr] = Field(
        default=None,
        description="Password for HTTP basic auth"
    )
    use_ssl: bool = Field(
        default=False,
        description="Whether to use SSL/TLS for the connection"
    )
    verify_certs: bool = Field(
        default=False,
        description="Whether to verify SSL certificates"
    )
    ca_certs: Optional[Path] = Field(
        default=None,
        description="Path to CA certificate bundle"
    )
    bulk_size: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Number of documents to index in a single bulk request"
    )
    timeout: int = Field(
        default=30,
        ge=1,
        description="Timeout in seconds for Elasticsearch operations"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum number of retries for failed requests"
    )
    media_storage: Dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": True,
            "base_path": "./media",
            "max_size_mb": 10,
            "allowed_types": ["image/jpeg", "image/png", "image/gif", "video/mp4"]
        },
        description="Configuration for media file storage"
    )

    @field_validator('hosts')
    def validate_hosts(cls, v):
        """Ensure at least one host is provided."""
        if not v:
            raise ValueError("At least one Elasticsearch host must be provided")
        return v

    @field_validator('ca_certs', mode='before')
    def validate_ca_certs(cls, v):
        """Ensure CA certificate file exists if provided."""
        if v is not None:
            cert_path = Path(v)
            if not cert_path.exists():
                raise ValueError(f"CA certificate file not found: {v}")
            return cert_path
        return v

    def get_es_connection_params(self) -> Dict[str, Any]:
        """Get connection parameters for AsyncElasticsearch."""
        params = {
            "hosts": self.hosts,
            "use_ssl": self.use_ssl,
            "verify_certs": self.verify_certs,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }

        # Add authentication if provided
        if self.username and self.password:
            params["basic_auth"] = (self.username, self.password.get_secret_value())

        # Add CA certificate if provided
        if self.ca_certs:
            params["ca_certs"] = str(self.ca_certs)

        return params


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
    elasticsearch: ElasticsearchSettings = Field(
        default_factory=ElasticsearchSettings,
        description="Elasticsearch configuration",
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
