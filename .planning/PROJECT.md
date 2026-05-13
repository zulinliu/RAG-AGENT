# 企业多源项目知识问答Agent (RAG-AGENT)

## What This Is

基于RAG架构的企业级知识问答系统，整合钉钉知识库、Seafile、NAS、本地文件等多数据源项目材料，通过自然语言交互为项目成员提供精准、可追溯的知识问答服务。面向公司内部50-200人的项目团队。

## Core Value

答案精准度 — 确保回答基于真实项目材料，目标准确率 >= 90%，幻觉率 <= 5%，每个回答附带来源引用。

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] 多数据源文档自动同步（钉钉/Seafile/NAS/本地文件）
- [ ] 文档解析引擎（PDF/Word/Excel/PPT/Markdown/图片OCR）
- [ ] 中文智能分块（结构感知 + 递归字符分块）
- [ ] 混合检索引擎（BM25 + 向量语义检索 + RRF融合 + Rerank精排）
- [ ] 答案生成引擎（含反幻觉机制、强制引用、置信度评估）
- [ ] Web对话界面（流式输出、来源引用展示、反馈收集）
- [ ] 管理后台（项目管理、数据源配置、用户权限、同步监控）
- [ ] 多项目隔离（RBAC权限模型、项目级数据隔离）
- [ ] 完整的Docker Compose部署方案

### Out of Scope

- 不替代现有文档管理系统 — 仅做知识检索层
- 不支持实时协作编辑 — 非本系统职责
- 不做通用聊天机器人 — 仅回答项目知识相关问题
- 不做代码生成/执行 — V2阶段支持
- 不做自动文档生成 — V2阶段支持
- 不处理涉密/机密信息 — 系统不存储机密文档

## Context

### 技术背景
- 公司使用钉钉作为项目管理和知识库平台
- Seafile作为文件管理平台，NAS用于网络存储
- 项目知识分散在多个系统中，检索效率低
- 现有通用大模型无法获取公司内部资料，容易产生幻觉

### 业务驱动
- 知识检索平均耗时10-30分钟/次，严重影响效率
- 新人培训成本高，历史决策难以追溯
- 核心人员离职后知识流失风险

### 技术选型已确定
- 后端：Python (FastAPI)
- 前端：React + Next.js
- LLM：Qwen2.5-72B (私有部署，vLLM加速)
- Embedding：bge-large-zh-v1.5 (1024维)
- Rerank：bge-reranker-v2-m3
- 向量数据库：Milvus 2.6
- 全文检索：Elasticsearch 8.x
- 关系数据库：PostgreSQL 16
- 缓存/消息队列：Redis 7.x
- 文档解析：MinerU + Unstructured + PaddleOCR
- 对象存储：MinIO
- 容器化：Docker + Docker Compose

## Constraints

- **部署方式**: 全链路私有化部署，数据不出域
- **GPU资源**: LLM推理需4xA100 80GB（或初期用API替代）
- **响应时间**: P95 <= 5秒
- **并发用户**: >= 50
- **知识库更新延迟**: <= 30分钟
- **文档格式**: PDF/Word/Excel/PPT/Markdown/图片
- **钉钉接入**: 可能无企业API权限，需支持CLI替代方案
- **中文优先**: 分块、检索、生成均需针对中文优化

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 自研核心 + 借鉴开源 | 需对精准度完全控制，不直接依赖单一开源平台 | — Pending |
| 混合检索（BM25+向量+Rerank） | 提升中文检索召回率和精确率 | — Pending |
| 多层反幻觉机制 | 精准度是最高优先级 | — Pending |
| bge-large-zh-v1.5 作为Embedding | 中文效果优秀，开源免费 | — Pending |
| Milvus 2.6 作为向量数据库 | 高性能分布式，混合检索支持好 | — Pending |
| Docker Compose 初期部署 | 简单快速，后续可迁移K8s | — Pending |
| Redis Streams 消息队列 | 轻量级，适合文档同步任务 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-13 after initialization*
