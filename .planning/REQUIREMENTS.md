# Requirements: Enterprise Multi-Source Knowledge QA Agent (RAG-AGENT)

**Defined:** 2026-05-13
**Core Value:** 答案精准度 — 确保回答基于真实项目材料，目标准确率 >= 90%，幻觉率 <= 5%

## v1 Requirements

### Data Source Connectivity (CONN)

- [ ] **CONN-01**: 用户可配置本地文件目录作为知识源，系统自动监控文件变更并触发同步
- [ ] **CONN-02**: 用户可配置钉钉知识库连接，系统自动同步文档元数据和内容（支持API和CLI两种模式）
- [ ] **CONN-03**: 用户可配置Seafile资料库连接，系统自动递归同步文件
- [ ] **CONN-04**: 用户可配置NAS存储连接（支持NFS/SMB/WebDAV协议），系统自动同步文件
- [ ] **CONN-05**: 系统支持增量同步，仅处理新增和变更的文档（基于修改时间戳和内容哈希）
- [ ] **CONN-06**: 系统支持跨数据源文档去重（SHA-256内容哈希 + 向量相似度模糊去重）
- [ ] **CONN-07**: 用户可在管理后台查看各数据源同步状态、成功/失败计数

### Document Processing (PROC)

- [ ] **PROC-01**: 系统可解析PDF文档（原生PDF和扫描件OCR），保留表格和标题结构
- [ ] **PROC-02**: 系统可解析Word文档（.docx），保留标题层级和表格结构
- [ ] **PROC-03**: 系统可解析Excel文档（.xlsx），将表格转换为文本描述
- [ ] **PROC-04**: 系统可解析Markdown文档，保留标题层级和代码块
- [ ] **PROC-05**: 系统可解析纯文本文件，自动检测编码
- [ ] **PROC-06**: 系统实现中文智能分块：结构感知粗分（按标题层级）+ 递归字符细分（中文分隔符优先级）+ jieba边界保护
- [ ] **PROC-07**: 系统根据文档类型自动选择分块策略（技术文档800-1000字符、会议纪要500-800字符、表格整块、FAQ按对）
- [ ] **PROC-08**: 系统为每个文档块提取完整元数据（标题、作者、日期、项目归属、文件路径、标题层级路径、内容哈希）

### Knowledge Retrieval (RETR)

- [ ] **RETR-01**: 系统使用bge-large-zh-v1.5模型将文本块转换为1024维向量并存入Milvus
- [ ] **RETR-02**: 系统使用Elasticsearch的ik_max_word分词器建立BM25全文索引
- [ ] **RETR-03**: 系统实现混合检索：并行执行Milvus向量检索(Top-50) + ES BM25检索(Top-50)
- [ ] **RETR-04**: 系统使用RRF算法融合多路检索结果
- [ ] **RETR-05**: 系统使用bge-reranker-v2-m3 Cross-Encoder对融合结果重排序，输出Top-10
- [ ] **RETR-06**: 系统对重排序结果进行相关性阈值过滤（分数低于0.3的文档剔除）
- [ ] **RETR-07**: 系统支持按项目ID范围限定检索（自动附加project_id过滤条件）
- [ ] **RETR-08**: 系统实现查询理解：意图识别、问题改写、关键词提取

### Answer Generation (GEN)

- [ ] **GEN-01**: 系统使用Qwen2.5-72B生成答案，每个事实声明必须引用来源文档编号[来源N]
- [ ] **GEN-02**: 系统在知识库无相关内容时明确回答"根据现有项目资料，我没有找到相关信息"
- [ ] **GEN-03**: 系统通过LangGraph实现CRAG管道：检索 → 文档相关性评分 → 不满足时改写查询重试 → 重排序 → 生成
- [ ] **GEN-04**: 系统实现引用验证后处理：检查答案中每个[来源N]引用对应真实检索结果，过滤虚假引用
- [ ] **GEN-05**: 系统为每个答案计算置信度评分（基于检索相关性、引用覆盖率），低于0.6时显示警告提示
- [ ] **GEN-06**: 系统支持流式输出版答案（SSE），用户可实时看到生成过程
- [ ] **GEN-07**: 系统支持多轮对话，理解上下文指代

### User Interface (UI)

- [ ] **UI-01**: 用户可通过Web界面进行自然语言问答，答案支持Markdown渲染和流式显示
- [ ] **UI-02**: 用户可点击答案中的来源引用，查看源文档片段详情（标题、章节、作者、日期）
- [ ] **UI-03**: 用户可对答案进行点赞/点踩反馈
- [ ] **UI-04**: 用户可查看对话历史记录
- [ ] **UI-05**: 管理员可通过Web管理后台创建/编辑/删除项目，配置数据源
- [ ] **UI-06**: 管理员可查看同步任务状态、手动触发同步
- [ ] **UI-07**: 管理员可管理用户权限（基于角色的访问控制）

### Authentication & Authorization (AUTH)

- [ ] **AUTH-01**: 用户可通过JWT Token进行认证登录
- [ ] **AUTH-02**: 系统实现RBAC权限模型（系统管理员、项目管理员、知识库管理员、普通用户、只读用户）
- [ ] **AUTH-03**: 系统实现项目级数据隔离：检索时自动附加用户所属项目的过滤条件
- [ ] **AUTH-04**: 系统API通过中间件自动注入用户的项目权限上下文

### Infrastructure (INFRA)

- [ ] **INFRA-01**: 系统可通过Docker Compose一键部署全部服务
- [ ] **INFRA-02**: 系统包含健康检查和优雅关闭机制
- [ ] **INFRA-03**: 系统实现结构化日志（JSON格式，支持关联ID追踪）
- [ ] **INFRA-04**: 系统配置通过环境变量和YAML配置文件管理，支持不同环境（开发/测试/生产）

## v2 Requirements

### Advanced Features

- **ADV-01**: 支持PPT文档解析（提取文本框+备注+表格）
- **ADV-02**: 支持图片OCR文字提取
- **ADV-03**: 支持钉钉机器人集成，在钉钉群内直接问答
- **ADV-04**: 支持相似问题推荐
- **ADV-05**: 支持查询意图识别和问题改写

### Evaluation & Monitoring

- **EVAL-01**: RAGAS自动化评估管道（Faithfulness/Answer Relevancy/Context Precision/Context Recall）
- **EVAL-02**: BadCase管理流程（收集→分类→分析→优化→验证）
- **EVAL-03**: Prometheus + Grafana监控仪表盘（准确率、满意度、延迟等核心指标）
- **EVAL-04**: 质量监控仪表盘（系统级和项目级视图）

### V2+ Features (Deferred)

- **KNOW-01**: 知识图谱增强（GraphRAG）
- **KNOW-02**: Agentic深度搜索（自主分解复杂问题）
- **KNOW-03**: 智能代码生成（基于项目知识库）
- **KNOW-04**: 技术文档自动生成
- **KNOW-05**: 会议纪要自动生成
- **KNOW-06**: 多模态问答（图片/表格/流程图理解）

## Out of Scope

| Feature | Reason |
|---------|--------|
| 文档创建/编辑/审批 | 不替代现有文档管理系统，仅做知识检索层 |
| 实时协作编辑 | 非本系统职责，增加复杂度无收益 |
| 通用聊天机器人 | 仅回答项目知识相关问题，闲聊/天气等不处理 |
| 代码生成/执行 | V2阶段支持，V1聚焦精准QA |
| 自动文档生成 | V2阶段支持 |
| 涉密/机密信息处理 | 系统不存储机密文档 |
| 移动App | 响应式Web + 钉钉机器人提供移动端访问 |
| 插件/扩展市场 | 过度抽象，核心功能稳定后再考虑 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONN-01 | Phase 2 | Pending |
| CONN-02 | Phase 3 | Pending |
| CONN-03 | Phase 3 | Pending |
| CONN-04 | Phase 3 | Pending |
| CONN-05 | Phase 2 | Pending |
| CONN-06 | Phase 2 | Pending |
| CONN-07 | Phase 3 | Pending |
| PROC-01 | Phase 2 | Pending |
| PROC-02 | Phase 2 | Pending |
| PROC-03 | Phase 2 | Pending |
| PROC-04 | Phase 2 | Pending |
| PROC-05 | Phase 2 | Pending |
| PROC-06 | Phase 2 | Pending |
| PROC-07 | Phase 2 | Pending |
| PROC-08 | Phase 2 | Pending |
| RETR-01 | Phase 2 | Pending |
| RETR-02 | Phase 2 | Pending |
| RETR-03 | Phase 4 | Pending |
| RETR-04 | Phase 4 | Pending |
| RETR-05 | Phase 4 | Pending |
| RETR-06 | Phase 4 | Pending |
| RETR-07 | Phase 4 | Pending |
| RETR-08 | Phase 4 | Pending |
| GEN-01 | Phase 5 | Pending |
| GEN-02 | Phase 5 | Pending |
| GEN-03 | Phase 5 | Pending |
| GEN-04 | Phase 5 | Pending |
| GEN-05 | Phase 5 | Pending |
| GEN-06 | Phase 5 | Pending |
| GEN-07 | Phase 5 | Pending |
| UI-01 | Phase 7 | Pending |
| UI-02 | Phase 7 | Pending |
| UI-03 | Phase 7 | Pending |
| UI-04 | Phase 7 | Pending |
| UI-05 | Phase 6 | Pending |
| UI-06 | Phase 6 | Pending |
| UI-07 | Phase 6 | Pending |
| AUTH-01 | Phase 6 | Pending |
| AUTH-02 | Phase 6 | Pending |
| AUTH-03 | Phase 6 | Pending |
| AUTH-04 | Phase 6 | Pending |
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 44 total
- Mapped to phases: 44
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-13*
*Last updated: 2026-05-13 after initial definition*
