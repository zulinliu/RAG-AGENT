# RAG-AGENT — 企业多源项目知识问答系统

基于 RAG（检索增强生成）架构的企业级知识问答系统，整合钉钉知识库、Seafile、NAS、本地文件等多数据源项目材料，通过自然语言交互为项目成员提供精准、可追溯的知识问答服务。

## 项目亮点

### 核心特性

- **精准问答** — 目标准确率 >= 90%，幻觉率 <= 5%，每个回答附带来源文档引用
- **多源整合** — 钉钉知识库、Seafile、NAS（NFS/SMB/WebDAV）、本地文件一站式接入
- **中文优化** — 专用中文分块引擎（结构感知 + jieba边界保护）、bge-large-zh-v1.5 Embedding、ik_max_word中文分词
- **混合检索** — BM25关键词检索 + 向量语义检索 + RRF融合 + Cross-Encoder重排序
- **多层反幻觉** — 检索过滤 → CRAG自校正循环 → 强制引用 → 引用验证 → 置信度评估（5层防御）
- **项目隔离** — RBAC权限模型 + Milvus Partition Key项目级数据隔离
- **流式输出** — SSE实时流式响应，Markdown渲染 + 代码高亮
- **私有部署** — 全链路私有化，数据不出域，Docker Compose一键部署

### 技术架构

```
┌──────────────────────────────────────────────────────────┐
│                    Frontend (React/Next.js)               │
├──────────────────────────────────────────────────────────┤
│                    API Gateway (FastAPI)                  │
├──────────┬──────────┬───────────┬────────────────────────┤
│ Auth/RBAC│ Project  │   QA      │  Document Management   │
├──────────┴──────────┴───────────┴────────────────────────┤
│              RAG Engine (LangGraph CRAG Pipeline)         │
│  Query Understanding → Hybrid Retrieval → RRF → Rerank  │
│  → Document Grading → Generate → Citation Verify         │
├──────────────────────────────────────────────────────────┤
│           Document Processing Pipeline                    │
│  Parse → Clean → Chunk → Embed(bge-large-zh) → Dual-Index│
├──────────────────────────────────────────────────────────┤
│        Data Source Connectors                             │
│  DingTalk │ Seafile │ NAS │ Local Files                   │
├──────────────────────────────────────────────────────────┤
│  PostgreSQL │ Milvus 2.6 │ Elasticsearch 8.19 │ Redis 7  │
└──────────────────────────────────────────────────────────┘
```

## 系统要求

### 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 8核 | 16核+ |
| 内存 | 32GB | 64GB+ |
| GPU | 无（可用API替代LLM） | 4xA100 80GB（私有部署LLM） |
| 存储 | 100GB SSD | 500GB+ NVMe |

### 软件要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Docker | 27.x+ | 容器运行时 |
| Docker Compose | 2.x+ | 容器编排 |
| Python | 3.11+ | 后端运行时 |
| Node.js | 20.x+ | 前端构建 |
| NVIDIA Driver | 535+ | GPU驱动（私有部署LLM时需要） |
| CUDA | 12.x | GPU计算（私有部署LLM时需要） |

### 核心技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端框架 | FastAPI + Pydantic v2 | 0.136+ / 2.13+ |
| 前端框架 | React + Next.js + Tailwind CSS | 19 / 15 / 4 |
| LLM | Qwen2.5-72B-Instruct (vLLM) | 0.20+ |
| Embedding | bge-large-zh-v1.5 | 1024维 |
| Rerank | bge-reranker-v2-m3 | Cross-Encoder |
| 向量数据库 | Milvus | 2.6.x |
| 全文检索 | Elasticsearch | 8.19.x |
| 关系数据库 | PostgreSQL | 17.x |
| 缓存/队列 | Redis | 7.x |
| 对象存储 | MinIO | latest |
| 文档解析 | MinerU + PaddleOCR + Unstructured | 1.3+ / 3.5+ / 0.22+ |
| 工作流 | LangGraph | 1.2+ |
| 任务队列 | Celery | 5.6+ |

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url> rag-agent
cd rag-agent
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库密码、JWT密钥等
vim .env
```

**必须修改的配置项：**

```env
# JWT密钥（生产环境必须更换！）
AUTH_SECRET_KEY=your-secret-key-change-this-in-production

# 数据库密码
DB_PASSWORD=your-secure-password

# Redis密码
REDIS_PASSWORD=your-redis-password

# 初始化管理员密码（scripts/init-db.sh 必需）
ADMIN_PASSWORD=your-admin-password
```

### 3. 一键启动（Docker Compose）

```bash
# 启动所有基础设施服务
docker compose up -d

# 等待服务就绪（约30秒）
# 初始化数据库和索引
bash scripts/init-db.sh
bash scripts/init-es.sh
python scripts/init-milvus.py
```

### 4. 启动后端

```bash
cd backend

# 安装依赖（开发环境）
pip install -e ".[dev]"

# 运行数据库迁移
alembic upgrade head

# 启动开发服务器
python run.py
```


### 4.1 启动 Celery Worker（文档处理等异步任务）

后端启动后，还需启动 Celery Worker 和 Beat 进程来处理文档同步等异步任务：

```bash
cd backend

# 启动 Celery Worker（处理异步任务）
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2

# 另开终端，启动 Celery Beat（定时任务调度）
celery -A app.tasks.celery_app beat --loglevel=info
```

> Docker Compose 部署时，Worker 和 Beat 已包含在编排中，无需手动启动。

### 5. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 6. 访问系统

- 前端界面：http://localhost:3000
- 后端API文档：http://localhost:8000/docs
- 管理员账号由 `.env` 中的 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 创建；使用 `.env.example` 默认值时为 `admin / admin123`。

### 7. LLM / Embedding / Reranker 模型配置

所有 AI 模型均支持 **本地 Docker 部署** 和 **第三方云 API** 两种方式，通过 `.env` 中的 `*_PROVIDER` 一键切换，无需改代码。

#### 7.1 Embedding & Reranker 本地部署（CPU，零 GPU 需求）

`docker-compose.yml` 内置了两个 HuggingFace TEI 容器：

| 服务 | 模型 | 参数量 | 镜像 | CPU 内存 | 端口 |
|------|------|--------|------|---------|------|
| `embedding-worker` | BAAI/bge-large-zh-v1.5 | ~326M | `ghcr.io/huggingface/text-embeddings-inference:cpu-latest` | ~3 GB | 8100 |
| `reranker-worker` | BAAI/bge-reranker-v2-m3 | ~568M | `ghcr.io/huggingface/text-embeddings-inference:cpu-latest` | ~3 GB | 8101 |

首次启动自动从 HuggingFace 下载模型（约 2.3 GB），后续启动使用缓存，几秒内就绪。

**无需任何额外配置**，默认 `.env` 已指向本地 TEI 服务：

```env
EMBEDDING_PROVIDER=tei          # 本地 TEI Docker
RERANKER_PROVIDER=tei           # 本地 TEI Docker
```

CPU 推理性能：Embedding ~100-300ms/批次(32条)，Reranker ~150-500ms/批次(50条)，50-200 人规模下完全够用。

#### 7.2 LLM 配置

**方式一：本地 vLLM 私有部署（需 GPU）**

```bash
# GPU服务器上启动vLLM
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-72B-Instruct \
  --tensor-parallel-size 4 \
  --host 0.0.0.0 --port 8001
```

```env
LLM_PROVIDER=local
LLM_API_BASE=http://host.docker.internal:8001/v1  # Docker Compose 内访问宿主机 vLLM
LLM_MODEL_NAME=Qwen2.5-72B-Instruct
```

**方式二：第三方 API（免 GPU）**

系统通过 OpenAI 兼容协议支持所有主流国内大模型平台：

| 平台 | LLM_PROVIDER | LLM_MODEL_NAME | 获取API Key |
|------|-------------|----------------|------------|
| 智谱GLM | `zhipu` | `glm-4-plus` | [open.bigmodel.cn](https://open.bigmodel.cn) |
| DeepSeek | `deepseek` | `deepseek-chat` | [platform.deepseek.com](https://platform.deepseek.com) |
| MiniMax | `minimax` | `MiniMax-Text-01` | [api.minimax.chat](https://api.minimax.chat) |
| 硅基流动 | `siliconflow` | `Qwen/Qwen2.5-72B-Instruct` | [cloud.siliconflow.cn](https://cloud.siliconflow.cn) |
| 通义千问 | `openai` | `qwen-plus` | [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com) |
| Ollama本地 | `ollama` | `qwen2.5:72b` | 无需 |
| NewAPI中转 | `openai` | 按中转平台配置 | 使用中转平台Key |

> `LLM_API_BASE` 在选择已知 provider 时会自动填充，无需手动设置。仅 `custom` 模式需手动指定。

配置示例（智谱GLM）：
```env
LLM_PROVIDER=zhipu
LLM_API_KEY=your-zhipu-api-key
LLM_MODEL_NAME=glm-4-plus
```

配置示例（公司 NewAPI 中转）：
```env
LLM_PROVIDER=openai
LLM_API_KEY=your-relay-api-key
LLM_API_BASE=https://your-newapi-domain.com/v1
LLM_MODEL_NAME=glm-4-plus
```

#### 7.3 Embedding 配置

| Provider | 说明 | 需要GPU |
|----------|------|---------|
| `tei` | 本地 TEI Docker（默认，推荐） | 否 |
| `siliconflow` | 硅基流动 API（同款 bge 模型） | 否 |
| `zhipu` | 智谱AI Embedding-3 | 否 |
| `openai` | OpenAI 兼容中转 | 否 |
| `custom` | 自定义 OpenAI 兼容端点 | 否 |
| `local-py` | 进程内 transformers 加载（开发） | 可选 |

```env
# 默认：本地 TEI Docker
EMBEDDING_PROVIDER=tei

# 切换到硅基流动 API（零部署）
EMBEDDING_PROVIDER=siliconflow
EMBEDDING_API_KEY=your-siliconflow-api-key

# 切换到智谱AI（注意维度不同）
EMBEDDING_PROVIDER=zhipu
EMBEDDING_API_KEY=your-zhipu-api-key
EMBEDDING_MODEL_NAME=embedding-3
EMBEDDING_DIMENSION=2048
```

#### 7.4 Reranker 配置

| Provider | 说明 | 需要GPU |
|----------|------|---------|
| `tei` | 本地 TEI Docker（默认，推荐） | 否 |
| `siliconflow` | 硅基流动 API | 否 |
| `custom` | 自定义端点 | 否 |
| `local-py` | 进程内加载（开发） | 可选 |

```env
# 默认：本地 TEI Docker
RERANKER_PROVIDER=tei

# 切换到硅基流动 API
RERANKER_PROVIDER=siliconflow
RERANKER_API_KEY=your-siliconflow-api-key
```

#### 7.5 配置切换总结

只需修改 `.env` 中的 3 个 PROVIDER 变量即可在本地/云端之间切换，所有服务自动适配请求格式：

| 场景 | LLM_PROVIDER | EMBEDDING_PROVIDER | RERANKER_PROVIDER |
|------|-------------|-------------------|-------------------|
| 全本地（默认） | `local` | `tei` | `tei` |
| 全云端（零GPU） | `zhipu` | `siliconflow` | `siliconflow` |
| 混合模式 | `zhipu` | `tei` | `tei` |
| 中转平台 | `openai` | `openai` | `custom` |

## 配置文件详解

### 环境变量配置 (.env)

完整配置模板见 `.env.example`，所有 `*_PROVIDER` 变量控制本地/云端切换：

```env
# ==================== 基础配置 ====================
ENVIRONMENT=dev                    # 运行环境: dev / test / prod
LOG_LEVEL=INFO                     # 日志级别
CORS_ORIGINS=http://localhost:3000 # 允许的前端域名（逗号分隔）

# ==================== PostgreSQL ====================
DB_HOST=postgres
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres               # 生产环境必须更换！
DB_DATABASE=rag_agent

# ==================== Redis ====================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=ragagent123          # 生产环境必须更换！

# ==================== Milvus ====================
MILVUS_HOST=milvus-standalone
MILVUS_PORT=19530

# ==================== Elasticsearch ====================
ES_HOSTS=http://elasticsearch:9200

# ==================== MinIO ====================
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin         # 生产环境必须更换！
MINIO_SECRET_KEY=minioadmin         # 生产环境必须更换！
MINIO_BUCKET=rag-docs

# ==================== LLM ====================
# 已知 provider 会自动填充 API_BASE；Docker Compose 本地 vLLM 默认使用 host.docker.internal:8001
LLM_PROVIDER=local                  # local/zhipu/deepseek/minimax/siliconflow/ollama/openai/custom
LLM_API_KEY=                        # 第三方API密钥（本地部署无需）
LLM_API_BASE=                       # custom 或特殊网络拓扑时手动设置
LLM_MODEL_NAME=Qwen2.5-72B-Instruct
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.1

# ==================== Embedding ====================
EMBEDDING_PROVIDER=tei              # tei/siliconflow/zhipu/openai/custom/local-py
EMBEDDING_API_KEY=                  # 第三方API密钥（TEI本地无需）
EMBEDDING_MODEL_NAME=BAAI/bge-large-zh-v1.5
EMBEDDING_DIMENSION=1024

# ==================== Reranker ====================
RERANKER_PROVIDER=tei               # tei/siliconflow/custom/local-py
RERANKER_API_KEY=                   # 第三方API密钥（TEI本地无需）
RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3
RERANKER_THRESHOLD=0.3

# ==================== 认证 ====================
AUTH_SECRET_KEY=                    # JWT密钥（生产环境不少于32字符）
```

### Docker Compose 配置

- `docker-compose.yml` — 开发环境配置
- `docker-compose.prod.yml` — 生产环境覆盖（资源限制、日志轮转）

```bash
# 开发环境
docker compose up -d

# 生产环境
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Elasticsearch 索引配置

`config/elasticsearch/mappings.json` 定义了 `rag_chunks` 索引：
- 使用 `ik_max_word` 分词器（中文最佳实践）
- 1主分片 + 1副本
- 包含15个字段（project_id、content、title、author等）
- 若部署环境未安装 IK 插件，初始化脚本和运行时索引创建会自动回退到 standard analyzer，保证系统可启动；生产环境仍建议安装 IK 以提升中文 BM25 效果。

### Milvus Collection 配置

`config/milvus/collection.py` 定义了 `rag_chunks` Collection：
- `project_id` 作为 Partition Key（项目级数据隔离）
- `vector` 字段：FLOAT_VECTOR(1024)，HNSW索引（M=16, efConstruction=256, COSINE）
- 支持按project_id分区查询

## 使用说明

### 创建项目和数据源

1. 登录系统后，进入**管理后台 → 项目管理**
2. 点击**创建项目**，填写项目名称和描述
3. 进入项目详情，添加数据源：
   - **本地文件**：指定服务器上的目录路径，系统自动监控文件变更
   - **钉钉知识库**：API模式填入 AppKey、AppSecret、知识库空间 ID；也可配置 CLI 模式
   - **Seafile**：填入服务器地址、Access Token、资料库ID
   - **NAS**：选择协议（NFS/SMB/WebDAV），填入地址、远程路径和认证信息
4. 点击**测试连接**确认连通性
5. 点击**开始同步**，系统自动下载、解析、分块、索引文档

### 知识问答

1. 在**对话界面**选择要查询的项目
2. 用自然语言提问，例如：
   - "XX项目的系统架构设计方案是什么？"
   - "为什么选择了A技术方案而不是B？"
   - "上周评审会议的结论是什么？"
3. 系统返回答案并附带来源引用（可点击查看原文）
4. 对答案进行点赞/点踩反馈

### 用户权限管理

| 角色 | 权限 |
|------|------|
| 系统管理员 | 全部权限，管理所有项目 |
| 项目管理员 | 管理指定项目的知识库、成员、数据源 |
| 知识库管理员 | 管理指定项目的文档同步和索引 |
| 普通用户 | 对有权限的项目进行知识问答 |
| 只读用户 | 仅可查询，不可反馈 |

## 项目结构

```
RAG-AGENT/
├── backend/                    # Python后端
│   ├── app/
│   │   ├── api/                # API路由（auth/projects/datasources/documents/qa）
│   │   ├── connectors/         # 数据源连接器（dingtalk/seafile/nas/local）
│   │   ├── middleware/         # 中间件（auth/logging）
│   │   ├── models/             # SQLAlchemy数据模型
│   │   ├── processors/         # 文档处理（parser/chunker/embedding/indexer/pipeline）
│   │   ├── rag/                # RAG引擎（retriever/reranker/generator/graph）
│   │   ├── schemas/            # Pydantic请求/响应模型
│   │   ├── services/           # 业务服务（user/project/datasource/document/qa）
│   │   ├── tasks/              # Celery异步任务
│   │   └── utils/              # 工具（auth/logging/dedup）
│   ├── alembic/                # 数据库迁移
│   ├── pyproject.toml          # Python依赖
│   └── Dockerfile              # 后端Docker镜像
├── frontend/                   # React前端
│   ├── src/
│   │   ├── app/                # Next.js页面（chat/admin/login）
│   │   ├── components/         # UI组件（chat/admin/ui）
│   │   └── lib/                # 工具库（api/auth/store）
│   ├── package.json            # Node.js依赖
│   └── Dockerfile              # 前端Docker镜像
├── config/                     # 基础设施配置
│   ├── elasticsearch/          # ES索引映射
│   ├── milvus/                 # Milvus Collection初始化
│   ├── redis/                  # Redis配置
│   └── postgresql.conf         # PostgreSQL优化配置
├── docs/                       # 架构设计与评审整改记录
├── scripts/                    # 初始化脚本
├── docker-compose.yml          # 开发环境编排
├── docker-compose.prod.yml     # 生产环境覆盖
└── .env.example                # 环境变量模板
```

## 注意事项

### 安全

- **生产环境必须更换** `.env` 中的所有密码和密钥
- AUTH_SECRET_KEY 建议使用 `openssl rand -hex 32` 生成
- 系统默认关闭Elasticsearch安全模块（xpack.security.enabled=false），内网部署时可接受
- 所有API接口需要JWT Token认证（除 `/health`、`/api/v1/health` 和 `/api/v1/auth/login`）
- 数据按项目隔离，用户只能访问有权限的项目数据

### 性能

- **LLM推理是性能瓶颈**：首次提问较慢（模型加载），后续请求受益于vLLM的continuous batching
- **Embedding/Reranker 不需要 GPU**：bge-large-zh-v1.5 和 bge-reranker-v2-m3 模型很小（<600M 参数），CPU Docker 部署即可，50-200 人规模下性能充足
- **文档处理耗时**：PDF OCR处理每页约1-3秒，大文档建议在非工作时间全量同步
- **Milvus内存需求**：每100万1024维向量约需4GB内存

### 运维

- 定期检查Redis内存使用（`redis-cli info memory`）
- 监控Elasticsearch磁盘空间（日志和数据共用磁盘时注意）
- Milvus数据目录需要定期备份
- PostgreSQL建议配置主从复制（生产环境）
- MinIO建议配置多节点分布式模式（生产环境）

### 已知限制

- 钉钉API有调用频率限制（标准版1万次/月），建议使用CLI模式
- PPT和图片OCR需要额外GPU资源，V1阶段支持基础解析
- 多轮对话上下文窗口有限（最近5轮），超长对话会自动压缩
- 中文分块效果依赖文档结构质量，无标题层级的文档效果稍差

## 后续规划

### V2（预计 Q3 2026）

| 功能 | 描述 |
|------|------|
| PPT完整解析 | 提取文本框、备注、表格，图片用VLM描述 |
| 图片OCR | PaddleOCR深度集成，支持图片文字提取 |
| 钉钉机器人 | 在钉钉群内直接问答，无需打开Web |
| RAGAS评估管道 | 自动化Faithfulness/Relevancy评估 |
| BadCase管理增强 | 当前已有基础落库与解决状态，后续补齐前端管理、归因和优化验证闭环 |
| Grafana监控 | 准确率、满意度、延迟等核心指标仪表盘 |
| 知识图谱增强 | GraphRAG跨文档关联查询 |
| Agentic搜索 | Agent自主分解复杂问题，多步检索 |
| 智能代码生成 | 基于项目知识库生成代码片段 |

### V3（预计 Q1 2027）

| 功能 | 描述 |
|------|------|
| 技术文档自动生成 | 从代码生成API文档、架构图 |
| 会议纪要自动生成 | 从录音/速记生成结构化纪要 |
| 主动知识推送 | 根据工作场景主动推送相关知识 |
| 知识协作 | 用户对答案补充和纠错 |
| 跨项目知识发现 | 自动发现相似方案和最佳实践 |
| 项目报告自动生成 | 基于项目材料生成周报/月报 |

## 技术支持

- 项目方案文档：`企业多源项目知识问答Agent_项目方案.md`
- 架构设计说明：`docs/ARCHITECTURE.md`
- 评审整改记录：`docs/REVIEW_REMEDIATION.md`
- API文档：启动后端后访问 `http://localhost:8000/docs`
- 项目规划：`.planning/` 目录下的 ROADMAP.md 和 REQUIREMENTS.md

## 开源协议

内部项目，仅供公司内部使用。
