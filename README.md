# 企业多源项目知识问答Agent

> 基于 RAG 架构的企业级精准知识问答系统，整合钉钉知识库、Seafile、NAS、本地文件等多数据源，为项目团队提供精准、可追溯、反幻觉的知识问答服务。

---

## 目录

- [项目介绍](#项目介绍)
- [核心亮点](#核心亮点)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [配置文件详解](#配置文件详解)
- [使用说明](#使用说明)
- [注意事项](#注意事项)
- [后续规划](#后续规划)

---

## 项目介绍

### 背景

企业项目知识资产分散存储在钉钉知识库、Seafile 文件管理平台、NAS 网络存储、本地电脑等多个数据源中，项目成员在日常工作中面临：

- **知识检索效率低** — 跨多个平台手动查找资料，平均耗时 10-30 分钟/次
- **知识复用率差** — 已有方案和经验难以被及时发现和复用
- **新人培训成本高** — 新员工需要较长时间才能熟悉项目背景和历史决策
- **知识流失风险** — 核心人员离职后，项目知识难以完整传承
- **答案准确性无保障** — 通用大模型无法获取公司内部资料，容易产生幻觉

### 目标

构建一个企业级项目知识问答 Agent 系统，整合多数据源项目材料，提供精准、可靠、可追溯的知识问答服务。

| 核心目标 | 指标 |
|---------|------|
| 答案精准度 | 准确率 ≥ 90%，幻觉率 ≤ 5% |
| 答案可追溯性 | 每个回答附带来源文档引用 |
| 多数据源覆盖 | 钉钉、Seafile、NAS、本地文件 |
| 项目级隔离 | RBAC 权限控制，跨项目数据不可见 |
| 实时性 | 新文档 30 分钟内可被检索 |
| 响应速度 | 端到端 P95 ≤ 5 秒 |

### 适用场景

| 场景 | 典型问题 |
|------|---------|
| 方案查阅 | "XX 项目的系统架构设计方案是什么？" |
| 技术决策回溯 | "为什么 XX 项目选择了 A 技术方案而不是 B？" |
| 接口/规范查询 | "XX 项目的 API 接口规范文档在哪里？" |
| 问题排查 | "XX 项目上线时遇到过 XX 问题，当时是怎么解决的？" |
| 新人培训 | "XX 项目的技术栈和开发规范是什么？" |
| 会议纪要查询 | "上周 XX 项目的评审会议结论是什么？" |

---

## 核心亮点

### 1. 多层反幻觉机制

系统从检索层、生成层、后处理层、评估层四个维度构建了完整的反幻觉防线：

| 防御层 | 策略 | 效果 |
|-------|------|------|
| 检索层 | BM25 + 向量语义双路召回 + RRF 融合 + Cross-Encoder 精排 | 召回率 ≥ 85%，Top-1 准确率 ≥ 90% |
| 生成层 | 强制引用来源 + 上下文不足时拒绝回答 + 置信度评估 | 答案可追溯，避免编造 |
| 后处理层 | 引用验证（过滤虚假引用）+ 事实一致性检查 | 检测矛盾和虚假引用 |
| 评估层 | RAGAS 自动化评估 + BadCase 闭环管理 | 持续监控和改进 |

### 2. 中文深度优化的智能分块引擎

- **结构感知粗分** — 按标题层级（H1-H6）将文档切分为章节级大块
- **递归字符细分** — 中文分隔符优先级：`\n\n` > `\n` > `。` > `！` > `？` > `；` > `，` > 空格
- **语义完整性检查** — 使用 jieba 分词检测块边界是否截断完整词语
- **多策略预设** — 技术文档、方案文档、会议纪要、表格、FAQ 五种分块策略

### 3. 多数据源统一接入

- **钉钉知识库** — 支持 API 方式和 dingtalk-workspace-cli 方式双通道接入
- **Seafile** — 递归遍历资料库目录，基于 mtime 增量同步
- **NAS** — SMB/NFS/WebDAV 三协议支持，watchdog 准实时监听
- **本地文件** — watchdog 实时监听 + 目录白名单

### 4. 项目级数据隔离

- Milvus Partition Key 按 `project_id` 分区
- Elasticsearch 按 `project_id` 字段过滤
- PostgreSQL 查询自动附加项目条件
- API 中间件自动注入用户项目权限上下文

### 5. 完整的评估与监控闭环

- RAGAS 自动化评估（Faithfulness / Answer Relevancy / Context Precision / Context Recall）
- BadCase 收集 → 分类 → 分析 → 优化 → 验证闭环
- Prometheus + Grafana 监控仪表盘

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端展示层 (Next.js)                       │
│              Web 对话界面 / 管理后台 / 钉钉机器人                    │
├─────────────────────────────────────────────────────────────────┤
│                        接口层 (FastAPI)                           │
│              RESTful API / WebSocket SSE / 钉钉 Webhook          │
├─────────────────────────────────────────────────────────────────┤
│                      业务服务层                                   │
│         用户服务 / 项目管理 / 知识库管理 / 问答服务 / 评估服务        │
├─────────────────────────────────────────────────────────────────┤
│                    检索增强层 (RAG Engine)                        │
│      查询理解 → 多路检索 → RRF 融合 → Rerank → 答案生成 → 后处理     │
├─────────────────────────────────────────────────────────────────┤
│                    文档处理层                                     │
│         文档下载 → 格式识别 → 文档解析 → 文本清洗 → 智能分块 → 向量化  │
├─────────────────────────────────────────────────────────────────┤
│                   数据源接入层                                    │
│       钉钉 Connector / Seafile Connector / NAS Connector / Local │
├─────────────────────────────────────────────────────────────────┤
│                   基础设施层                                      │
│    Milvus / Elasticsearch / PostgreSQL / Redis / MinIO / vLLM    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 技术栈

| 技术层级 | 选型 | 说明 |
|---------|------|------|
| 后端框架 | Python 3.11 + FastAPI | AI/ML 生态丰富，异步高性能 |
| 前端框架 | React 18 + Next.js 14 | SSR 支持，组件生态丰富 |
| LLM 大模型 | Qwen2.5-72B-Instruct | 中文能力强，支持私有化部署 |
| Embedding | bge-large-zh-v1.5 (1024 维) | 中文效果优秀，开源免费 |
| Rerank | bge-reranker-v2-m3 | 中文多语言 Cross-Encoder |
| 向量数据库 | Milvus 2.6 | 分布式高性能，Partition Key 支持 |
| 全文检索 | Elasticsearch 8.x | BM25 + ik 中文分词 |
| 关系数据库 | PostgreSQL 16 | JSON 支持，pgvector 可复用 |
| 消息队列 | Redis Streams | 轻量级，适合文档同步任务 |
| 缓存 | Redis 7.x | 查询缓存 + Embedding 缓存 |
| 对象存储 | MinIO | 原始文档文件存储 |
| 文档解析 | PyMuPDF + python-docx + openpyxl + python-pptx | 多格式全覆盖 |
| OCR | PaddleOCR | 中文识别准确率高 |
| 任务调度 | Celery + Redis | 异步文档同步和处理 |
| 容器化 | Docker + Docker Compose | 初期简单，后续可迁移 K8s |
| 监控 | Prometheus + Grafana | 云原生标准监控方案 |

---

## 项目结构

```
├── backend/                          # 后端服务
│   ├── src/rag_qa/
│   │   ├── api/v1/                   # API 端点（auth/projects/datasources/chat/knowledge/admin）
│   │   ├── core/                     # 核心配置（config/security/exceptions）
│   │   ├── connectors/               # 数据源连接器（dingtalk/seafile/nas/local + registry）
│   │   ├── pipeline/                 # 文档处理管道
│   │   │   ├── parsers/              # 解析器（pdf/word/excel/ppt/markdown/text）
│   │   │   ├── chunker.py            # 中文智能分块引擎
│   │   │   ├── cleaner.py            # 文本清洗
│   │   │   ├── metadata_extractor.py # 元数据提取
│   │   │   └── indexer.py            # 索引构建（Embedding + Milvus + ES）
│   │   ├── retrieval/                # 检索引擎
│   │   │   ├── vector_retriever.py   # Milvus 向量检索
│   │   │   ├── bm25_retriever.py     # ES BM25 检索
│   │   │   ├── rrf_fusion.py         # RRF 融合算法
│   │   │   ├── reranker.py           # Cross-Encoder 重排序
│   │   │   ├── query_optimizer.py    # 查询优化（意图识别/改写/HyDE/扩展）
│   │   │   └── retriever.py          # 混合检索编排器
│   │   ├── generator/                # 答案生成引擎
│   │   │   ├── llm_client.py         # LLM 服务客户端（同步+流式）
│   │   │   ├── prompt_templates.py   # Prompt 模板管理
│   │   │   ├── context_builder.py    # 上下文构建
│   │   │   ├── answer_generator.py   # 答案生成（含流式输出）
│   │   │   ├── citation_verifier.py  # 引用验证
│   │   │   ├── confidence_scorer.py  # 置信度评估
│   │   │   └── session_manager.py    # 多轮对话管理
│   │   ├── evaluation/               # 评估体系
│   │   │   ├── evaluator.py          # RAGAS 自动化评估
│   │   │   └── badcase.py            # BadCase 管理
│   │   ├── integrations/             # 第三方集成
│   │   │   └── dingtalk_bot.py       # 钉钉机器人
│   │   ├── models/                   # SQLAlchemy 数据模型
│   │   ├── schemas/                  # Pydantic Schema
│   │   ├── services/                 # 业务服务层
│   │   ├── workers/                  # Celery Worker
│   │   └── db/                       # 数据库会话管理
│   ├── alembic/                      # 数据库迁移
│   ├── deploy/                       # 部署配置
│   │   ├── docker-compose.prod.yml   # 生产环境编排
│   │   ├── nginx/nginx.conf          # Nginx 反向代理
│   │   ├── monitoring/               # Prometheus + Grafana
│   │   ├── elasticsearch/            # ES 配置
│   │   ├── postgresql/               # PG 初始化
│   │   └── redis/                    # Redis 配置
│   ├── tests/                        # 测试用例
│   ├── docker-compose.yml            # 开发环境编排
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── .env.example
│
└── frontend/                         # 前端应用
    ├── src/
    │   ├── app/
    │   │   ├── chat/                 # 对话界面
    │   │   ├── login/                # 登录页面
    │   │   └── admin/                # 管理后台
    │   │       ├── projects/         # 项目管理
    │   │       ├── datasources/      # 数据源配置
    │   │       ├── sync/             # 同步监控
    │   │       ├── users/            # 权限管理
    │   │       └── dashboard/        # 质量仪表盘
    │   ├── components/               # UI 组件
    │   │   ├── ChatMessage.tsx       # 消息组件（Markdown + 引用 + 反馈）
    │   │   ├── SourceCard.tsx        # 来源引用卡片
    │   │   └── ChatInput.tsx         # 对话输入框
    │   └── lib/api.ts                # API 客户端封装
    ├── Dockerfile
    ├── package.json
    └── next.config.js
```

---

## 快速开始

### 环境要求

| 组件 | 最低版本 | 推荐配置 |
|------|---------|---------|
| Docker | 24.0+ | 4 核 8GB 内存 |
| Docker Compose | 2.20+ | — |
| Python | 3.11+ | 用于本地开发 |
| Node.js | 18+ | 用于前端开发 |
| GPU（LLM 推理） | — | 4×A100 80GB（私有部署 Qwen2.5-72B） |

### 一键启动（Docker Compose）

```bash
# 1. 克隆项目
git clone <repository-url>
cd backend

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入实际配置（详见下方"配置文件详解"）

# 3. 启动所有基础设施服务
docker compose up -d etcd minio milvus-standalone elasticsearch postgresql redis

# 4. 等待服务就绪（约 30 秒），初始化数据库
docker compose exec api-server alembic upgrade head

# 5. 启动应用服务
docker compose up -d api-server worker

# 6. 启动前端（另一个终端）
cd ../frontend
npm install
npm run dev
```

访问 `http://localhost:3000` 即可使用系统。

### 本地开发模式

**后端：**

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e ".[dev]"

# 仅启动基础设施（不启动应用容器）
docker compose up -d etcd minio milvus-standalone elasticsearch postgresql redis

# 数据库迁移
alembic upgrade head

# 启动 API 服务（热重载）
uvicorn rag_qa.main:app --reload --host 0.0.0.0 --port 8000

# 启动 Celery Worker（另一个终端）
celery -A rag_qa worker --loglevel=info
```

**前端：**

```bash
cd frontend
npm install
npm run dev
```

### 最小化部署（资源有限场景）

如果 GPU 资源有限，LLM 可暂时使用 API 调用替代私有部署：

```bash
# .env 中配置 LLM API
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=your-api-key
LLM_MODEL_NAME=qwen-plus
```

所有服务可部署在 1-2 台服务器上（需 64GB+ 内存）。

---

## 配置文件详解

### 环境变量 (.env)

所有配置通过环境变量注入，支持 `.env` 文件和 `config.yaml` 两种方式。

#### 数据库配置

| 变量名 | 默认值 | 说明 |
|-------|--------|------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/rag_qa` | PostgreSQL 连接字符串（必须使用 asyncpg 驱动） |
| `DB_POOL_SIZE` | `20` | 连接池大小 |
| `DB_MAX_OVERFLOW` | `10` | 连接池最大溢出 |
| `DB_POOL_RECYCLE` | `3600` | 连接回收时间（秒） |

#### Redis 配置

| 变量名 | 默认值 | 说明 |
|-------|--------|------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接地址，用于缓存和消息队列 |

#### Milvus 配置

| 变量名 | 默认值 | 说明 |
|-------|--------|------|
| `MILVUS_HOST` | `localhost` | Milvus 服务地址 |
| `MILVUS_PORT` | `19530` | Milvus 服务端口 |

#### Elasticsearch 配置

| 变量名 | 默认值 | 说明 |
|-------|--------|------|
| `ES_HOSTS` | `["http://localhost:9200"]` | ES 集群地址列表 |

#### MinIO 配置

| 变量名 | 默认值 | 说明 |
|-------|--------|------|
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO 服务地址 |
| `MINIO_ACCESS_KEY` | `minioadmin` | 访问密钥 |
| `MINIO_SECRET_KEY` | `minioadmin` | 秘密密钥 |
| `MINIO_BUCKET` | `rag-qa-docs` | 文档存储桶名 |

#### LLM 配置

| 变量名 | 默认值 | 说明 |
|-------|--------|------|
| `LLM_API_BASE` | `https://api.openai.com/v1` | LLM API 地址（兼容 OpenAI 格式） |
| `LLM_API_KEY` | — | API 密钥 |
| `LLM_MODEL_NAME` | `gpt-4o` | 模型名称，私有部署推荐 `Qwen2.5-72B-Instruct` |
| `LLM_MAX_TOKENS` | `4096` | 最大生成 token 数 |
| `LLM_TEMPERATURE` | `0.1` | 生成温度（问答场景建议低值） |

#### Embedding 配置

| 变量名 | 默认值 | 说明 |
|-------|--------|------|
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-large-zh-v1.5` | Embedding 模型名称 |
| `EMBEDDING_DIMENSION` | `1024` | 向量维度（需与模型匹配） |

#### 安全配置

| 变量名 | 默认值 | 说明 |
|-------|--------|------|
| `SECRET_KEY` | `change-me-in-production` | JWT 签名密钥（**生产环境必须修改**） |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token 过期时间（分钟） |

#### 同步配置

| 变量名 | 默认值 | 说明 |
|-------|--------|------|
| `SYNC_INTERVAL_MINUTES` | `15` | 增量同步间隔（分钟） |
| `FULL_SYNC_HOUR` | `2` | 全量同步时间（小时，默认凌晨 2 点） |

### config.yaml 方式（可选）

除环境变量外，也支持 YAML 配置文件：

```yaml
database:
  url: "postgresql+asyncpg://rag_qa:password@localhost:5432/rag_qa"
  pool_size: 20

redis:
  url: "redis://localhost:6379/0"

milvus:
  host: "localhost"
  port: 19530

llm:
  api_base: "http://localhost:8000/v1"
  model_name: "Qwen2.5-72B-Instruct"
  temperature: 0.1

embedding:
  model_name: "BAAI/bge-large-zh-v1.5"
  dimension: 1024

security:
  secret_key: "your-production-secret-key"
  access_token_expire_minutes: 1440
```

### 数据源连接配置

各数据源的连接参数存储在 `datasources.config` JSON 字段中：

**钉钉知识库：**

```json
{
  "app_key": "dingxxxxxx",
  "app_secret": "xxxxxx",
  "dws_cli_path": "/usr/local/bin/dws"
}
```

> `dws_cli_path` 为可选项，配置后使用 dingtalk-workspace-cli 方式接入（无需企业 API 权限）

**Seafile：**

```json
{
  "server_url": "https://seafile.example.com",
  "api_token": "xxxxxxxxxxxx",
  "repo_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**NAS：**

```json
{
  "protocol": "smb",
  "host": "192.168.1.100",
  "port": 445,
  "username": "user",
  "password": "pass",
  "share_path": "shared/docs"
}
```

> `protocol` 支持 `smb` / `nfs` / `webdav`

**本地文件：**

```json
{
  "base_path": "/data/project-docs",
  "watch_patterns": ["*.pdf", "*.docx", "*.md"]
}
```

---

## 使用说明

### 1. 创建项目和数据源

1. 登录系统后，进入 **管理后台 → 项目管理**，创建项目
2. 进入 **数据源配置**，为项目添加数据源（选择类型并填入连接参数）
3. 点击 **连接测试** 验证数据源可用性
4. 点击 **触发同步** 开始首次文档同步

### 2. 知识问答

1. 进入 **对话界面**，顶部下拉选择项目范围
2. 用自然语言提问，例如："项目的系统架构设计方案是什么？"
3. AI 回答附带来源引用，点击引用卡片可查看原文详情
4. 对回答进行点赞/点踩反馈

### 3. 多轮对话

系统支持上下文连续问答：

```
用户: XX项目的系统架构是什么？
AI: [回答架构方案]

用户: 它的数据库选型是什么？     ← 自动理解"它"指代XX项目
AI: [回答数据库选型]
```

### 4. 同步监控

在 **管理后台 → 同步监控** 页面可查看：
- 各数据源同步状态（运行中/已完成/失败）
- 同步统计（处理文档数、失败数）
- 手动触发增量/全量同步

### 5. 质量监控

在 **管理后台 → 质量仪表盘** 可查看：
- 核心指标：Faithfulness、Answer Relevancy、Context Precision、Context Recall
- BadCase 列表和分类统计
- 用户满意度趋势

### 6. 钉钉机器人

配置钉钉机器人后，可在钉钉群内直接 @机器人 提问：

1. 在钉钉群中添加自定义机器人
2. 配置 Webhook URL 和 App Secret
3. 在系统中配置机器人回调地址
4. 群内 @机器人 提问即可获得回答

---

## 注意事项

### 安全相关

- ⚠️ **生产环境必须修改 `SECRET_KEY`**，使用强随机字符串
- ⚠️ **修改默认数据库密码**，不要使用 `.env.example` 中的默认密码
- ⚠️ **MinIO 访问密钥**必须修改默认的 `minioadmin/minioadmin`
- ⚠️ **启用 HTTPS**，使用 Nginx 反向代理配置 SSL 证书
- ⚠️ **不要将 .env 文件提交到版本控制**，`.gitignore` 已包含此规则

### 性能相关

- Milvus HNSW 索引参数 `M=16, efConstruction=256` 适合百万级向量；千万级需调大参数
- Elasticsearch 建议配置 `ES_JAVA_OPTS` 为物理内存的 50%，且不超过 32GB
- LLM 推理推荐使用 vLLM 加速，开启 PagedAttention 可提升 2-3 倍吞吐
- Embedding 批量编码建议 `batch_size=32`，过大会导致 OOM

### 数据源相关

- **钉钉 API 限流**：标准版 1 万次/月，建议合理规划调用频率，缓存 access_token
- **钉钉无企业权限**：可使用 `dingtalk-workspace-cli` 替代方案，通过浏览器 OAuth 认证
- **Seafile 大文件**：下载超时建议调整 httpx timeout 参数
- **NAS 协议选择**：Linux 环境优先使用 NFS（性能优于 SMB），跨平台使用 SMB
- **本地文件监听**：watchdog 在 NFS/CIFS 挂载目录上可能不稳定，建议使用轮询模式

### 文档处理相关

- **PDF 扫描件**：需部署 PaddleOCR 服务（需 GPU），否则扫描件内容标记为 `[OCR待处理]`
- **大文件处理**：单个文件超过 100MB 建议分片处理，避免内存溢出
- **中文分块**：jieba 首次加载词典需约 1-2 秒，后续使用缓存

### 部署相关

- 生产环境推荐使用 [docker-compose.prod.yml](deploy/docker-compose.prod.yml)，包含资源限制和健康检查
- GPU 服务器需安装 NVIDIA Driver + CUDA + nvidia-container-toolkit
- Milvus 数据目录建议使用 NVMe SSD，避免 HDD 影响检索性能

---

## 后续规划

### V2 — 智能增强（预计 Q3 2026）

| 功能 | 描述 |
|------|------|
| 知识图谱增强 | 构建项目知识图谱，支持跨文档关联查询和多跳推理 |
| Agentic 深度搜索 | Agent 自主分解复杂问题，多步检索后综合回答 |
| 文档自动摘要 | 自动为长文档生成摘要，辅助快速了解文档内容 |
| 智能代码生成 | 基于项目知识库生成代码片段、函数实现、单元测试 |
| 技术文档自动生成 | 从代码生成 API 文档、架构图、README |
| 会议纪要自动生成 | 从会议录音/速记生成结构化会议纪要 |
| 多模态问答 | 支持图片、表格、流程图等多模态内容的理解和问答 |

### V3 — 主动智能（预计 Q1 2027）

| 功能 | 描述 |
|------|------|
| 主动知识推送 | 根据用户工作场景主动推送相关知识 |
| 知识协作 | 支持用户对答案进行补充和纠错，形成知识众包 |
| 跨项目知识发现 | 自动发现不同项目间的相似方案和最佳实践 |
| 智能知识库整理 | 自动识别过时文档、重复文档，建议归档或合并 |
| 项目报告自动生成 | 基于项目材料自动生成周报/月报/总结报告 |

---

## 开源参考

本项目借鉴了以下开源项目的设计思路：

| 项目 | 参考价值 |
|------|---------|
| [RAGFlow](https://github.com/infiniflow/ragflow) | 深度文档解析、引用溯源、混合检索 |
| [Dify](https://github.com/langgenius/dify) | 工作流编排、插件化架构、权限管理 |
| [LlamaIndex](https://github.com/run-llama/llama_index) | RAG 数据层框架、文档加载器 |
| [LangGraph](https://github.com/langchain-ai/langgraph) | Agent 工作流框架 |
| [MinerU](https://github.com/opendatalab/MinerU) | 中文 PDF 深度解析 |
| [RAGAS](https://github.com/explodinggradients/ragas) | RAG 评估框架 |
| [vLLM](https://github.com/vllm-project/vllm) | LLM 高性能推理引擎 |

---

## License

内部项目，仅供公司内部使用。
