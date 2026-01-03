# Document Deduplication - Implementation Tasks

## Dependencies
- [ ] Complete Elasticsearch storage implementation (001-es-storage)
- [ ] Verify Elasticsearch cluster is accessible
- [ ] Configure proper index mappings

## Phase 1: Core Infrastructure Setup

### 1.1 Document Structure Updates
- [ ] T001 Update Elasticsearch mapping in `src/crawler/storage/elasticsearch.py`
- [ ] T002 Implement content fingerprinting using SHA-256
- [ ] T003 Add HTTP header caching support

### 1.2 Configuration
- [ ] T004 Add deduplication settings to `src/crawler/config.py`
- [ ] T005 Add CLI arguments for deduplication in `src/crawler/cli.py`

## Phase 2: Core Implementation

### 2.1 Document Storage
- [ ] T006 [US1] Implement `document_exists()` in `elasticsearch.py`
- [ ] T007 [US1] Add `get_document_metadata()` with field filtering
- [ ] T008 [US1] Implement `update_document_metadata()` for atomic updates

### 2.2 Deduplication Logic
- [ ] T009 [US1] Implement `should_recrawl()` with mode support
- [ ] T010 [US1] Add content fingerprinting to document storage
- [ ] T011 [US1] Implement HTTP header handling for conditional requests

## Phase 3: Caching Layer

### 3.1 In-Memory Cache
- [ ] T012 [P] Implement `DocumentCache` class in `src/crawler/cache.py`
- [ ] T013 [P] Add LRU eviction policy
- [ ] T014 [P] Implement TTL-based invalidation

### 3.2 Cache Integration
- [ ] T015 Integrate cache with storage layer
- [ ] T016 Add cache statistics collection
- [ ] T017 Implement cache warming on startup

## Phase 4: Crawler Integration

### 4.1 Core Integration
- [ ] T018 [US1] Modify `Crawler._process_url()` to check for duplicates
- [ ] T019 [US1] Add deduplication statistics tracking
- [ ] T020 [US1] Implement bulk URL checking

### 4.2 Performance Optimizations
- [ ] T021 [P] Implement connection pooling for ES
- [ ] T022 [P] Add request batching for metadata updates
- [ ] T023 [P] Optimize bulk document checks

## Phase 5: Testing & Validation

### 5.1 Unit Tests
- [ ] T024 Add tests for `DocumentCache` class
- [ ] T025 Test deduplication logic
- [ ] T026 Verify cache eviction policies

### 5.2 Integration Tests
- [ ] T027 Test end-to-end crawling with deduplication
- [ ] T028 Verify different deduplication modes
- [ ] T029 Test error handling and recovery

## Phase 6: Documentation & Monitoring

### 6.1 Documentation
- [ ] T030 Update README with deduplication features
- [ ] T031 Add CLI usage examples
- [ ] T032 Document configuration options

### 6.2 Monitoring
- [ ] T033 Add metrics collection for deduplication
- [ ] T034 Implement logging for deduplication events
- [ ] T035 Add Prometheus metrics endpoint

## Parallel Execution Examples

### Story US1: Skip Existing Documents
```bash
# Terminal 1
python -m crawler crawl --dedupe skip --urls [https://example.com](https://example.com)

# Terminal 2 (can run in parallel)
python -m crawler crawl --dedupe force --urls [https://example.com](https://example.com)