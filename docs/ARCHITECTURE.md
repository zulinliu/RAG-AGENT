# RAG-AGENT 架构设计说明

本文档对齐 `企业多源项目知识问答Agent_项目方案.md` 的 V1 目标，描述当前代码实现的真实架构、关键边界和后续扩展点。

## 1. 架构目标

RAG-AGENT 的核心目标是为企业项目知识提供可追溯、权限隔离、可持续同步的问答能力。架构优先级如下：

1. 准确性和可追溯性：混合检索、重排序、CRAG 自校正、引用校验和置信度评分共同降低幻觉。
2. 多源接入：统一连接器模型接入本地目录、Seafile、NAS、钉钉知识库。
3. 项目隔离：鉴权层、PostgreSQL 元数据、Milvus partition key 和检索过滤共同保证项目级隔离。
4. 可运维性：健康检查、同步状态、BadCase、评估运行记录和标准化部署配置支持上线后的质量闭环。
5. 可扩展性：连接器、解析器、检索器、评估器均按接口边界扩展，避免把业务逻辑写死在 API 层。

## 2. 总体分层

```text
Frontend (Next.js)
  - chat/admin/status pages
  - SSE stream client
  - data source and document management

FastAPI API Layer
  - auth/projects/datasources/documents/qa/evaluation/health
  - JWT + RBAC + project permission checks

Service Layer
  - QAService
  - DataSourceService
  - DocumentService

Async Task Layer
  - Celery worker/beat
  - data source sync
  - document processing dispatch

RAG Engine
  - query understanding
  - hybrid retrieval
  - RRF fusion
  - rerank
  - document grading
  - generation
  - citation verification

Document Processing Pipeline
  - parser registry
  - cleaner
  - Chinese chunker
  - embedding
  - dual indexer

Storage
  - PostgreSQL: users/projects/datasources/documents/chunks/conversations/evaluation
  - Milvus: vector index, collection `rag_chunks`
  - Elasticsearch: BM25 index `rag_chunks`
  - Redis: Celery broker/cache
  - MinIO/local uploads: original files
```

## 3. 核心数据流

### 3.1 文档同步流

1. 管理员在前端创建数据源，后端保存 `source_type + config`。
2. 手动同步或 Celery Beat 触发 `sync_data_source_task`。
3. 连接器执行 `connect -> list_files -> download_file`。
4. 每个文件进入 `sync_document_task`。
5. `DocumentPipeline` 执行解析、清洗、分块、向量化。
6. `DualIndexer` 写入 Milvus 和 Elasticsearch；两者都成功后写 PostgreSQL 元数据和分块记录。
7. 数据源状态更新为 `completed` 或 `failed`，文档状态更新为 `indexed` 或 `failed`。

### 3.2 文件上传流

1. 前端上传文件到 `/api/v1/projects/{project_id}/documents/upload`。
2. 后端校验扩展名、content type、大小，写入共享上传目录。
3. 尝试写入 MinIO；MinIO 不可用时保留本地路径作为处理源。
4. 创建 `documents` pending 记录。
5. 派发 `sync_document_task`，使用现有处理管道完成索引。

### 3.3 问答流

1. 前端向 `/api/v1/qa/stream` 发送 `question/project_id/conversation_id`。
2. `QAService` 创建或复用 conversation，并保存用户消息。
3. CRAG 管道完成查询理解、检索、重排、文档相关性判断。
4. 生成器通过 SSE 输出 token。
5. 生成结束后做引用校验和置信度评分，保存助手消息。
6. 最终 SSE `done` 事件返回 `conversation_id/message_id/citations/confidence/sources_used`。

## 4. 关键契约

### 4.1 数据源前后端字段

API 使用以下字段作为唯一契约：

- `source_type`: `local | seafile | nas | dingtalk`
- `sync_status`: `idle | syncing | completed | failed`
- Seafile token 字段：`access_token`
- NAS 路径字段：`remote_path`
- NAS 协议字段：`protocol`，支持 `nfs/smb/webdav`

旧字段 `type/api_token/share_path/status` 仅在部分同步任务中做向后兼容读取，不作为新接口输出。

### 4.2 文档状态

文档处理状态统一为：

- `pending`: 已入库但尚未开始处理
- `processing`: 正在解析、分块或索引
- `indexed`: Milvus、Elasticsearch、PostgreSQL 元数据写入完成
- `failed`: 解析、向量化、索引或元数据写入失败

### 4.3 索引命名

当前运行时代码、初始化脚本和配置统一使用：

- Milvus collection: `rag_chunks`
- Elasticsearch index: `rag_chunks`

如需多环境隔离，优先通过独立数据库/集群或显式设置 `MILVUS_COLLECTION_NAME`、`ES_INDEX_NAME`，不要只改 prefix。

## 5. 可靠性设计

- 双索引写入：Milvus 和 ES 任一失败时回滚已写入的一侧，并把文档标为 `failed`。
- 解析失败可见：解析为空、分块为空、管道异常均会更新文档状态，避免长时间停留在 `pending`。
- 增量处理：文档 ID 对数据源文件使用项目、数据源、路径的稳定 UUID；同一文件重复同步可稳定命中已有记录。
- ES 降级：IK analyzer 不可用时自动回退 standard analyzer，保证开发和最小部署能启动。
- 上传兜底：MinIO 不可用时仍保留本地上传文件，Worker 通过共享 `/app/uploads` 处理。

## 6. 安全设计

- JWT 鉴权默认保护所有业务接口。
- `/health` 和 `/api/v1/health` 公开用于容器健康检查。
- 项目访问统一通过 `check_project_permission` 校验。
- 数据源更新采用先读、先校验权限、再写入的顺序。
- 数据源响应会屏蔽 password、secret、token、key 等敏感配置字段。

## 7. 评估与质量闭环

当前已具备基础闭环：

- 用户反馈：对回答点赞/点踩。
- BadCase：按消息归属项目落库，支持列表和解决状态；点踩会自动生成反馈型 BadCase。
- Evaluation Run：可记录评估运行、数据集名、状态、指标 JSON。

后续建议补齐：

- RAGAS 或自定义评估任务的异步执行器。
- 标注数据集管理。
- 指标趋势看板。
- BadCase 到检索参数、分块策略、提示词、连接器质量的归因工作流。

## 8. 后续扩展点

- 连接器：企业微信、飞书、Confluence、Git 仓库、Jira/禅道。
- 解析器：图片 VLM 描述、CAD/流程图、邮件、压缩包。
- 检索：GraphRAG、跨项目相似方案发现、时间线检索。
- Agent 场景：技术决策回溯、风险清单生成、周报/月报生成、接口变更影响分析。
- 运维：Grafana 看板、OpenTelemetry 链路追踪、队列积压告警。
