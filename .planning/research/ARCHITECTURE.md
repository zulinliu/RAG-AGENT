# Architecture Patterns

**Domain:** Enterprise Multi-Source Knowledge QA Agent (RAG System)
**Researched:** 2026-05-13

## Recommended Architecture

The system uses a **six-layer pipeline architecture** with clear directional data flow and strict component boundaries. Each layer owns its data and exposes a narrow API to the layer above. The architecture is intentionally monolithic-deployable (single Docker Compose) but modular in code, enabling future migration to microservices without rewriting internals.

```
                     USER FLOW (top-down query)                 DATA FLOW (bottom-up ingestion)

  ┌──────────────────────────────────────────────┐
  │           6. Frontend Layer                   │
  │    React/Next.js Web UI + Admin Dashboard    │
  └──────────────────┬───────────────────────────┘
                     │ HTTP/WebSocket/SSE
  ┌──────────────────▼───────────────────────────┐
  │           5. API Gateway Layer                │
  │    FastAPI + Auth Middleware + Rate Limiting  │
  └──────────────────┬───────────────────────────┘
                     │ Internal function calls
  ┌──────────────────▼───────────────────────────┐
  │        4. Business Services Layer             │
  │  User / Project / Knowledge / QA / Evaluate  │
  └──────────────────┬───────────────────────────┘
                     │
  ┌──────────────────▼───────────────────────────┐
  │          3. RAG Engine Layer                  │
  │  Query Understanding → Multi-Route Retrieval │
  │  → RRF Fusion → Rerank → Generate → Verify  │
  └──────────────────┬───────────────────────────┘
                     │
  ┌──────────────────▼───────────────────────────┐
  │      2. Document Processing Pipeline          │
  │  Download → Parse → Clean → Chunk → Embed    │
  │  → Index (Milvus + Elasticsearch)            │
  └──────────────────▲───────────────────────────┘
                     │
  ┌──────────────────┴───────────────────────────┐
  │     1. Data Source Connectors Layer           │
  │  DingTalk / Seafile / NAS / Local FileSystem │
  └──────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Communicates With | Technology |
|-----------|---------------|-------------------|------------|
| **Data Source Connectors** | Discover, authenticate, download documents from external systems | Document Processing Pipeline (via Redis Streams tasks) | Python (pysmb, watchdog, httpx) |
| **Document Processing Pipeline** | Parse raw files into structured chunks with metadata; generate embeddings; write to indexes | Connectors (receives tasks), Milvus + ES (writes), PostgreSQL (metadata), MinIO (raw files) | MinerU, Unstructured, PaddleOCR, bge-large-zh |
| **RAG Engine** | End-to-end query processing: understand, retrieve, rerank, generate, verify | Milvus + ES (reads), vLLM (generation), bge-reranker (scoring) | LlamaIndex (data layer), LangGraph (workflow orchestration) |
| **Business Services** | Domain logic: users, projects, RBAC, sessions, feedback, evaluation | PostgreSQL (reads/writes), Redis (cache), RAG Engine (invokes) | FastAPI services |
| **API Gateway** | Request routing, authentication, rate limiting, SSE streaming | Business Services (delegates) | FastAPI + middleware |
| **Frontend** | User interaction: chat UI, admin dashboard, feedback collection | API Gateway (HTTP/WS) | React + Next.js |

### Data Flow

**Ingestion flow (bottom-up, asynchronous):**

1. Connectors detect new/changed documents via polling (15-min intervals) or filesystem events (watchdog)
2. Connector publishes a sync task to Redis Streams with document metadata (source, path, project_id)
3. Document Processing Worker consumes the task, downloads the file to MinIO
4. Worker selects parser by MIME type, extracts structured text + metadata
5. Chinese-aware chunking engine splits into 500-1000 char blocks with 100-200 char overlap
6. Embedding service (bge-large-zh-v1.5) converts chunks to 1024-dim vectors
7. Dual-write: vectors + metadata to Milvus collection, full-text to Elasticsearch index
8. PostgreSQL records document metadata, sync status, and chunk lineage

**Query flow (top-down, synchronous):**

1. User submits question via Web UI or DingTalk bot
2. API Gateway authenticates, resolves user's project permissions, forwards to QA Service
3. RAG Engine processes the query through a LangGraph state machine:
   - **Query Understanding node**: intent classification, question rewrite, keyword extraction
   - **Routing decision**: LLM determines if retrieval is needed or can answer directly
   - **Retrieve node**: parallel BM25 (ES) + vector (Milvus) search with project_id filter
   - **Grade Documents node**: binary relevance assessment per retrieved chunk
   - **Rewrite loop** (if documents fail grading): reformulate query and re-retrieve
   - **Rerank node**: bge-reranker-v2-m3 Cross-Encoder scores top candidates
   - **Generate node**: Qwen2.5-72B produces answer with forced citations
   - **Verify node**: citation existence check, faithfulness scoring
4. Response streams back via SSE with citations, confidence score, and source metadata
5. User feedback (thumbs up/down) captured and stored for evaluation pipeline

## Patterns to Follow

### Pattern 1: LangGraph State Machine for RAG Pipeline

**What:** Model the entire retrieval-generation pipeline as a directed graph where each node is a processing step and edges are conditional transitions. This is the Corrective RAG (CRAG) pattern.

**When:** The RAG Engine layer -- the core query processing pipeline.

**Why:** Unifies routing, retrieval, grading, correction, and generation into a single auditable workflow. Enables self-correction loops (rewrite + re-retrieve) when initial retrieval fails. LangGraph provides built-in state persistence and streaming.

**Example structure:**

```
START
  → generate_query_or_respond (LLM decides: retrieve or answer directly)
    → retrieve (parallel BM25 + vector via Milvus hybrid_search)
      → grade_documents (binary relevance per chunk)
        → [all irrelevant?] → rewrite_question → loop back to retrieve
        → [some relevant?] → rerank → generate_answer → verify_citations → END
    → [no retrieval needed] → END (direct response)
```

**Key insight from LangGraph agentic RAG docs:** The LLM itself acts as the router. By binding the retriever as a tool via `.bind_tools()`, the LLM decides whether to invoke retrieval or respond directly. This eliminates a separate intent classification component and simplifies the graph.

**Confidence:** HIGH (verified against LangGraph official documentation)

### Pattern 2: Milvus 2.6 Native Hybrid Search (BM25 + Dense Vector)

**What:** Milvus 2.6 supports native BM25 full-text search alongside dense vector search within a single collection, using `hybrid_search()` with `RRFRanker()`.

**When:** Document indexing and retrieval in the RAG Engine.

**Why:** Eliminates the need for a separate Elasticsearch instance for BM25 in many cases. Milvus 2.6 can handle both dense vectors and sparse BM25 vectors in one collection with built-in RRF fusion.

**However:** The project spec requires Elasticsearch 8.x for mature Chinese tokenization (ik_max_word analyzer). Milvus BM25 uses a standard analyzer which may not match ik_max_word quality for Chinese text. **Recommendation: use both Milvus for vector search and Elasticsearch for BM25 with Chinese tokenization, with external RRF fusion.** This gives the best Chinese retrieval quality while keeping the option to consolidate later if Milvus BM25 Chinese support improves.

**Example (Milvus 2.6 native hybrid if Chinese tokenization is adequate):**

```python
from pymilvus import MilvusClient, DataType, Function, FunctionType, AnnSearchRequest, RRFRanker

schema = client.create_schema(auto_id=True)
schema.add_field("text", DataType.VARCHAR, max_length=2048,
                 enable_analyzer=True, analyzer_params={"type": "standard"})
schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=1024)

bm25_function = Function(
    name="text_bm25",
    input_field_names=["text"],
    output_field_names=["sparse_vector"],
    function_type=FunctionType.BM25,
)
schema.add_function(bm25_function)

# Hybrid search
dense_req = AnnSearchRequest(data=[query_embedding], anns_field="dense_vector",
                              param={"metric_type": "COSINE"}, limit=50)
sparse_req = AnnSearchRequest(data=[query_text], anns_field="sparse_vector",
                               param={"metric_type": "BM25"}, limit=50)
results = client.hybrid_search(collection_name="docs", reqs=[dense_req, sparse_req],
                                ranker=RRFRanker(), limit=10)
```

**Confidence:** HIGH (verified against Milvus 2.6 official documentation via Context7)

### Pattern 3: Multi-Layer Anti-Hallucination Architecture

**What:** A defense-in-depth approach with five distinct layers that each independently reduce hallucination risk.

**When:** The entire RAG pipeline, from retrieval through generation to post-processing.

**Layers:**

1. **Retrieval quality layer**: Hybrid BM25+vector retrieval with RRF fusion ensures high recall (target 85%+). Reranker with threshold filtering (score < 0.3 rejected) ensures precision. This prevents irrelevant context from reaching the generator.

2. **Context gating layer**: Document grading node in the LangGraph pipeline performs binary relevance assessment. If no documents pass grading, the query is rewritten and retrieval is retried (up to 2 iterations). This creates a Corrective RAG loop.

3. **Generation constraint layer**: System prompt enforces three rules: (a) only use provided context, (b) cite source number for every factual claim, (c) explicitly say "I don't know" when context is insufficient. Temperature set low (0.1-0.3) to reduce creative generation.

4. **Post-verification layer**: Citation verification checks that every `[Source N]` reference in the answer maps to an actual retrieved chunk. Faithfulness scoring using RAGAS Faithfulness metric. Low-confidence answers (score < 0.6) get a visible warning banner.

5. **Continuous evaluation layer**: RAGAS metrics (Faithfulness, Answer Relevancy, Context Precision, Context Recall) run weekly on a held-out test set. User feedback (thumbs up/down) feeds a BadCase pipeline for manual review and systematic improvement.

**RAGAS metrics for evaluation (verified against official docs):**

```python
from ragas.metrics.collections import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall

# Each metric requires an LLM for evaluation
faithfulness = Faithfulness(llm=eval_llm)           # Score 0-1: answer vs context consistency
answer_relevancy = AnswerRelevancy(llm=eval_llm, embeddings=embeddings)  # Answer vs question relevance
context_precision = ContextPrecision(llm=eval_llm)   # Retrieved docs ranking quality
context_recall = ContextRecall(llm=eval_llm)         # Retrieved docs coverage
```

**Confidence:** HIGH (RAGAS metrics verified via Context7; CRAG pattern verified against LangGraph official docs)

### Pattern 4: LlamaIndex IngestionPipeline for Document Processing

**What:** Use LlamaIndex's `IngestionPipeline` to orchestrate the document processing steps as a sequence of transformations (parse, split, embed, metadata extract).

**When:** The Document Processing Pipeline layer.

**Why:** LlamaIndex provides battle-tested transformations for document loading, node parsing (chunking), embedding generation, and metadata extraction. The pipeline handles caching, parallelism (`num_workers`), and deduplication automatically.

**Example:**

```python
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter

pipeline = IngestionPipeline(
    transformations=[
        # Custom Chinese-aware parser (MinerU + Unstructured)
        ChineseDocumentParser(),
        # Custom structure-aware chunker
        ChineseStructureAwareChunker(chunk_size=800, chunk_overlap=150),
        # Metadata extraction
        MetadataExtractor(),
        # Embedding generation
        embedding_model,  # bge-large-zh-v1.5
    ],
    vector_store=milvus_vector_store,
)
nodes = pipeline.run(documents=documents, num_workers=4)
```

**Note:** The custom Chinese chunker must be implemented because LlamaIndex's built-in splitters do not handle Chinese sentence boundaries well. Use jieba for word segmentation at chunk boundaries.

**Confidence:** HIGH (verified against LlamaIndex official documentation via Context7)

### Pattern 5: Project-Level Data Isolation via Partition Key

**What:** Use Milvus Partition Key on `project_id` to physically separate data by project while maintaining a single collection.

**When:** Milvus collection schema design.

**Why:** Partition Key provides automatic data routing and filtering. Queries with `project_id` filter only scan the relevant partition, achieving project isolation without managing multiple collections.

**Implementation:**

```python
schema.add_field("project_id", DataType.VARCHAR, max_length=64, is_partition_key=True)
# All queries automatically filter by project_id
results = client.search(collection_name="docs", data=[query_vec],
                        filter='project_id == "proj_001"',
                        limit=10)
```

**Elasticsearch equivalent:** Use index aliases per project or `project_id` field filtering with routing.

**PostgreSQL equivalent:** All business tables include `project_id` column; queries use Row-Level Security policies or application-level filtering.

**Confidence:** HIGH (standard Milvus pattern verified in official docs)

### Pattern 6: Redis Streams for Async Document Sync Tasks

**What:** Use Redis Streams as a lightweight message queue for document synchronization tasks. Each Connector publishes tasks; Worker processes consume and execute.

**When:** Data Source Connectors and Document Processing Pipeline communication.

**Why:** Redis Streams is simpler than Kafka/RabbitMQ for this workload (thousands of tasks/day, not millions). Already required for caching, so no additional infrastructure. Supports consumer groups for horizontal scaling of document processing workers.

**Flow:**

```
Connector → XADD sync_tasks {source: "seafile", file_path: "...", project_id: "proj_001"}
Worker    → XREADGROUP GROUP doc_workers consumer-1 COUNT 1 BLOCK 5000 STREAMS sync_tasks >
Worker    → Process document → XACK sync_tasks doc_workers <entry_id>
```

**Confidence:** HIGH (standard Redis pattern, specified in project requirements)

## Anti-Patterns to Avoid

### Anti-Pattern 1: Monolithic Retrieval Without Grading

**What:** Retrieve documents once, pass all of them directly to the LLM for generation.

**Why bad:** Low-quality or irrelevant retrieved documents pollute the context, causing the LLM to hallucinate or produce contradictory answers. This is the single biggest source of hallucination in RAG systems.

**Instead:** Use the Corrective RAG pattern -- grade documents after retrieval, reject irrelevant ones, and loop back with a rewritten query if too few pass grading.

### Anti-Pattern 2: Single-Path Retrieval

**What:** Use only vector similarity search or only BM25 keyword search.

**Why bad:** Vector search misses exact keyword matches (critical for Chinese technical terms, project codes). BM25 misses semantic matches (paraphrased queries). Each alone achieves 60-70% recall; combined they reach 85%+.

**Instead:** Always run parallel BM25 + vector retrieval with RRF fusion.

### Anti-Pattern 3: Fixed Chunk Size Without Structure Awareness

**What:** Split documents at exactly N characters regardless of document structure.

**Why bad:** Cuts sentences, breaks table rows, splits code blocks mid-function. Creates chunks with incomplete context that produce poor retrieval results and confusing citations.

**Instead:** Two-phase chunking: (1) structure-aware coarse split by headings/sections, then (2) recursive character split for oversized sections. Preserve hierarchy metadata in each chunk.

### Anti-Pattern 4: Trusting LLM Citations Without Verification

**What:** Let the LLM generate `[Source 1]` citations and display them to the user without checking.

**Why bad:** LLMs frequently hallucinate citations -- referencing non-existent sources, mixing up source numbers, or attributing content to the wrong document. This directly undermines the system's trustworthiness.

**Instead:** Post-processing citation verification step that maps every citation in the answer to an actual retrieved chunk. Strip or flag any unverified citations.

### Anti-Pattern 5: Shared Storage Without Project Isolation

**What:** Store all projects' documents in the same indices/collections with only application-level filtering.

**Why bad:** A single bug in the filter logic leaks cross-project data. Performance degrades as all projects share the same index scan. No clear data ownership for compliance.

**Instead:** Milvus Partition Key on `project_id`, ES index aliases or routing by project, PostgreSQL Row-Level Security. Application middleware injects project scope into every query.

### Anti-Pattern 6: Synchronous Document Processing in Request Path

**What:** Process and index documents during the user's HTTP request.

**Why bad:** Document parsing (especially OCR) can take minutes. Blocks the API worker, causes timeouts, and degrades query performance.

**Instead:** Async pipeline via Redis Streams. Connectors publish tasks, Workers consume independently. User sees sync status, not blocked requests.

## Scalability Considerations

| Concern | At 50 users / 10 projects | At 200 users / 50 projects | At 1000+ users / 500+ projects |
|---------|---------------------------|----------------------------|-------------------------------|
| Query throughput | Single FastAPI instance, single vLLM | 2x FastAPI behind nginx, vLLM with continuous batching | Kubernetes autoscaling, vLLM multi-node |
| Vector search latency | Milvus standalone, 500K vectors | Milvus cluster (3 nodes), 5M vectors | Milvus cluster with GPU indexing, 50M+ vectors |
| Document processing | 1-2 Celery workers | 4-8 workers with priority queues | Dedicated processing cluster |
| LLM inference | vLLM on 4xA100 (72B model) | vLLM on 4xA100 with larger batch | Multi-node vLLM or switch to smaller quantized model |
| Storage | PostgreSQL single node, MinIO single node | PostgreSQL primary-replica, MinIO 4-node | PostgreSQL cluster, MinIO distributed, S3-compatible |
| Concurrency | 10 concurrent queries | 50 concurrent queries | 200+ concurrent queries |

## Suggested Build Order (Dependency-Driven)

The build order follows a strict dependency chain where each layer builds on the one below it. Within each layer, components can be built in parallel.

```
Phase 1: Foundation (no dependencies)
  ├── PostgreSQL schema + migrations
  ├── Milvus collection schema (with partition key + BM25 function)
  ├── Elasticsearch index template (with ik_max_word analyzer)
  ├── Redis configuration
  ├── MinIO setup
  ├── FastAPI application skeleton
  └── Docker Compose development environment

Phase 2: Data Ingestion Pipeline (depends on Phase 1)
  ├── Local File Connector (simplest, validates the pipeline end-to-end)
  ├── Document Processing Pipeline (parse → chunk → embed → index)
  │   ├── Markdown/Text parser (simplest)
  │   ├── PDF parser (MinerU + OCR)
  │   ├── Word/Excel/PPT parser
  │   └── Chinese chunker
  ├── Embedding service (bge-large-zh-v1.5)
  └── Index builder (dual-write Milvus + ES)

Phase 3: Remaining Connectors (depends on Phase 2 pipeline)
  ├── Seafile Connector
  ├── NAS Connector
  └── DingTalk Connector (most complex, last)

Phase 4: RAG Engine (depends on Phase 2 indexes being populated)
  ├── LangGraph state machine skeleton
  ├── Query understanding node
  ├── Milvus vector retriever
  ├── ES BM25 retriever
  ├── RRF fusion module
  ├── Reranker service (bge-reranker-v2-m3)
  └── Document grading node + rewrite loop

Phase 5: Generation + Anti-Hallucination (depends on Phase 4 retrieval)
  ├── vLLM deployment (Qwen2.5-72B)
  ├── Prompt engineering + context builder
  ├── Answer generation with streaming
  ├── Citation verification post-processor
  ├── Confidence scorer
  └── Multi-turn session management

Phase 6: Business Services + API (depends on Phase 5 generation)
  ├── User auth + RBAC service
  ├── Project management service
  ├── QA orchestration service
  ├── Feedback collection service
  └── API endpoints (REST + WebSocket/SSE)

Phase 7: Frontend (depends on Phase 6 API)
  ├── Chat UI with SSE streaming
  ├── Citation display + source viewer
  ├── Admin dashboard
  └── Feedback UI

Phase 8: Evaluation + Monitoring (depends on Phase 6+7)
  ├── RAGAS evaluation pipeline
  ├── BadCase management workflow
  ├── Prometheus + Grafana dashboards
  └── Quality metrics tracking
```

## Architecture Decision Records

### ADR-1: External RRF Fusion (Milvus + ES) vs Milvus-Only Hybrid

**Decision:** Use Elasticsearch for BM25 with ik_max_word Chinese tokenizer, and Milvus for vector search. Perform RRF fusion in application code.

**Rationale:** Milvus 2.6 native BM25 uses a "standard" analyzer that does not match the quality of Elasticsearch's ik_max_word for Chinese text segmentation. Chinese technical terms, compound words, and domain jargon require specialized tokenization that ik_max_word provides. The overhead of external fusion is minimal (two parallel queries + merge), while the retrieval quality improvement is significant.

**Revisit when:** Milvus adds Chinese-aware BM25 tokenization support.

### ADR-2: LangGraph for RAG Workflow (not raw FastAPI)

**Decision:** Use LangGraph StateGraph to model the retrieval-generation pipeline as a graph with conditional edges and correction loops.

**Rationale:** The RAG pipeline has branching logic (retrieve or answer directly), loops (rewrite and re-retrieve), and state that must persist across steps (query, retrieved docs, grades, answer). LangGraph provides built-in state management, persistence, streaming, and visualization. Writing this as nested if/else in FastAPI handlers leads to unmaintainable spaghetti.

**Revisit when:** If LangGraph adds unacceptable latency overhead. LangGraph's graph compilation adds ~5ms overhead per invocation, which is negligible relative to the 2-5s total query time.

### ADR-3: LlamaIndex for Data Layer, LangGraph for Workflow

**Decision:** Use LlamaIndex for document loading, parsing, chunking, embedding, and indexing (the data layer). Use LangGraph for the retrieval-generation workflow orchestration (the logic layer).

**Rationale:** LlamaIndex excels at the ETL pipeline -- it has the richest ecosystem of document loaders, node parsers, and vector store integrations. LangGraph excels at workflow orchestration -- state management, conditional routing, and correction loops. Together they cover the full RAG stack without overlap.

### ADR-4: Redis Streams over Kafka/RabbitMQ

**Decision:** Use Redis Streams as the message queue for document sync tasks.

**Rationale:** The document sync workload is estimated at thousands of tasks per day, not millions. Redis Streams handles this volume easily while requiring no additional infrastructure (Redis is already needed for caching). Consumer groups provide horizontal scaling of workers. If volume grows beyond Redis Streams capacity (unlikely at target scale), migration to Kafka is straightforward since the interface is abstract.

### ADR-5: bge-large-zh-v1.5 over bge-m3 for Embedding

**Decision:** Use bge-large-zh-v1.5 (1024-dim, Chinese-optimized) as the primary embedding model.

**Rationale:** The system is Chinese-first. bge-large-zh-v1.5 outperforms multilingual models on Chinese text benchmarks. The 1024-dimension is well-supported by Milvus HNSW indexing. If multilingual support is needed later (English technical terms mixed with Chinese), bge-m3 can be evaluated as a replacement.

## Sources

- Milvus 2.6 Hybrid Search Documentation: https://milvus.io/docs/v2.6.x/search_patterns.md (Context7 verified)
- Milvus 2.6 RAG Pipeline: https://milvus.io/docs/v2.6.x/rag_pipeline.md (Context7 verified)
- Milvus 2.6 Full-Text Search Schema: https://milvus.io/docs/v2.6.x/full-text-search.md (Context7 verified)
- LangGraph Agentic RAG: https://docs.langchain.com/oss/python/langgraph/agentic-rag (Context7 verified)
- LangGraph Graph API: https://docs.langchain.com/oss/python/langgraph/graph-api (Context7 verified)
- LlamaIndex IngestionPipeline: https://developers.llamaindex.ai/python/framework/module_guides/loading/node_parsers (Context7 verified)
- RAGAS Faithfulness Metric: https://github.com/explodinggradients/ragas/blob/main/docs/concepts/metrics/available_metrics/faithfulness.md (Context7 verified)
- RAGAS Answer Relevancy: https://github.com/explodinggradients/ragas/blob/main/docs/concepts/metrics/available_metrics/answer_relevance.md (Context7 verified)
- RAGFlow Architecture: https://github.com/infiniflow/ragflow (Context7 verified)
- Project Specification: /home/liuzl/agent/RAG-AGENT/企业多源项目知识问答Agent_项目方案.md
