<!-- GSD:project-start source:PROJECT.md -->
## Project

**企业多源项目知识问答Agent (RAG-AGENT)**

基于RAG架构的企业级知识问答系统，整合钉钉知识库、Seafile、NAS、本地文件等多数据源项目材料，通过自然语言交互为项目成员提供精准、可追溯的知识问答服务。面向公司内部50-200人的项目团队。

**Core Value:** 答案精准度 — 确保回答基于真实项目材料，目标准确率 >= 90%，幻觉率 <= 5%，每个回答附带来源引用。

### Constraints

- **部署方式**: 全链路私有化部署，数据不出域
- **GPU资源**: LLM推理需4xA100 80GB（或初期用API替代）
- **响应时间**: P95 <= 5秒
- **并发用户**: >= 50
- **知识库更新延迟**: <= 30分钟
- **文档格式**: PDF/Word/Excel/PPT/Markdown/图片
- **钉钉接入**: 可能无企业API权限，需支持CLI替代方案
- **中文优先**: 分块、检索、生成均需针对中文优化
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Framework (Backend)
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11+ | Runtime | AI/ML ecosystem compatibility, performance sweet spot (3.12+ has some library compat issues) |
| FastAPI | 0.136.x | Web framework | Async-native, OpenAPI auto-docs, Pydantic v2 integration, WebSocket support. Confirmed: HIGH confidence (PyPI verified) |
| Pydantic | 2.13.x | Data validation | V2 is 5-50x faster than v1, tight FastAPI integration |
| SQLAlchemy | 2.0.x | ORM | Mature, async support, Pythonic query API |
| Alembic | 1.18.x | DB migrations | SQLAlchemy companion, production-proven |
| uvicorn | 0.34+ | ASGI server | FastAPI standard, uvloop for performance |
| PyJWT | 2.12.x | JWT auth | Standard JWT handling for API auth |
| python-multipart | 0.0.28 | File uploads | FastAPI file upload support |
### Core Framework (Frontend)
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| React | 19.x | UI library | Latest stable, concurrent features, Server Components |
| Next.js | 15.x | Framework | App Router, SSR/SSG, streaming support |
| TypeScript | 5.x | Type safety | Industry standard |
| Tailwind CSS | 4.x | Styling | Utility-first, fast iteration |
| shadcn/ui | latest | Component library | Composable, accessible, not a dependency |
### Database & Storage
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | 17.x | Primary RDBMS | pgvector extension available as fallback, JSONB, mature. 17 is latest stable (May 2026). Confirmed: HIGH confidence |
| pgvector | 0.4.2 | Vector extension for PG | Backup/complement to Milvus for small-scale vector ops |
| Elasticsearch | 8.19.x | Full-text search (BM25) | BM25 maturity, ik_analyzer Chinese tokenization, aggregation power. **Stick with 8.x, NOT 9.x** -- ES 9.x just released and has breaking changes + fewer Chinese analyzer plugins confirmed working. Confirmed: HIGH confidence (PyPI shows 9.4.0 but 8.19.x is stable and proven) |
| Milvus | 2.6.x | Vector database | Built-in BM25 sparse vectors (confirmed from docs), HNSW, partition key, hybrid search. Latest stable: 2.6.15. Confirmed: HIGH confidence (GitHub verified) |
| PyMilvus | 3.0.0 | Milvus Python SDK | Matches Milvus 2.6+ server, hybrid search API. Confirmed: HIGH confidence (PyPI verified) |
| Redis | 7.x | Cache + message queue | Streams for task queue, caching, session store. Proven and lightweight |
| MinIO | latest stable | Object storage | S3-compatible, self-hosted, stores raw documents and parsed results |
### LLM & AI Models
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Qwen2.5-72B-Instruct | latest | Answer generation LLM | Best open Chinese LLM at this size, strong reasoning, private deployment. **Note:** vLLM focus has shifted to Qwen3/Qwen3.5 but Qwen2.5 remains fully supported. Confirmed: HIGH confidence |
| vLLM | 0.20.x | LLM inference engine | PagedAttention, continuous batching, OpenAI-compatible API. Latest: 0.20.2. Confirmed: HIGH confidence (GitHub verified) |
| bge-large-zh-v1.5 | v1.1 | Text embedding (1024-dim) | Best-in-class Chinese embedding, open-source, proven in production. Part of FlagEmbedding 1.4.0. Confirmed: HIGH confidence (FlagEmbedding 1.4.0 on PyPI, model from v1.1 tag) |
| bge-reranker-v2-m3 | v1.3+ | Reranking model | Cross-encoder for Chinese+multilingual, open-source, high accuracy. Part of FlagEmbedding 1.4.0. Confirmed: HIGH confidence |
| FlagEmbedding | 1.4.0 | Embedding/Rerank SDK | BAAI official library, includes bge-large-zh, bge-reranker, and new BGE-Reasoner. Confirmed: HIGH confidence (PyPI verified) |
### Document Processing
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| MinerU (magic-pdf) | 1.3.12 | PDF deep parsing | Best Chinese PDF parser, table extraction, layout analysis, CUDA acceleration. Confirmed: HIGH confidence (PyPI verified) |
| PaddleOCR | 3.5.0 | OCR engine | Best Chinese OCR accuracy (94.5% on OmniDocBench), PP-OCRv5, 109 languages. Confirmed: HIGH confidence (PyPI verified) |
| Unstructured | 0.22.28 | Multi-format doc parsing | Table-aware chunking, formula markdown, DOCX/PPTX/XLSX support. Confirmed: HIGH confidence (PyPI verified) |
| python-docx | 1.2.0 | Word (.docx) parsing | Direct DOCX structure extraction, heading hierarchy |
| openpyxl | 3.1.5 | Excel (.xlsx) parsing | Sheet-by-sheet processing, cell formatting |
| python-pptx | 1.0.2 | PowerPoint (.pptx) parsing | Slide text + notes + tables extraction |
| pandas | 3.0.x | Tabular data processing | Excel-to-text conversion, data cleaning |
| jieba | 0.42.1 | Chinese word segmentation | Standard Chinese tokenizer for BM25 indexing, query processing. Confirmed: HIGH confidence (de facto standard, stable) |
### RAG Pipeline Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| LlamaIndex | 0.14.x | RAG data framework | Document loaders, index abstractions, retrieval composability. Use selectively for data connectors, NOT as full framework. Confirmed: HIGH confidence (PyPI: 0.14.21) |
| LangGraph | 1.2.0 | Agent workflow orchestration | Stateful graph-based workflows for V2 Agentic search. Use for complex multi-step retrieval. Confirmed: HIGH confidence (PyPI verified) |
### Task Queue & Scheduling
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Celery | 5.6.x | Async task execution | Battle-tested, Redis broker, retry logic, monitoring. Latest: 5.6.3. Confirmed: HIGH confidence (PyPI verified) |
| Redis Streams | (via Redis 7.x) | Message queue for doc sync | Lightweight, already using Redis, good for ordered task processing |
### Data Source Connectors
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| httpx | 0.28.x | HTTP client | Async-capable, modern replacement for requests |
| watchdog | 6.0.0 | File system monitoring | Real-time file change detection for local/NAS directories |
| pysmb | 1.2.14 | SMB/CIFS protocol | Pure Python SMB access for NAS, cross-platform |
| dingtalk-workspace-cli | latest | DingTalk KB access (no API) | Official CLI tool for scenarios without enterprise API permissions |
### Evaluation & Monitoring
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| RAGAS | 0.4.x | RAG evaluation framework | Faithfulness, Answer Relevancy, Context metrics. Latest: 0.4.3. Confirmed: HIGH confidence (PyPI verified) |
| Prometheus | 3.x | Metrics collection | Industry standard for application metrics |
| Grafana | 12.x | Dashboards | Visualization for metrics, alerting |
### Infrastructure
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Docker | 27.x | Containerization | Standard container runtime |
| Docker Compose | 2.x | Container orchestration | Simple multi-service deployment, migration path to K8s later |
| psycopg | 3.3.x | PostgreSQL driver | Async-capable, modern PG driver (replaces psycopg2) |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | 9.1.x | Retry logic | API calls, network operations, transient failures |
| PyYAML | 6.0.x | Configuration files | YAML config loading |
| sse-starlette | 3.4.x | Server-Sent Events | Streaming LLM responses to frontend |
| structlog | latest | Structured logging | JSON logs for production, correlation IDs |
## Alternatives Considered
| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Web framework | FastAPI | Django | Django is heavier, less async-native, slower for API-only services |
| Web framework | FastAPI | Flask | No native async, no auto OpenAPI docs, less modern |
| Vector DB | Milvus 2.6 | Qdrant | Qdrant simpler but Milvus has built-in BM25 sparse vectors, better for hybrid search |
| Vector DB | Milvus 2.6 | pgvector-only | pgvector lacks HNSW tuning, partition key, distributed scaling. Use only as supplement |
| Vector DB | Milvus 2.6 | Weaviate | More resource-heavy, less flexible hybrid search control |
| Full-text search | Elasticsearch 8.19 | OpenSearch | Fork is fine but ES has broader Chinese analyzer ecosystem (ik_max_word) |
| Full-text search | Elasticsearch 8.19 | ES 9.x | Too new (released mid-2026), Chinese analyzer plugins not yet confirmed, breaking changes |
| Full-text search | Elasticsearch 8.19 | Milvus BM25 only | ES BM25 is more mature for Chinese, ik_analyzer battle-tested. Use Milvus BM25 as complement |
| LLM | Qwen2.5-72B | DeepSeek-V3 | DeepSeek requires 8xA100 (671B MoE), heavier deployment |
| LLM | Qwen2.5-72B | Qwen3-72B | Qwen3 exists but Qwen2.5 is proven and well-documented for RAG use cases |
| Embedding | bge-large-zh-v1.5 | GTE-large-zh | Comparable quality but bge has larger community and FlagEmbedding SDK |
| Embedding | bge-large-zh-v1.5 | bge-m3 | bge-m3 is multilingual, slightly less optimized for pure Chinese |
| OCR | PaddleOCR 3.5 | Tesseract | Tesseract Chinese accuracy significantly lower |
| PDF parsing | MinerU 1.3 | Doc2X | Doc2X is commercial/limited, MinerU is open-source with excellent Chinese support |
| Task queue | Celery 5.6 | Redis Streams only | Redis Streams lacks retry logic, dead letter queues, task monitoring |
| Task queue | Celery 5.6 | Dramatiq | Smaller community, fewer integrations |
| Task queue | Celery 5.6 | ARQ | Too lightweight for enterprise use, less mature |
| RAG framework | Custom pipeline | Dify (as platform) | Black box retrieval, hard to control precision (our #1 priority) |
| RAG framework | Custom pipeline | RAGFlow (as platform) | GPU-heavy, deployment complexity, but borrow their parsing ideas |
| RAG framework | Custom + LlamaIndex utils | Full LlamaIndex | Framework abstractions leak, debugging is painful, custom gives better control |
| Monitoring | Prometheus + Grafana | Zabbix | Zabbix is old-school agent-based, Prometheus is cloud-native standard |
## Installation
# Core backend
# Auth & utilities
# Vector database & search
# AI models
# Document processing
# RAG utilities (selective use)
# Evaluation
# File monitoring
# Frontend (separate project)
## Key Architecture Decisions
### 1. Elasticsearch 8.x (NOT 9.x) for BM25
### 2. Custom Retrieval Pipeline (NOT full RAG framework)
- BM25 retrieval: direct Elasticsearch client calls with jieba tokenization
- Vector retrieval: direct PyMilvus calls with bge-large-zh embeddings
- RRF fusion: simple Python implementation (sum(1/(k+rank_i)))
- Rerank: FlagEmbedding reranker inference
### 3. Celery over Redis-Streams-only
### 4. MinerU + Unstructured (NOT either/or)
- **MinerU**: Best for PDF (especially Chinese), table extraction, layout analysis
- **Unstructured**: Best for DOCX/PPTX structure extraction, table-aware chunking
- Use MinerU as primary PDF parser, Unstructured for Office formats and chunking
- PaddleOCR handles scanned PDFs and images
### 5. Milvus Hybrid Search (Sparse + Dense)
- Dense vectors (bge-large-zh): semantic similarity
- Sparse vectors (BM25): keyword matching
- Both stored in Milvus, searched together with hybrid search API
- Complex aggregation queries
- Proven Chinese analyzer ecosystem (ik_max_word)
- Faceted search and filtering
- Operational familiarity
## Version Stability Notes
| Component | Risk Level | Notes |
|-----------|-----------|-------|
| FastAPI 0.136 | LOW | Rapid release cycle but stable API surface |
| Pydantic 2.13 | LOW | V2 is stable and well-documented |
| Milvus 2.6 | LOW | Latest stable, 2.6.15, well-tested |
| PyMilvus 3.0 | MEDIUM | Major version bump, verify hybrid search API compat |
| LlamaIndex 0.14 | MEDIUM | Frequent breaking changes, pin version |
| vLLM 0.20 | LOW | Stable for Qwen2.5, but verify Qwen2.5 support hasn't been deprecated |
| Elasticsearch 8.19 | LOW | Mature 8.x line, security patches only |
| LangGraph 1.2 | LOW | 1.x stable API since Jan 2025 |
## Sources
- Milvus releases: https://github.com/milvus-io/milvus/releases (verified 2.6.15 latest stable)
- vLLM releases: https://github.com/vllm-project/vllm/releases (verified 0.20.2 latest)
- MinerU releases: https://github.com/opendatalab/MinerU/releases (verified 1.3.12 latest, named magic-pdf on PyPI)
- PaddleOCR releases: https://github.com/PaddlePaddle/PaddleOCR/releases (verified 3.5.0 latest)
- FastAPI releases: https://github.com/fastapi/fastapi/releases (verified 0.136.1 latest)
- FlagEmbedding releases: https://github.com/FlagOpen/FlagEmbedding/releases (verified 1.4.0, bge-large-zh from v1.1)
- Unstructured releases: https://github.com/unstructured-io/unstructured/releases (verified 0.22.28)
- Celery releases: https://github.com/celery/celery/releases (verified 5.6.3)
- Elasticsearch releases: https://github.com/elastic/elasticsearch/releases (verified 9.4.1 latest, 8.19.x stable line)
- MinIO releases: https://github.com/minio/minio/releases (verified RELEASE.2025-10-15)
- Milvus 2.6 hybrid search docs: Context7 verified BM25BuiltInFunction and hybrid search API
- PyPI package indexes: All Python package versions verified via pip index
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
