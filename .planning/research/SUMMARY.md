# Research Summary

**Project:** Enterprise Multi-Source Knowledge QA Agent (RAG-AGENT)
**Synthesized:** 2026-05-13
**Confidence:** HIGH

## Key Findings

### Stack
- Python 3.11+ / FastAPI 0.136 / Pydantic 2.13 / SQLAlchemy 2.0 / Celery 5.6
- Milvus 2.6.15 (内置BM25稀疏向量) + Elasticsearch 8.19.x (ik_max_word中文分词) + PostgreSQL 17
- bge-large-zh-v1.5 (1024维) + bge-reranker-v2-m3 (中文Embedding/Rerank SOTA)
- Qwen2.5-72B via vLLM 0.20.x (私有部署) / MinerU 1.3 + PaddleOCR 3.5 + Unstructured 0.22
- React 19 + Next.js 15 + Tailwind 4 前端
- **关键决策**: 自定义检索管道（不用LlamaIndex/LangChain作为主框架），LlamaIndex仅用于数据层ETL，LangGraph用于RAG工作流编排

### Table Stakes
- 自然语言中文问答 + 强制来源引用 + "我不知道"拒绝回答
- 多格式文档解析（PDF/Word/Excel/PPT/MD/图片OCR）
- 混合检索（BM25 + 向量 + RRF融合 + Rerank精排）
- 项目级数据隔离 + RBAC权限
- Web对话界面（流式输出、来源展示、反馈收集）
- 多数据源连接器（钉钉/Seafile/NAS/本地文件）
- 增量同步 + 文档去重

### Differentiators
1. **多层反幻觉防御** (5+层)：检索过滤 → 上下文门控(CRAG纠正循环) → 生成约束 → 引用验证 → 持续评估
2. **中文优化分块**：结构感知 + 递归字符 + jieba边界保护，按文档类型差异化参数
3. **企业多源原生连接**：钉钉知识库 + Seafile + NAS + 本地文件，跨源去重
4. **BadCase管理闭环**：收集 → 分类 → 分析 → 优化 → 验证

### Watch Out For
1. **中文分块质量**是检索精度的关键瓶颈 — 默认分块器严重损害中文文本
2. **钉钉API权限不确定** — 必须验证CLI替代方案(dingtalk-workspace-cli)能否获取所需内容
3. **Milvus 2.6 BM25中文分词不如ES的ik_max_word** — 保留ES做中文BM25，外部RRF融合
4. **PyMilvus 3.0.0是大版本升级** — 需早期测试hybrid search API兼容性
5. **文档处理GPU需求** — MinerU + PaddleOCR需GPU，需与LLM推理分开规划
6. **RAGAS评估需独立LLM** — 用同一模型做生成和评估可能引入偏差
7. **Elasticsearch 9.x不成熟** — 坚持使用8.19.x，ik_analyzer插件生态更稳定

## Architecture Summary

6层管道架构：Data Source Connectors → Document Processing Pipeline → RAG Engine → Business Services → API Gateway → Frontend

核心模式：
- LangGraph StateGraph编排RAG管道（CRAG纠正循环）
- Milvus Partition Key实现项目级数据隔离
- Redis Streams + Celery实现异步文档同步
- 5层反幻觉防御架构

## Build Order

Phase 1: 基础设施（数据库Schema + FastAPI骨架 + Docker Compose）
Phase 2: 数据摄入管道（本地连接器 + 解析器 + 分块器 + Embedding + 索引）
Phase 3: 剩余连接器（Seafile + NAS + 钉钉）
Phase 4: RAG引擎（LangGraph管道 + 混合检索 + Rerank）
Phase 5: 生成 + 反幻觉（vLLM部署 + Prompt工程 + 引用验证）
Phase 6: 业务服务 + API（用户/RBAC + 项目管理 + QA编排）
Phase 7: 前端（对话UI + 管理后台）
Phase 8: 评估 + 监控（RAGAS + BadCase + Grafana）

## Files
- `.planning/research/STACK.md` — 完整技术栈推荐
- `.planning/research/FEATURES.md` — 功能全景与优先级
- `.planning/research/ARCHITECTURE.md` — 架构模式、反模式、ADR

---
*Research synthesized: 2026-05-13*
