# Tasks

## P0: 基础架构搭建

- [x] Task 1: 项目工程初始化
  - [x] SubTask 1.1: 创建Python项目结构（src/目录分层：api、core、models、services、connectors、pipeline、retrieval、generator）
  - [x] SubTask 1.2: 初始化pyproject.toml，配置依赖管理（FastAPI、uvicorn、sqlalchemy、celery、redis等）
  - [x] SubTask 1.3: 配置Git仓库和.gitignore
  - [x] SubTask 1.4: 创建配置管理模块（基于pydantic-settings，支持环境变量和.yaml配置文件）

- [x] Task 2: Docker Compose开发环境搭建
  - [x] SubTask 2.1: 编写docker-compose.yml，定义Milvus、Elasticsearch、PostgreSQL、Redis、MinIO服务
  - [x] SubTask 2.2: 编写各服务的配置文件（Milvus milvus.yaml、ES elasticsearch.yml、PostgreSQL init.sql、Redis redis.conf）
  - [x] SubTask 2.3: 编写.env.example环境变量模板
  - [x] SubTask 2.4: 验证所有基础设施服务可正常启动和连接

- [x] Task 3: PostgreSQL数据库Schema设计与初始化
  - [x] SubTask 3.1: 设计用户表（users）、项目表（projects）、项目成员表（project_members）、角色表（roles）
  - [x] SubTask 3.2: 设计数据源配置表（data_sources）、同步任务表（sync_tasks）、同步日志表（sync_logs）
  - [x] SubTask 3.3: 设计文档元数据表（documents）、对话表（conversations）、消息表（messages）、反馈表（feedbacks）
  - [x] SubTask 3.4: 使用Alembic创建数据库迁移脚本
  - [x] SubTask 3.5: 编写SQLAlchemy模型定义

- [x] Task 4: Milvus Collection设计
  - [x] SubTask 4.1: 定义文档块向量Collection Schema（doc_id、chunk_id、project_id、content向量1024维、元数据字段）
  - [x] SubTask 4.2: 配置Partition Key按project_id分区
  - [x] SubTask 4.3: 创建HNSW索引（M=16, efConstruction=256）
  - [x] SubTask 4.4: 编写Milvus连接和Collection管理工具模块

- [x] Task 5: Elasticsearch Index Mapping设计
  - [x] SubTask 5.1: 定义文档索引Mapping（content使用ik_max_word分词、project_id、doc_id、chunk_id、元数据字段）
  - [x] SubTask 5.2: 创建Index模板，支持按project_id路由
  - [x] SubTask 5.3: 编写Elasticsearch连接和索引管理工具模块

- [x] Task 6: FastAPI应用框架搭建
  - [x] SubTask 6.1: 创建FastAPI应用实例，配置CORS、异常处理中间件、请求日志中间件
  - [x] SubTask 6.2: 搭建API路由结构（/api/v1/auth、/api/v1/projects、/api/v1/datasources、/api/v1/knowledge、/api/v1/chat、/api/v1/admin）
  - [x] SubTask 6.3: 实现JWT认证中间件和权限校验装饰器
  - [x] SubTask 6.4: 实现统一响应格式和错误码定义
  - [x] SubTask 6.5: 实现API请求参数校验（Pydantic Model）

- [x] Task 7: 统一元数据Schema定义
  - [x] SubTask 7.1: 定义DocumentChunk Pydantic模型（doc_id、source、source_id、project_id、title、chunk_id、content、chunk_type、author、created_at、modified_at、file_path、file_size、mime_type、checksum、parent_title、hierarchy）
  - [x] SubTask 7.2: 定义各数据源的原始元数据到统一Schema的转换映射
  - [x] SubTask 7.3: 编写Schema验证工具

## P1: 数据源接入

- [x] Task 8: 数据源Connector基类与框架
  - [x] SubTask 8.1: 定义BaseConnector抽象基类（connect、list_changes、download、disconnect方法）
  - [x] SubTask 8.2: 实现Connector注册和工厂模式
  - [x] SubTask 8.3: 实现同步任务调度框架（Celery + Redis Streams）
  - [x] SubTask 8.4: 实现增量同步逻辑（变更检测、内容哈希去重）

- [x] Task 9: 钉钉Connector开发
  - [x] SubTask 9.1: 实现钉钉API认证模块（access_token获取和缓存）
  - [x] SubTask 9.2: 实现知识库文档列表获取和内容下载
  - [x] SubTask 9.3: 实现dingtalk-workspace-cli备用方案（subprocess调用dws命令）
  - [x] SubTask 9.4: 实现增量同步（基于modifiedTime检测变更）

- [x] Task 10: Seafile Connector开发
  - [x] SubTask 10.1: 实现Seafile API Token认证
  - [x] SubTask 10.2: 实现资料库目录递归遍历和文件下载
  - [x] SubTask 10.3: 实现增量同步（基于mtime时间戳检测变更）

- [x] Task 11: NAS Connector开发
  - [x] SubTask 11.1: 实现SMB/CIFS协议访问（pysmb库）
  - [x] SubTask 11.2: 实现NFS挂载后文件操作
  - [x] SubTask 11.3: 实现WebDAV协议访问
  - [x] SubTask 11.4: 实现watchdog文件变更事件监听

- [x] Task 12: 本地文件Connector开发
  - [x] SubTask 12.1: 实现本地目录扫描和文件列表获取
  - [x] SubTask 12.2: 实现watchdog实时监听文件创建、修改、删除事件
  - [x] SubTask 12.3: 实现目录白名单配置

- [x] Task 13: 同步状态监控与异常告警
  - [x] SubTask 13.1: 实现同步任务状态记录和查询
  - [x] SubTask 13.2: 实现同步异常捕获和重试机制
  - [x] SubTask 13.3: 实现同步状态监控API

- [x] Task 14: 数据源管理API
  - [x] SubTask 14.1: 实现数据源CRUD API端点
  - [x] SubTask 14.2: 实现数据源连接测试API
  - [x] SubTask 14.3: 实现手动触发同步API

## P2: 文档处理管道

- [x] Task 15: 文档解析器框架
  - [x] SubTask 15.1: 定义BaseParser抽象基类（parse方法，输入文件路径，输出ParsedDocument）
  - [x] SubTask 15.2: 实现Parser工厂模式，根据文件扩展名/MIME类型自动选择解析器
  - [x] SubTask 15.3: 实现文本清洗模块（去除页眉页脚、水印、特殊字符）

- [x] Task 16: PDF解析器开发
  - [x] SubTask 16.1: 集成MinerU/PyMuPDF实现原生PDF文本和结构提取
  - [x] SubTask 16.2: 集成PaddleOCR实现扫描件PDF文字识别
  - [x] SubTask 16.3: 实现PDF表格单独提取和公式转LaTeX

- [x] Task 17: Office文档解析器开发
  - [x] SubTask 17.1: 实现Word解析器（python-docx + Unstructured，提取段落+表格+标题层级）
  - [x] SubTask 17.2: 实现Excel解析器（pandas + openpyxl，表格转Markdown/文本描述，多Sheet分别处理）
  - [x] SubTask 17.3: 实现PPT解析器（python-pptx + Unstructured，提取文本框+备注+表格）
  - [x] SubTask 17.4: 实现旧格式.doc文件通过LibreOffice转docx后处理

- [x] Task 18: Markdown/纯文本解析器开发
  - [x] SubTask 18.1: 实现Markdown解析器（保留标题层级和代码块）
  - [x] SubTask 18.2: 实现纯文本解析器（按段落分割，编码自动检测）

- [x] Task 19: 中文智能分块引擎开发
  - [x] SubTask 19.1: 实现结构感知粗分（按H1/H2/H3标题层级切分为章节级大块）
  - [x] SubTask 19.2: 实现递归字符细分（分隔符优先级：\n\n > \n > 。> ！> ？> ；> ，> 空格）
  - [x] SubTask 19.3: 实现块大小约束（目标500-1000字符，重叠100-200字符）
  - [x] SubTask 19.4: 实现语义完整性检查（jieba分词检查块边界是否截断完整词语）
  - [x] SubTask 19.5: 实现不同文档类型的分块策略配置（技术文档/方案文档/会议纪要/表格/FAQ）

- [x] Task 20: 元数据提取器开发
  - [x] SubTask 20.1: 实现文档级元数据提取（标题、作者、日期）
  - [x] SubTask 20.2: 实现项目归属识别（基于数据源路径或配置映射）
  - [x] SubTask 20.3: 实现标题层级路径（hierarchy）提取

- [x] Task 21: Embedding服务部署与集成
  - [x] SubTask 21.1: 部署bge-large-zh-v1.5模型（基于sentence-transformers或vLLM）
  - [x] SubTask 21.2: 实现Embedding服务客户端（批量向量化接口，支持缓存）

- [x] Task 22: 向量化与索引构建管道
  - [x] SubTask 22.1: 实现Milvus向量写入模块（批量upsert，含元数据）
  - [x] SubTask 22.2: 实现Elasticsearch索引构建模块（批量index，含ik分词）
  - [x] SubTask 22.3: 实现端到端文档处理管道编排（下载→解析→清洗→分块→元数据→向量化→索引写入）
  - [x] SubTask 22.4: 实现管道Celery Worker集成

## P3: 检索引擎

- [x] Task 23: Milvus向量检索接口封装
  - [x] SubTask 23.1: 实现向量相似度检索（ANN，Top-K，余弦相似度）
  - [x] SubTask 23.2: 实现project_id Partition Key过滤
  - [x] SubTask 23.3: 实现元数据过滤（文档类型、时间范围等）

- [x] Task 24: Elasticsearch BM25检索接口封装
  - [x] SubTask 24.1: 实现BM25关键词检索（ik_max_word分词，Top-K）
  - [x] SubTask 24.2: 实现project_id字段过滤
  - [x] SubTask 24.3: 实现复合查询（关键词+元数据过滤）

- [x] Task 25: RRF融合算法实现
  - [x] SubTask 25.1: 实现Reciprocal Rank Fusion算法（k=60）
  - [x] SubTask 25.2: 实现多路检索结果合并和去重

- [x] Task 26: Rerank服务部署与集成
  - [x] SubTask 26.1: 部署bge-reranker-v2-m3模型
  - [x] SubTask 26.2: 实现Cross-Encoder重排序模块（Top-30→Top-10）
  - [x] SubTask 26.3: 实现相关性阈值过滤（分数<0.3剔除）

- [x] Task 27: 查询优化模块
  - [x] SubTask 27.1: 实现查询意图识别（事实查询/方案查询/对比查询/流程查询）
  - [x] SubTask 27.2: 实现Query改写（LLM将口语化问题改写为检索Query）
  - [x] SubTask 27.3: 实现HyDE假设性文档嵌入
  - [x] SubTask 27.4: 实现多查询扩展（复杂问题分解为子查询）

- [x] Task 28: 混合检索编排器
  - [x] SubTask 28.1: 实现检索编排主流程（查询理解→多路检索→RRF融合→Rerank→阈值过滤）
  - [x] SubTask 28.2: 实现项目范围限定逻辑
  - [x] SubTask 28.3: 实现检索结果标准化输出

## P4: 问答引擎

- [x] Task 29: LLM推理服务部署
  - [x] SubTask 29.1: 部署Qwen2.5-72B-Instruct（vLLM加速推理）
  - [x] SubTask 29.2: 实现LLM服务客户端（支持同步和流式调用，兼容OpenAI API格式）

- [x] Task 30: System Prompt设计与实现
  - [x] SubTask 30.1: 设计核心System Prompt模板（强制引用来源、不确定时拒绝回答、矛盾时指出）
  - [x] SubTask 30.2: 实现Prompt模板管理（支持版本控制和A/B测试）

- [x] Task 31: 上下文构建模块
  - [x] SubTask 31.1: 实现检索结果到结构化上下文的组装（[来源N]格式，含元数据）
  - [x] SubTask 31.2: 实现上下文长度控制（Token计数和截断策略）

- [x] Task 32: 答案生成模块
  - [x] SubTask 32.1: 实现同步答案生成接口
  - [x] SubTask 32.2: 实现流式答案生成（SSE输出）
  - [x] SubTask 32.3: 实现答案后处理（引用验证、置信度评估、低置信度标记）

- [x] Task 33: 多轮对话管理
  - [x] SubTask 33.1: 实现会话创建和上下文记忆管理
  - [x] SubTask 33.2: 实现上下文指代消解（LLM辅助理解指代）

- [x] Task 34: 问答API端点开发
  - [x] SubTask 34.1: 实现对话API（POST /api/v1/chat，支持流式SSE）
  - [x] SubTask 34.2: 实现对话历史API（GET /api/v1/chat/history）
  - [x] SubTask 34.3: 实现反馈API（POST /api/v1/chat/feedback）

- [x] Task 35: 反幻觉策略集成
  - [x] SubTask 35.1: 集成检索层防御（混合检索+Rerank+阈值过滤）
  - [x] SubTask 35.2: 集成生成层防御（强制引用+拒绝回答+置信度评估）
  - [x] SubTask 35.3: 集成后处理层防御（引用验证+事实一致性检查）
  - [x] SubTask 35.4: 编写反幻觉策略端到端测试

## P5: 前端与管理后台

- [x] Task 36: React项目初始化
  - [x] SubTask 36.1: 创建Next.js项目，配置TypeScript、TailwindCSS、UI组件库
  - [x] SubTask 36.2: 搭建前端路由结构（/chat、/admin/projects、/admin/datasources、/admin/sync、/admin/users、/admin/dashboard）
  - [x] SubTask 36.3: 实现API客户端封装（axios/fetch，JWT Token管理）

- [x] Task 37: 对话界面开发
  - [x] SubTask 37.1: 实现对话消息列表组件（支持Markdown渲染、代码高亮）
  - [x] SubTask 37.2: 实现流式输出显示（SSE EventSource连接）
  - [x] SubTask 37.3: 实现来源引用展示组件（点击展开文档详情）
  - [x] SubTask 37.4: 实现用户反馈组件（点赞/点踩）
  - [x] SubTask 37.5: 实现对话输入框（支持Enter发送、Shift+Enter换行）

- [x] Task 38: 管理后台开发
  - [x] SubTask 38.1: 实现项目管理页面（项目CRUD、成员管理）
  - [x] SubTask 38.2: 实现数据源配置页面（数据源CRUD、连接测试）
  - [x] SubTask 38.3: 实现同步任务监控页面（同步状态、手动触发、日志查看）
  - [x] SubTask 38.4: 实现用户权限管理页面（角色分配、权限配置）
  - [x] SubTask 38.5: 实现质量监控仪表盘（核心指标图表、BadCase列表）

## P6: 测试与优化

- [x] Task 39: 评测体系搭建
  - [x] SubTask 39.1: 构建评测数据集（100+问答对，人工标注）
  - [x] SubTask 39.2: 搭建RAGAS自动化评估管道
  - [x] SubTask 39.3: 实现评估指标计算（Faithfulness、Answer Relevancy、Context Precision、Context Recall）

- [x] Task 40: 精度调优
  - [x] SubTask 40.1: 调优分块参数（块大小、重叠、分块策略）
  - [x] SubTask 40.2: 调优检索参数（Top-K、RRF k值、Rerank阈值）
  - [x] SubTask 40.3: 优化System Prompt模板
  - [x] SubTask 40.4: 在测试集上验证改进效果

- [x] Task 41: 性能测试与优化
  - [x] SubTask 41.1: 端到端响应时间测试（目标P95 <= 5秒）
  - [x] SubTask 41.2: 并发用户测试（目标 >= 50并发）
  - [x] SubTask 41.3: 实现查询结果缓存（Redis热点查询缓存）
  - [x] SubTask 41.4: 实现Embedding缓存

- [x] Task 42: 安全测试
  - [x] SubTask 42.1: 权限隔离测试（跨项目数据不可见）
  - [x] SubTask 42.2: 数据泄露测试（无权限用户无法访问受限内容）
  - [x] SubTask 42.3: API安全测试（认证、授权、输入校验）

## P7: 部署与上线

- [x] Task 43: 生产环境部署
  - [x] SubTask 43.1: 编写生产环境docker-compose.yml（含资源限制、健康检查、日志配置）
  - [x] SubTask 43.2: 编写部署脚本和运维文档
  - [x] SubTask 43.3: 配置HTTPS/TLS加密通信

- [x] Task 44: 监控体系搭建
  - [x] SubTask 44.1: 部署Prometheus + Grafana
  - [x] SubTask 44.2: 配置应用指标采集（FastAPI metrics、Celery metrics）
  - [x] SubTask 44.3: 创建监控仪表盘（系统健康、问答质量、同步状态）

- [x] Task 45: 钉钉机器人集成
  - [x] SubTask 45.1: 实现钉钉机器人Webhook接收和回复
  - [x] SubTask 45.2: 实现钉钉群内直接问答功能

# Task Dependencies

- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 2]
- [Task 4] depends on [Task 2]
- [Task 5] depends on [Task 2]
- [Task 6] depends on [Task 1]
- [Task 7] depends on [Task 1]
- [Task 8] depends on [Task 6, Task 7]
- [Task 9] depends on [Task 8]
- [Task 10] depends on [Task 8]
- [Task 11] depends on [Task 8]
- [Task 12] depends on [Task 8]
- [Task 13] depends on [Task 8]
- [Task 14] depends on [Task 6]
- [Task 15] depends on [Task 7]
- [Task 16] depends on [Task 15]
- [Task 17] depends on [Task 15]
- [Task 18] depends on [Task 15]
- [Task 19] depends on [Task 15]
- [Task 20] depends on [Task 15]
- [Task 21] depends on [Task 2]
- [Task 22] depends on [Task 19, Task 20, Task 21, Task 4, Task 5]
- [Task 23] depends on [Task 22]
- [Task 24] depends on [Task 22]
- [Task 25] depends on [Task 23, Task 24]
- [Task 26] depends on [Task 2]
- [Task 27] depends on [Task 29]
- [Task 28] depends on [Task 25, Task 26, Task 27]
- [Task 29] depends on [Task 2]
- [Task 30] depends on [Task 29]
- [Task 31] depends on [Task 28]
- [Task 32] depends on [Task 30, Task 31]
- [Task 33] depends on [Task 29]
- [Task 34] depends on [Task 32, Task 33]
- [Task 35] depends on [Task 28, Task 32]
- [Task 36] depends on [Task 34]
- [Task 37] depends on [Task 36, Task 34]
- [Task 38] depends on [Task 36, Task 14]
- [Task 39] depends on [Task 34]
- [Task 40] depends on [Task 39]
- [Task 41] depends on [Task 37]
- [Task 42] depends on [Task 37]
- [Task 43] depends on [Task 40, Task 41, Task 42]
- [Task 44] depends on [Task 43]
- [Task 45] depends on [Task 34]
