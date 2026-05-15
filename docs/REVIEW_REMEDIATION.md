# 评审整改记录

本文档记录本轮按 `企业多源项目知识问答Agent_项目方案.md` 评审后的主要整改结果，便于后续复查。

## 1. 架构设计补充

已补充 `docs/ARCHITECTURE.md`，明确：

- 总体分层和模块边界。
- 文档同步、文件上传、流式问答三条主链路。
- 前后端字段契约、文档状态模型、索引命名规范。
- 可靠性、安全、质量评估和后续扩展点。

## 2. 已修复问题

### 2.1 部署和配置

- 健康检查兼容 `/health` 和 `/api/v1/health`，认证中间件放行两条路径。
- Milvus collection、Elasticsearch index、初始化脚本统一到 `rag_chunks`。
- 默认本地 LLM 端点从后端自身端口修正为 vLLM 端口。
- Docker Compose 为 backend、worker、beat 增加共享上传目录，保证上传文件可被 Worker 处理。
- ES 初始化和运行时索引创建在 IK 插件缺失时可回退到 standard analyzer。
- `.env.example` 补充索引名、collection 名和初始化管理员变量。

### 2.2 文档处理和同步

- `DocumentPipeline.from_settings()` 修正错误配置引用，改用真实的 `settings.es/settings.milvus/settings.embedding` 字段。
- parser registry 注册 PDF、Word、Excel、PPT、Markdown、文本、图片解析器。
- 上传接口保存文件到共享路径，创建完整任务载荷，并在 MinIO 不可用时本地兜底。
- 数据源手动同步从空任务改为真正派发 `sync_data_source_task`。
- Celery 数据源同步实现连接、列文件、下载、逐文件处理和状态更新。
- 本地目录 watchdog 触发任务时传入完整同步字段。
- 文档失败状态统一落库，避免解析失败后一直显示 `pending`。
- 文档处理状态统一为 `pending/processing/indexed/failed`。

### 2.3 检索和问答

- CRAG 文档相关性判断修复 `IRRELEVANT` 被误判为相关的问题。
- LangGraph 返回 dict 时转换回 `QueryState`。
- BM25 查询移除强制 IK analyzer 参数，兼容 ES fallback mapping。
- 流式问答前端发送 `question`，与后端 schema 对齐。
- SSE 客户端支持后端 `{type,data}` 事件格式，并读取最终 `message_id/confidence/conversation_id`。
- 新会话流式问答后前端会保存 `conversation_id`，下一轮能延续上下文。
- 中止生成时避免重复追加同一条助手消息。

### 2.4 管理端和接口契约

- 数据源前端字段改为 `source_type/sync_status`。
- Seafile 字段改为 `access_token`，NAS 字段改为 `remote_path`，NAS 增加 `protocol`。
- 数据源测试连接改为调用真实 test endpoint。
- 管理端新增 `/api/v1/datasources` 聚合列表，避免“全部数据源”页面按项目 N+1 请求。
- 数据源更新接口修复越权写入风险：先校验项目权限，再执行更新。
- 文档列表补充 `filename/file_size/size/chunk_count` 兼容字段。
- 对话列表和会话详情补充 `id/title/message_id` 等前端需要字段。

### 2.5 评估与 BadCase

- 新增 Alembic 迁移 `0002_evaluation_tables.py`。
- BadCase 支持创建、列表过滤、解决状态更新。
- 用户点踩回答时自动生成基础 BadCase；后续点赞同一回答时自动关闭该反馈型 BadCase。
- 评估运行支持落库记录。
- 评估指标接口补充项目权限校验。

## 3. 当前仍建议后续迭代

以下内容不阻塞 V1 基础可用，但仍是下一阶段质量提升重点：

- 评估任务仍需接入真实 RAGAS 或自定义批量评估执行器。
- BadCase 需要补充前端管理页面、归因字段和整改闭环。
- 钉钉 API 的真实字段和权限模型需用企业测试账号做联调确认。
- PPT、图片 OCR、复杂 Excel 的解析质量需要样本集回归测试。
- 需要补充端到端测试：上传、同步、检索、问答、权限隔离、健康检查。
- 生产环境建议接入指标监控、日志聚合、队列积压告警和备份策略。

## 4. 优质功能场景储备

- 技术决策回溯：自动汇总某个技术选型的背景、候选方案、评审结论和风险。
- 新人项目导师：按项目生成学习路径、关键文档清单和常见问题。
- 会议结论追踪：从会议纪要中抽取行动项、负责人、截止时间并关联历史决策。
- 跨项目方案对比：发现不同项目在架构、组件、成本、故障处理上的差异。
- 知识缺口分析：统计高频无答案问题，反向推动文档补齐。
- 变更影响分析：输入接口、模块或配置项，检索相关设计、依赖和上线记录。
