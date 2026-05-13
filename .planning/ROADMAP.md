# Roadmap: Enterprise Multi-Source Knowledge QA Agent (RAG-AGENT)

## Overview

Build an enterprise RAG system that ingests documents from multiple sources (DingTalk, Seafile, NAS, local files), processes them through a Chinese-optimized pipeline, and delivers accurate answers with source citations via a web interface. The journey starts with infrastructure foundations, builds the data ingestion pipeline end-to-end, adds multi-source connectors, constructs the hybrid retrieval engine, layers on anti-hallucination answer generation, exposes business services with RBAC, delivers the frontend, and caps with evaluation and monitoring.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation Infrastructure** - Storage schemas, FastAPI skeleton, Docker Compose, structured logging
- [ ] **Phase 2: Data Ingestion Pipeline** - Local connector, document parsers, Chinese chunking, embedding, dual-indexing
- [ ] **Phase 3: Multi-Source Connectors** - Seafile, NAS, DingTalk connectors with sync monitoring
- [ ] **Phase 4: RAG Engine** - Hybrid retrieval, RRF fusion, reranking, query understanding, project scoping
- [ ] **Phase 5: Generation and Anti-Hallucination** - vLLM deployment, CRAG pipeline, citation verification, streaming
- [ ] **Phase 6: Business Services and API** - JWT auth, RBAC, project management, admin APIs
- [ ] **Phase 7: Frontend** - Chat UI with SSE streaming, citation viewer, feedback, conversation history
- [ ] **Phase 8: Evaluation and Monitoring** - RAGAS pipeline, BadCase workflow, Grafana dashboards (v2 scope)

## Phase Details

### Phase 1: Foundation Infrastructure
**Goal**: All infrastructure services running with correct schemas, FastAPI skeleton alive, ready for feature development
**Mode**: mvp
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04
**Success Criteria** (what must be TRUE):
  1. `docker compose up` starts all services (PostgreSQL 17, Milvus 2.6, Elasticsearch 8.19, Redis 7, MinIO, FastAPI app) and health checks pass for each
  2. FastAPI application skeleton responds to `/health` endpoint with service connectivity status
  3. All services produce structured JSON logs with correlation ID tracking across requests
  4. Configuration loads correctly from environment variables and YAML files, supporting dev/test/prod profiles
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD
- [ ] 01-03: TBD

### Phase 2: Data Ingestion Pipeline
**Goal**: Documents flow from local files through parsing, Chinese-aware chunking, embedding, into dual-indexed storage (Milvus + Elasticsearch) with incremental sync and deduplication
**Mode**: mvp
**Depends on**: Phase 1
**Requirements**: CONN-01, CONN-05, CONN-06, PROC-01, PROC-02, PROC-03, PROC-04, PROC-05, PROC-06, PROC-07, PROC-08, RETR-01, RETR-02
**Success Criteria** (what must be TRUE):
  1. User configures a local directory and the system automatically detects file changes and triggers sync
  2. System parses PDF (including scanned OCR), Word, Excel, Markdown, and text files with correct structure preservation (tables, headings, code blocks)
  3. Chinese text is intelligently chunked with heading-aware coarse splitting and jieba word boundary protection, with strategy varying by document type
  4. Document chunks are embedded as 1024-dim vectors in Milvus and full-text indexed in Elasticsearch with ik_max_word Chinese tokenization
  5. Re-syncing processes only new/changed documents via timestamp and content hash, with cross-source SHA-256 deduplication
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD
- [ ] 02-03: TBD
- [ ] 02-04: TBD
- [ ] 02-05: TBD

### Phase 3: Multi-Source Connectors
**Goal**: Users can connect and sync documents from DingTalk, Seafile, and NAS, with visibility into sync status
**Mode**: mvp
**Depends on**: Phase 2
**Requirements**: CONN-02, CONN-03, CONN-04, CONN-07
**Success Criteria** (what must be TRUE):
  1. User configures a Seafile library connection and the system recursively syncs files from it
  2. User configures a NAS connection (NFS/SMB/WebDAV) and the system auto-syncs files
  3. User configures DingTalk knowledge base access (API or CLI mode) and system syncs document content
  4. Admin can view per-source sync status showing success/failure counts and last sync timestamps
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD
- [ ] 03-03: TBD

### Phase 4: RAG Engine
**Goal**: Hybrid retrieval pipeline delivers relevant, project-scoped results through BM25+vector fusion and cross-encoder reranking
**Mode**: mvp
**Depends on**: Phase 2 (indexes populated with real data)
**Requirements**: RETR-03, RETR-04, RETR-05, RETR-06, RETR-07, RETR-08
**Success Criteria** (what must be TRUE):
  1. A query triggers parallel Milvus vector search (Top-50) and Elasticsearch BM25 search (Top-50), with results fused via RRF algorithm
  2. bge-reranker-v2-m3 Cross-Encoder reorders fused results to Top-10 and filters items scoring below 0.3 relevance threshold
  3. Retrieval automatically scopes to a specific project_id via filter conditions on both Milvus and Elasticsearch
  4. Query understanding module classifies intent, rewrites questions for better retrieval, and extracts keywords
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD
- [ ] 04-03: TBD
- [ ] 04-04: TBD

### Phase 5: Generation and Anti-Hallucination
**Goal**: System generates accurate, cited answers with multi-layer anti-hallucination safeguards and real-time streaming
**Mode**: mvp
**Depends on**: Phase 4 (retrieval pipeline delivering ranked results)
**Requirements**: GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, GEN-06, GEN-07
**Success Criteria** (what must be TRUE):
  1. System generates answers where every factual claim cites a source document number [Source N], using Qwen2.5-72B via vLLM
  2. When knowledge base has no relevant content, system explicitly responds "no relevant information found based on available project materials"
  3. CRAG pipeline (LangGraph) routes queries, grades document relevance, and rewrites/retries retrieval when documents fail grading
  4. Post-generation citation verification checks every [Source N] against actual retrieved documents and strips false citations
  5. Answers stream to the client in real-time via SSE, with confidence score (below 0.6 triggers warning indicator)
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD
- [ ] 05-03: TBD
- [ ] 05-04: TBD

### Phase 6: Business Services and API
**Goal**: Users authenticate with role-based access, admins manage projects and data sources through typed API endpoints, and all data access is automatically scoped to authorized projects
**Mode**: mvp
**Depends on**: Phase 5 (generation pipeline ready for orchestration)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, UI-05, UI-06, UI-07
**Success Criteria** (what must be TRUE):
  1. User authenticates via JWT token and receives access scoped to their assigned roles and projects
  2. Admin can create/edit/delete projects and configure data sources through typed API endpoints
  3. Admin can assign and manage user roles across five RBAC levels (system admin, project admin, knowledge admin, user, read-only)
  4. All data queries are automatically scoped to the authenticated user's authorized projects via middleware-injected context
  5. Admin can trigger manual sync and view sync task status through API endpoints
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD
- [ ] 06-03: TBD

### Phase 7: Frontend
**Goal**: Users interact with the knowledge QA system through a polished web interface with real-time streaming, citation exploration, feedback, and conversation history
**Mode**: mvp
**Depends on**: Phase 6 (API endpoints available)
**Requirements**: UI-01, UI-02, UI-03, UI-04
**Success Criteria** (what must be TRUE):
  1. User asks questions via web chat UI and sees Markdown-rendered answers stream in real-time
  2. User clicks any [Source N] citation in an answer to view the source document fragment with title, section, author, and date
  3. User gives thumbs up/down feedback on any answer, and feedback is persisted for evaluation
  4. User views and navigates their conversation history across sessions
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD
- [ ] 07-03: TBD

### Phase 8: Evaluation and Monitoring
**Goal**: System quality is continuously measured and visualized through automated evaluation, BadCase management, and operational dashboards
**Mode**: mvp
**Depends on**: Phase 7 (full system operational for evaluation)
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04 (v2 scope)
**Success Criteria** (what must be TRUE):
  1. RAGAS pipeline runs automated evaluation (Faithfulness, Answer Relevancy, Context Precision, Context Recall) against a test question set
  2. BadCase management workflow supports collect-classify-analyze-optimize-verify cycle for systematic quality improvement
  3. Grafana dashboards display core metrics (accuracy, user satisfaction, query latency, index freshness) with system-level and project-level views
  4. Quality metrics are tracked over time and alert on degradation trends
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 08-01: TBD
- [ ] 08-02: TBD
- [ ] 08-03: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1, 2, 3, 4, 5, 6, 7, 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation Infrastructure | 0/? | Not started | - |
| 2. Data Ingestion Pipeline | 0/? | Not started | - |
| 3. Multi-Source Connectors | 0/? | Not started | - |
| 4. RAG Engine | 0/? | Not started | - |
| 5. Generation and Anti-Hallucination | 0/? | Not started | - |
| 6. Business Services and API | 0/? | Not started | - |
| 7. Frontend | 0/? | Not started | - |
| 8. Evaluation and Monitoring | 0/? | Not started | - |
