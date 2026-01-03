# Implementation Plan: Document Deduplication

**Feature Branch**: `002-document-dedupe`  
**Created**: 2026-01-03  
**Status**: Draft  
**Target Completion**: 2026-01-10

## 1. Technical Context

### 1.1 Current Architecture
- **Crawler**: Main crawling logic in [crawler.py](cci:7://file:///Users/gang.wang/code/crawler/src/crawler/crawler.py:0:0-0:0)
- **Storage**: Elasticsearch backend in [storage/elasticsearch.py](cci:7://file:///Users/gang.wang/code/crawler/src/crawler/storage/elasticsearch.py:0:0-0:0)
- **Configuration**: Settings in [config.py](cci:7://file:///Users/gang.wang/code/crawler/src/crawler/config.py:0:0-0:0)
- **CLI**: Command-line interface in [cli.py](cci:7://file:///Users/gang.wang/code/crawler/src/crawler/cli.py:0:0-0:0)

### 1.2 Performance Requirements
- O(1) lookup for document existence
- Sub-100ms overhead for duplicate checks
- Efficient memory usage for large-scale crawling

## 2. Implementation Phases

### Phase 0: Core Infrastructure (1 day)

#### 0.1 Document Structure Updates
- [ ] Add metadata fields to Elasticsearch mapping
- [ ] Implement content fingerprinting using SHA-256
- [ ] Add HTTP header caching support

```python
# In storage/elasticsearch.py
DOCUMENT_MAPPING = {
    "properties": {
        "fingerprint": {"type": "keyword"},
        "crawl_metadata": {
            "properties": {
                "status": {"type": "keyword"},
                "attempts": {"type": "integer"},
                "last_crawled": {"type": "date"},
                "etag": {"type": "keyword"},
                "last_modified": {"type": "keyword"},
                "next_crawl": {"type": "date"}
            }
        }
    }
}