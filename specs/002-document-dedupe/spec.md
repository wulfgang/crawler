# Document Deduplication for Web Crawler

**Feature Branch**: `002-document-dedupe`  
**Created**: 2026-01-03  
**Status**: Draft  
**Input**: "Implement document deduplication to optimize crawling by checking existing pages before download"

## User Scenarios & Testing

### User Story 1 - Skip Existing Documents (Priority: P1)

As a user, I want to skip crawling of previously processed URLs to save bandwidth and processing time.

**Why this priority**: Reduces server load and improves crawl efficiency.

**Independent Test**: Verify that already crawled URLs are skipped during subsequent runs.

**Acceptance Scenarios**:
1. **Given** a URL that was previously crawled, **When** running the crawler in skip mode, **Then** the URL is skipped.
2. **Given** a new URL, **When** running the crawler, **Then** the URL is processed normally.

---

### User Story 2 - Force Recrawl (Priority: P2)

As a user, I want to force recrawl of URLs even if they exist in the index.

**Why this priority**: Ensures content freshness when needed.

**Independent Test**: Verify that URLs are recrawled even when they exist.

**Acceptance Scenarios**:
1. **Given** a previously crawled URL, **When** running with --dedupe=force, **Then** the URL is recrawled.
2. **Given** a failed crawl, **When** running with --dedupe=force, **Then** the URL is retried.

---

## Functional Requirements

### 1. Document Structure Updates
- Add fingerprint field for content-based deduplication
- Add crawl metadata (status, timestamps, attempts)
- Store HTTP headers (ETag, Last-Modified)

### 2. Deduplication Modes
- `skip`: Skip existing documents (default)
- `force`: Always recrawl
- `if-modified`: Recrawl only if modified

### 3. Performance
- Implement bulk operations for metadata updates
- Cache frequently accessed document statuses
- Add rate limiting to prevent ES overload

## Success Criteria

1. **Performance**:
   - 95% reduction in redundant downloads
   - Sub-100ms overhead for duplicate checks

2. **Reliability**:
   - 99.9% accurate duplicate detection
   - Graceful handling of network errors

3. **Usability**:
   - Clear CLI documentation
   - Informative logging of deduplication decisions

## Key Entities

### Document Metadata
```python
{
    "url": "string",
    "fingerprint": "string",
    "crawl_metadata": {
        "status": "success|failed|pending",
        "attempts": "number",
        "last_crawled": "ISO8601",
        "etag": "string",
        "last_modified": "string"
    }
}