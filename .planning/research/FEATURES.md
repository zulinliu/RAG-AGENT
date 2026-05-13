# Feature Landscape

**Domain:** Enterprise Multi-Source Knowledge QA Agent (RAG System)
**Researched:** 2026-05-13
**Target:** Internal project teams (50-200 users), Chinese-language enterprise deployment
**Overall confidence:** HIGH (based on project spec, 6 open-source platforms analyzed, and RAG ecosystem survey)

## Table Stakes

Features users expect. Missing any of these means the system feels incomplete or untrustworthy. These are non-negotiable for V1.

### Natural Language Q&A with Accurate Answers

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Natural language Q&A in Chinese | Users will not learn a query language. Chatbot UX is the mental model everyone has now. | Medium | Prompt engineering is the hard part, not the API call |
| Grounded answers with source citations | Without citations, users cannot verify answers and will not trust the system. This is the single most important trust signal. | Medium | Every factual claim must reference a specific document and section |
| "I don't know" when evidence is insufficient | A QA system that fabricates answers is worse than no QA system. Users will abandon it after one bad hallucination. | Medium | Requires careful prompt design and confidence thresholds |
| Streaming response output | Users expect chat-like real-time output. Waiting 5 seconds for a full response feels broken. | Low | SSE/WebSocket streaming is standard in every modern RAG platform |

### Document Ingestion and Search

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Multi-format document parsing (PDF/Word/Excel/PPT/MD) | Enterprise knowledge lives in all of these. Missing one format means missing real documents. | High | PDF (especially scanned) is the hardest; MinerU + PaddleOCR is the right stack |
| Hybrid search (keyword + semantic) | Pure keyword search misses semantic matches; pure vector search misses exact terms. Both are needed. | Medium | BM25 + vector with RRF fusion is the industry standard pattern |
| Reranking of search results | Without reranking, Top-10 accuracy is poor. Rerank is what separates demo-grade from production-grade. | Medium | bge-reranker-v2-m3 for Chinese is the right choice |
| Incremental document sync | Users upload new documents daily. If sync is manual-only or batch-only, knowledge goes stale. | Medium | Event-driven (watchdog) + polling hybrid covers all data sources |
| Chinese-optimized chunking | Default chunking breaks Chinese text mid-sentence. This destroys retrieval quality. | High | Structure-aware + recursive character split with Chinese delimiters (。\！\？\；) |

### Multi-Project Isolation and Access Control

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Project-level data isolation | Different projects have different teams. Cross-project data leakage is a dealbreaker for enterprise. | Medium | Milvus partition key by project_id + ES field filtering + PG row-level |
| RBAC permission model | Enterprise requires at minimum admin vs. regular user. Without this, IT will not approve deployment. | Medium | 4-5 roles: sys admin, project admin, KB admin, user, readonly |
| User authentication (SSO/LDAP or basic) | Users will not create Yet Another Account. Must integrate with existing identity systems. | Medium | DingTalk OAuth is primary; LDAP fallback for non-DingTalk orgs |

### Web Chat Interface

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Clean web chat UI | The interface IS the product for most users. A bad UI kills adoption regardless of backend quality. | Medium | React + Next.js per project spec; streaming markdown rendering is key |
| Source document display | Users click citations to verify. If they cannot see the source, they will not trust the answer. | Low | Link from citation [N] to highlighted passage in source document |
| Thumbs up/down feedback | The only way to improve is to collect signal. Also makes users feel heard. | Low | Simple API + storage; analytics come later |
| Conversation history | Users refer back to previous questions. Without history, the system feels disposable. | Low | Per-user, per-project conversation list with search |

### Data Source Connectivity

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| DingTalk knowledge base sync | DingTalk is the primary knowledge platform in the target org. Without it, the system covers <50% of knowledge. | High | API preferred; dingtalk-workspace-cli as fallback when no enterprise API access |
| Seafile file sync | Seafile holds project files. Without it, technical documents are missing. | Medium | Seafile Web API v2.1 with Token auth; well-documented |
| NAS/local file sync | Some teams store files on NAS or local machines. Must support these as well. | Medium | SMB/NFS/WebDAV protocols; watchdog for event-driven sync |

## Differentiators

Features that set this system apart from generic RAG platforms (Dify, FastGPT, MaxKB). Not expected by default, but create strong competitive advantage for this specific use case.

### Anti-Hallucination Depth

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Multi-layer hallucination defense | Most RAG platforms have a single "grounded" prompt. This system has 5+ layers: retrieval filtering, forced citation, refusal to answer, citation verification, confidence scoring. This is the core differentiator. | High | The project spec already outlines this well; execution matters |
| Citation verification post-processing | After LLM generates, verify every [Source N] reference actually maps to a real retrieved chunk. Most platforms skip this. | Medium | Regex extraction + chunk ID lookup; filters fabricated references |
| Confidence score display | Show users how confident the system is. Low confidence = "verify original docs". Most platforms give no signal. | Medium | Based on rerank scores, citation coverage, context relevance |
| Automated RAGAS evaluation pipeline | Continuous quality monitoring. Most teams evaluate once and never again. This catches regression early. | Medium | Faithfulness >= 0.90, Answer Relevancy >= 0.85 targets per spec |

### Enterprise Integration Depth

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| DingTalk bot in-app Q&A | Users do not leave DingTalk. Questions answered where work happens. This is adoption-critical for Chinese enterprises. | Medium | DingTalk robot Webhook; receive messages in group, reply with answers |
| BadCase management workflow | Structured process: collect (thumbs down) -> classify (retrieval vs generation failure) -> analyze (weekly) -> optimize -> verify. This is how the system improves over time. | Medium | Dedicated admin UI for case review and pattern analysis |
| Quality monitoring dashboard | Real-time metrics: accuracy, satisfaction rate, hallucination rate, latency. Makes the system auditable for management. | Medium | Grafana + Prometheus; per-project, per-time-range views |

### Chinese-Optimized Pipeline

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Structure-aware Chinese chunking with jieba boundary protection | Default chunkers (LlamaIndex, LangChain) handle Chinese poorly. Custom chunker that respects Chinese sentence boundaries and document structure (H1/H2/H3 hierarchy) significantly improves retrieval quality. | High | The spec's hybrid approach (structure + recursive + jieba check) is the right design |
| bge-large-zh-v1.5 + bge-reranker-v2-m3 combination | Chinese-optimized embedding + reranker pair. Most platforms default to multilingual models which underperform on Chinese. | Low | Well-established models with strong Chinese benchmarks |
| Chinese document type awareness | Different chunking strategies for technical docs vs. meeting minutes vs. tables vs. FAQ pairs. This context-specific tuning is rare in generic platforms. | Medium | Per-spec chunking strategy table with type-specific parameters |

### Data Source Deduplication

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Cross-source document deduplication | Same document often exists in DingTalk AND Seafile AND NAS. SHA-256 content hash dedup + vector similarity fuzzy dedup prevents indexing noise. | Medium | Most platforms do not handle this because they assume single-source |
| Source priority resolution | When duplicates exist, define priority (DingTalk > Seafile > NAS > local) and keep latest version. Prevents stale answers. | Low | Simple rule engine per project configuration |

## Anti-Features

Features to explicitly NOT build. These are scope-killers, maintenance nightmares, or outside the system's purpose.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| General-purpose chatbot / small talk handling | Dilutes the core value proposition. Adds complexity to intent routing. Makes hallucination control harder because the system tries to answer everything. | Detect off-topic questions and respond: "I can only answer questions about project knowledge. Please ask about specific project documents, decisions, or processes." |
| Document editing / collaboration | Not a document management system. Building editing features doubles the scope. The system's job is retrieval, not creation. | Link to source documents in their original platform (DingTalk, Seafile). Let users edit there. |
| Code generation / execution (V1) | Requires an entirely different pipeline (AST parsing, code embedding, execution sandbox). Distracts from core QA quality. | Defer to V2. Build solid text QA first. |
| Auto document generation / report writing (V1) | Complex multi-agent orchestration with different quality requirements. Report generation has different accuracy tolerances than QA. | Defer to V2/V3. The spec already correctly scopes this out. |
| Knowledge graph / multi-hop reasoning (V1) | GraphRAG is immature and adds enormous complexity. The marginal accuracy gain does not justify the engineering cost at 50-200 users. | Defer to V2. Start with flat retrieval + rerank which covers 90% of use cases. |
| Multi-language support (non-Chinese) | Target users are Chinese-speaking internal teams. Adding English/Japanese support doubles testing and tuning surface. | Chinese-first. bge-m3 model supports cross-lingual retrieval if needed later, but do not optimize for it. |
| Mobile app | Web responsive is sufficient for initial launch. Native mobile is a major engineering investment with low marginal value for an internal tool. | Responsive web design. DingTalk bot provides mobile access within the app users already have. |
| Plugin / extension marketplace | Premature abstraction. Building an extensible plugin system before core features are solid is classic over-engineering. | Build features directly. Consider plugin architecture in V3 if third-party integration demand emerges. |
| Real-time collaboration features | Google Docs-style co-editing is completely outside the system's purpose and would require fundamentally different architecture. | The system is read-only for documents. All writes happen in source systems. |
| Custom model fine-tuning UI | Fine-tuning embedding or LLM models is an engineering task, not a user feature. Exposing this to admins invites misconfiguration. | Engineer-driven model selection and tuning. Provide configuration (model name, temperature) but not training UI. |
| Agentic autonomous search (V1) | Letting the AI decompose and plan multi-step searches is cool but adds latency, unpredictability, and debugging complexity. | Single-turn retrieval + generation. Well-tuned hybrid search covers the majority of enterprise QA scenarios. |
| Voice input / TTS output | Niche feature for an internal enterprise tool. Significantly increases integration complexity (ASR + TTS pipeline). | Text-only input/output. If demand exists, DingTalk voice messages can be handled by DingTalk's built-in ASR. |

## Feature Dependencies

```
Data Source Connectors (DingTalk/Seafile/NAS/Local)
  --> Document Parsing Engine (PDF/Word/Excel/PPT/MD/OCR)
    --> Chinese Smart Chunking (structure-aware + recursive)
      --> Embedding + Indexing (bge-large-zh -> Milvus + ES)
        --> Hybrid Retrieval (vector + BM25)
          --> RRF Fusion
            --> Rerank (bge-reranker-v2-m3)
              --> Answer Generation (Qwen2.5 + anti-hallucination prompt)
                --> Citation Verification (post-processing)
                  --> Confidence Scoring
                    --> Streaming Response to Web UI

RBAC + Project Isolation (independent, but must wrap all retrieval)
  --> applies project_id filter at every storage and retrieval layer

User Feedback (thumbs up/down)
  --> BadCase Collection
    --> BadCase Analysis (manual review)
      --> Retrieval/Generation Tuning Loop

DingTalk Bot (depends on Q&A API being ready)
  --> mirrors Web UI functionality in DingTalk group context
```

Dependency chains that block parallel development:
- Chunking depends on parsing being stable (parsing API contract must be defined early)
- Retrieval depends on chunking + indexing being stable (retrieval API contract must be defined early)
- Answer generation depends on retrieval (context format must be agreed upon)
- Frontend depends on Q&A API contract (define OpenAPI spec early)
- DingTalk bot depends on Q&A API (can be developed in parallel with frontend once API is stable)

## MVP Recommendation

### Priority 1 -- Ship These First (Core Value Loop)

These form the smallest useful system. A user can upload a document, ask a question, and get a cited answer.

1. Local file connector (simplest data source, validates the pipeline end-to-end)
2. PDF/Word/Markdown parsing (covers 80% of document types)
3. Chinese smart chunking with structure awareness
4. Hybrid search (vector + BM25) with RRF fusion and rerank
5. Answer generation with forced citation and "I don't know" refusal
6. Streaming web chat UI with source display
7. Basic project isolation (project_id filtering)
8. Thumbs up/down feedback

### Priority 2 -- Complete the Enterprise Story

These make it deployable for real teams.

9. DingTalk knowledge base connector (or CLI fallback)
10. Seafile connector
11. NAS connector
12. RBAC with DingTalk OAuth authentication
13. Admin dashboard (project management, data source config, sync monitoring)
14. Citation verification post-processing
15. Confidence score display

### Priority 3 -- Quality and Scale

These make it sustainable and trustworthy.

16. BadCase management workflow
17. RAGAS automated evaluation pipeline
18. Quality monitoring dashboard (Grafana)
19. DingTalk bot integration (in-app Q&A)
20. Conversation history and search
21. Document deduplication across sources

### Defer to V2

- Knowledge graph / GraphRAG
- Agentic multi-step search
- Code generation
- Auto document generation
- Meeting minutes generation
- Multimodal QA (image/table understanding beyond OCR)

## Feature-Platform Comparison

How this project's planned features compare to existing open-source platforms:

| Feature Area | This Project | RAGFlow | Dify | FastGPT | QAnything | MaxKB |
|-------------|-------------|---------|------|---------|-----------|-------|
| Deep citation tracing | Multi-layer verification | Good | Basic | Basic | Basic | Basic |
| Anti-hallucination depth | 5+ layers | Prompt-only | Configurable | Configurable | Prompt-only | Basic |
| Chinese chunking | Custom jieba-aware | Template-based | Generic | Generic | Good | Generic |
| Multi-source sync (DingTalk/Seafile/NAS) | Native 4 connectors | S3/Notion/Drive plugins | Manual upload | Manual upload | Manual upload | Manual + web crawl |
| Cross-source dedup | SHA-256 + vector fuzzy | No | No | No | No | No |
| Project-level isolation | Milvus partition + ES filter + PG row | Dataset-level | Tenant-level | Knowledge base level | Knowledge base level | Knowledge base level |
| BadCase management workflow | Full lifecycle | No | No | No | No | No |
| DingTalk native integration | Bot + KB sync | No | No | No | No | No |
| RAGAS evaluation | Built-in pipeline | No | Langfuse integration | No | No | No |

**Key insight:** No existing platform offers the combination of deep anti-hallucination + Chinese-optimized chunking + multi-source enterprise connectors + DingTalk integration. This project fills a genuine gap in the Chinese enterprise RAG market.

## Sources

- RAGFlow GitHub (infiniflow/ragflow) -- deep document parsing, citation tracing, template chunking
- Dify GitHub (langgenius/dify) -- workflow orchestration, plugin ecosystem, RAG pipeline
- FastGPT GitHub (labring/FastGPT) -- visual workflow, multi-library QA, API integration
- QAnything GitHub (netease-youdao/QAnything) -- Chinese two-stage retrieval, offline deployment, BCEmbedding
- MaxKB GitHub (1Panel-dev/MaxKB) -- lightweight agent platform, workflow engine, multi-modal
- Langchain-Chatchat GitHub (chatchat-space/Langchain-Chatchat) -- full RAG pipeline, BM25+KNN, FAISS default
- RAGAS library (vibrantlabsai/ragas via Context7) -- Faithfulness, ContextPrecision, ContextRecall, AnswerRelevancy metrics
- Project specification: 企业多源项目知识问答Agent_项目方案.md
