# 🕷️ Crawler

A high-performance, asynchronous web crawler designed for efficient data extraction and processing. This crawler efficiently extracts and processes web content with support for multiple output formats.

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- ⚡ Asynchronous crawling with configurable concurrency
- 🔍 Smart content extraction with trafilatura
- 🤖 Respects robots.txt and implements rate limiting
- 📦 Multiple output formats (JSONL, JSON, Parquet, CSV)
- 🛠️ Extensible architecture
- 📊 Progress tracking and logging

## 🚀 Installation

First, install [uv](https://github.com/astral-sh/uv) if you haven't already:

```bash
curl -sSf https://astral.sh/uv/install.sh | sh
```

Then, set up the project:

```bash
# Clone the repository
git clone https://github.com/wulfgang/crawler.git
cd crawler

# Install the package in development mode
make install

# Install development dependencies
make install-dev

# Install pre-commit hooks
make install-hooks
```

## 🏃‍♂️ Quick Start

### Basic Usage

```bash
# Crawl a single URL
crawler crawl https://example.com output/

# Crawl with depth and multiple workers
crawler crawl -d 2 -w 8 https://docs.example.com output/

# Use a configuration file
crawler --config config.yaml
```

### Elasticsearch Integration

Store crawled data directly in Elasticsearch:

```bash
# Basic usage with default Elasticsearch settings
crawler crawl https://example.com output/ --es-hosts http://localhost:9200

# With authentication and SSL
crawler crawl https://example.com output/ \
  --es-hosts https://elasticsearch:9200 \
  --es-username elastic \
  --es-password yourpassword \
  --es-use-ssl \
  --es-verify-certs

# With custom index prefix and bulk settings
crawler crawl https://example.com output/ \
  --es-hosts http://localhost:9200 \
  --es-index-prefix myapp_ \
  --es-bulk-size 2000 \
  --es-timeout 60
```

### Elasticsearch Management Commands

```bash
# List all indices with the configured prefix
crawler es list-indices --es-hosts http://localhost:9200

# Create a new index
crawler es create-index my_index --shards 2 --replicas 1

# Delete an index (with confirmation)
crawler es delete-index my_index

# Force delete without confirmation
crawler es delete-index my_index --force
```

### Configuration

#### YAML Configuration

Create a `config.yaml` file:

```yaml
# Required
start_url: https://example.com
output_dir: output/

# Optional
max_depth: 2
workers: 4
request_delay: 1.0  # seconds
output_format: jsonl  # jsonl, json, parquet, or csv
include_metadata: true
respect_robots_txt: true
user_agent: "Mozilla/5.0 (compatible; Crawler/1.0; +https://github.com/yourusername/crawler)"

# Elasticsearch Configuration
elasticsearch:
  hosts: ["http://localhost:9200"]
  index_prefix: "crawler_"
  username: "elastic"
  password: "yourpassword"
  use_ssl: false
  verify_certs: true
  ca_certs: "/path/to/ca.crt"
  bulk_size: 1000
  timeout: 30
  max_retries: 3
  media_storage:
    enabled: true
    base_path: "./media"
    max_size_mb: 10
    allowed_types: ["image/jpeg", "image/png", "image/gif", "video/mp4"]
```

#### Environment Variables

All settings can be configured via environment variables:

```bash
# Basic settings
START_URLS='["https://example.com"]'
OUTPUT__OUTPUT_DIR="output"
CRAWL__MAX_DEPTH=2
CRAWL__WORKERS=4

# Elasticsearch settings
ELASTICSEARCH__HOSTS='["http://localhost:9200"]'
ELASTICSEARCH__INDEX_PREFIX="crawler_"
ELASTICSEARCH__USERNAME="elastic"
ELASTICSEARCH__PASSWORD="yourpassword"
ELASTICSEARCH__USE_SSL="false"
ELASTICSEARCH__VERIFY_CERTS="true"
ELASTICSEARCH__CA_CERTS="/path/to/ca.crt"
ELASTICSEARCH__BULK_SIZE=1000
ELASTICSEARCH__TIMEOUT=30
ELASTICSEARCH__MAX_RETRIES=3

# Media storage settings
ELASTICSEARCH__MEDIA_STORAGE__ENABLED="true"
ELASTICSEARCH__MEDIA_STORAGE__BASE_PATH="./media"
ELASTICSEARCH__MEDIA_STORAGE__MAX_SIZE_MB=10
ELASTICSEARCH__MEDIA_STORAGE__ALLOWED_TYPES='["image/jpeg","image/png"]'
```

## 🛠 Development

### Common Tasks

```bash
# Install development dependencies
make install-dev

# Run linters
make lint

# Format code
make format

# Run tests
make test

# Run with coverage report
make test-cov

# Clean build artifacts
make clean
```

### Project Structure

```
crawler/
├── src/
│   └── crawler/
│       ├── __init__.py      # Package initialization and exports
│       ├── cli.py          # Command-line interface
│       ├── config.py       # Configuration management with Pydantic
│       ├── crawler.py      # Core crawling functionality
│       ├── extractor.py    # Content extraction utilities
│       ├── http_client.py  # Async HTTP client with rate limiting
│       └── version.py      # Package version information
├── .gitignore
├── .pre-commit-config.yaml
├── constraints.txt
├── Makefile
├── pyproject.toml          # Project metadata and dependencies
└── README.md
```

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [trafilatura](https://github.com/adbar/trafilatura) - Web scraping library
- [httpx](https://www.python-httpx.org/) - Async HTTP client
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
