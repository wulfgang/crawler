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
git clone https://github.com/yourusername/crawler.git
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
crawler https://example.com output/

# Crawl with depth and multiple workers
crawler -d 2 -w 8 https://docs.example.com output/

# Use a configuration file
crawler --config config.yaml
```

### Configuration

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
│       ├── __init__.py
│       ├── cli.py          # Command-line interface
│       ├── config.py       # Configuration management
│       ├── extractor.py    # Content extraction
│       ├── http_client.py  # Async HTTP client
│       └── storage.py      # Output storage handlers
├── tests/                  # Test files
├── .gitignore
├── .pre-commit-config.yaml
├── constraints.txt
├── Makefile
├── pyproject.toml
├── README.md
└── requirements-dev.in
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
