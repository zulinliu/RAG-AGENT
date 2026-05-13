# 企业多源项目知识问答Agent

> 基于 RAG 架构的企业级精准知识问答系统，整合钉钉知识库、Seafile、NAS、本地文件等多数据源，为项目团队提供精准、可追溯、反幻觉的知识问答服务。

---

## 目录

- [项目介绍](#项目介绍)
- [核心亮点](#核心亮点)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [部署基础环境](#部署基础环境)
- [快速开始](#快速开始)
- [模型服务配置](#模型服务配置)
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

## 部署基础环境

系统依赖以下基础组件，所有组件均通过 Docker 部署，也可使用已有服务。

### 组件清单

| 组件 | 版本 | 用途 | 必选 | 默认端口 |
|------|------|------|------|---------|
| PostgreSQL | 16 | 业务数据存储（用户/项目/文档/对话） | ✅ | 5432 |
| Redis | 7.x | 缓存 + 消息队列（Celery Broker） | ✅ | 6379 |
| Milvus | 2.6+ | 向量数据库（文档块语义检索） | ✅ | 19530 |
| Elasticsearch | 8.x | 全文检索（BM25 关键词搜索） | ✅ | 9200 |
| MinIO | latest | 对象存储（原始文档文件存储） | ✅ | 9000 |
| etcd | 3.5+ | Milvus 元数据存储（Milvus 依赖） | ✅ | 2379 |
| Nginx | 1.24+ | 反向代理 + HTTPS + 前端静态文件 | 生产必选 | 80/443 |
| Prometheus | 2.x | 指标采集 | 可选 | 9090 |
| Grafana | 10.x | 监控仪表盘 | 可选 | 3000 |

### Docker 安装

如果服务器尚未安装 Docker，请先安装：

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# 安装 Docker Compose V2（已内置于 Docker 24.0+）
docker compose version
```

### 各组件 Docker 部署说明

> 以下为独立部署各组件的说明。如果使用项目自带的 `docker-compose.yml`，这些组件会自动编排启动，无需单独部署。

#### 1. PostgreSQL 16

```bash
docker run -d \
  --name postgresql \
  --restart unless-stopped \
  -e POSTGRES_DB=rag_qa \
  -e POSTGRES_USER=rag_qa \
  -e POSTGRES_PASSWORD=rag_qa_password \
  -v pg-data:/var/lib/postgresql/data \
  -p 5432:5432 \
  postgres:16

# 验证
docker exec postgresql psql -U rag_qa -d rag_qa -c "SELECT version();"
```

**配置要点：**
- 生产环境必须修改默认密码
- 建议配置 `shared_buffers` 为物理内存的 25%
- 数据目录建议挂载到 SSD

#### 2. Redis 7

```bash
docker run -d \
  --name redis \
  --restart unless-stopped \
  -v redis-data:/data \
  -p 6379:6379 \
  redis:7-alpine \
  redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru --appendonly yes

# 验证
docker exec redis redis-cli ping
```

**配置要点：**
- 建议设置 `maxmemory` 防止 OOM
- 开启 AOF 持久化避免数据丢失
- 生产环境建议设置密码（`--requirepass`）

#### 3. Milvus 2.6（含 etcd + MinIO）

Milvus 依赖 etcd 和 MinIO，建议使用官方 docker-compose 一起部署：

```bash
# 下载 Milvus 官方编排文件
wget https://github.com/milvus-io/milvus/releases/download/v2.6.0/milvus-standalone-docker-compose.yml -O docker-compose.milvus.yml

# 启动 Milvus + etcd + MinIO
docker compose -f docker-compose.milvus.yml up -d

# 验证
curl http://localhost:9091/healthz
```

**或手动分别部署：**

```bash
# etcd
docker run -d \
  --name etcd \
  --restart unless-stopped \
  -e ETCD_AUTO_COMPACTION_MODE=revision \
  -e ETCD_AUTO_COMPACTION_RETENTION=1000 \
  -e ETCD_QUOTA_BACKEND_BYTES=4294967296 \
  -v etcd-data:/etcd \
  -p 2379:2379 \
  quay.io/coreos/etcd:v3.5.16 \
  etcd -advertise-client-urls=http://0.0.0.0:2379 \
       -listen-client-urls http://0.0.0.0:2379 \
       --data-dir /etcd

# MinIO
docker run -d \
  --name minio \
  --restart unless-stopped \
  -e MINIO_ACCESS_KEY=minioadmin \
  -e MINIO_SECRET_KEY=minioadmin \
  -v minio-data:/data \
  -p 9000:9000 \
  -p 9001:9001 \
  minio/minio:latest \
  server /data --console-address ":9001"

# Milvus
docker run -d \
  --name milvus \
  --restart unless-stopped \
  -e ETCD_ENDPOINTS=etcd:2379 \
  -e MINIO_ADDRESS=minio:9000 \
  -v milvus-data:/var/lib/milvus \
  -p 19530:19530 \
  -p 9091:9091 \
  milvusdb/milvus:v2.6.0
```

**配置要点：**
- Milvus 数据目录建议使用 NVMe SSD
- 生产环境 MinIO 密钥必须修改
- Milvus 2.6 默认使用 Partition Key 功能，无需额外配置

#### 4. Elasticsearch 8.x（含 ik 中文分词）

```bash
# 安装 ik 分词器插件后启动
docker run -d \
  --name elasticsearch \
  --restart unless-stopped \
  -e discovery.type=single-node \
  -e xpack.security.enabled=false \
  -e "ES_JAVA_OPTS=-Xms1g -Xmx1g" \
  -v es-data:/usr/share/elasticsearch/data \
  -v es-plugins:/usr/share/elasticsearch/plugins \
  -p 9200:9200 \
  elasticsearch:8.17.0

# 安装 ik 分词器（首次部署后执行一次）
docker exec elasticsearch bin/elasticsearch-plugin install \
  https://get.infini.cloud/elasticsearch/analysis-ik/8.17.0
docker restart elasticsearch

# 验证
curl http://localhost:9200
curl -X POST "localhost:9200/_analyze?pretty" \
  -H 'Content-Type: application/json' \
  -d '{"analyzer": "ik_max_word", "text": "企业知识问答系统"}'
```

**配置要点：**
- `ES_JAVA_OPTS` 建议设为物理内存的 50%，不超过 32GB
- ik 分词器版本必须与 ES 版本严格匹配
- 生产环境建议开启安全认证（`xpack.security.enabled=true`）

#### 5. Nginx（生产环境反向代理）

```bash
docker run -d \
  --name nginx \
  --restart unless-stopped \
  -v /path/to/nginx.conf:/etc/nginx/nginx.conf:ro \
  -v /path/to/ssl:/etc/nginx/ssl:ro \
  -v /path/to/frontend/dist:/usr/share/nginx/html:ro \
  -p 80:80 \
  -p 443:443 \
  nginx:1.24-alpine
```

**配置要点：**
- 必须配置 SSL 证书启用 HTTPS
- SSE 流式接口需关闭 `proxy_buffering`
- 前端静态文件通过 Nginx 直接托管

#### 6. Prometheus + Grafana（可选监控）

```bash
# Prometheus
docker run -d \
  --name prometheus \
  --restart unless-stopped \
  -v /path/to/prometheus.yml:/etc/prometheus/prometheus.yml:ro \
  -v prometheus-data:/prometheus \
  -p 9090:9090 \
  prom/prometheus:v2.50.0

# Grafana
docker run -d \
  --name grafana \
  --restart unless-stopped \
  -v grafana-data:/var/lib/grafana \
  -p 3000:3000 \
  grafana/grafana:10.3.0
```

### 一键启动所有基础组件（推荐）

使用项目自带的 Docker Compose 编排文件一键启动所有组件：

```bash
cd backend
docker compose up -d etcd minio milvus-standalone elasticsearch postgresql redis
```

该命令会自动启动所有基础组件，无需逐一手动部署。

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

## 模型服务配置

系统涉及三类模型服务：**LLM（大语言模型）**、**Embedding（文本向量化模型）**、**Reranker（重排序模型）**。每类模型均支持 **本地私有化部署** 和 **第三方 API 调用** 两种模式，通过配置 `.env` 文件中的 `API_BASE`、`API_KEY`、`MODEL_NAME` 即可切换。

### 模型服务总览

| 模型类型 | 功能 | 私有部署推荐 | 第三方 API 可选 |
|---------|------|-------------|---------------|
| LLM | 答案生成、查询改写、意图识别、指代消解、评估 | Qwen2.5-72B-Instruct | 阿里云 DashScope、OpenAI、智谱 AI、DeepSeek 等 |
| Embedding | 文本向量化（文档索引 + 查询编码） | bge-large-zh-v1.5 | 阿里云 DashScope、OpenAI、Jina AI 等 |
| Reranker | 检索结果重排序 | bge-reranker-v2-m3 | Jina Reranker、Cohere Rerank 等 |

### 方式一：本地私有化部署

#### LLM 私有部署（vLLM）

推荐使用 vLLM 加速推理，兼容 OpenAI API 格式：

```bash
# GPU 要求：4×A100 80GB（Qwen2.5-72B）或 2×A100 80GB（Qwen2.5-32B）
docker run -d \
  --name vllm-server \
  --restart unless-stopped \
  --gpus all \
  -v /path/to/models:/models \
  -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model /models/Qwen2.5-72B-Instruct \
  --served-model-name Qwen2.5-72B-Instruct \
  --trust-remote-code \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.9

# 验证
curl http://localhost:8000/v1/models
```

**.env 配置：**

```bash
LLM_API_BASE=http://localhost:8000/v1
LLM_API_KEY=empty
LLM_MODEL_NAME=Qwen2.5-72B-Instruct
```

#### Embedding 私有部署

使用 TEI (Text Embeddings Inference) 或自建 FastAPI 服务：

```bash
# 方式 A：使用 TEI（推荐，GPU 加速）
docker run -d \
  --name embedding-server \
  --restart unless-stopped \
  --gpus all \
  -p 8001:80 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-large-zh-v1.5 \
  --max-batch-size 32

# 方式 B：使用 sentence-transformers 自建服务
pip install sentence-transformers fastapi uvicorn
python -c "
from sentence_transformers import SentenceTransformer
from fastapi import FastAPI
import uvicorn

app = FastAPI()
model = SentenceTransformer('BAAI/bge-large-zh-v1.5')

@app.post('/embeddings')
async def embed(request: dict):
    texts = request.get('input', [])
    embeddings = model.encode(texts).tolist()
    return {'data': [{'embedding': e, 'index': i} for i, e in enumerate(embeddings)]}

uvicorn.run(app, host='0.0.0.0', port=8001)
"
```

**.env 配置：**

```bash
EMBEDDING_API_BASE=http://localhost:8001
EMBEDDING_API_KEY=
EMBEDDING_MODEL_NAME=BAAI/bge-large-zh-v1.5
EMBEDDING_DIMENSION=1024
```

#### Reranker 私有部署

使用 TEI 或 FlagEmbedding 自建服务：

```bash
# 方式 A：使用 TEI（rerank 模式）
docker run -d \
  --name reranker-server \
  --restart unless-stopped \
  --gpus all \
  -p 8002:80 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-reranker-v2-m3 \
  --rerank

# 验证
curl http://localhost:8002/rerank \
  -H "Content-Type: application/json" \
  -d '{"query": "测试", "documents": ["文档1", "文档2"], "top_k": 2}'
```

**.env 配置：**

```bash
RERANKER_API_BASE=http://localhost:8002
RERANKER_API_KEY=
RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3
RERANKER_THRESHOLD=0.3
```

### 方式二：第三方 API 调用

所有模型客户端均采用 **OpenAI 兼容 API 格式**，只需配置 `API_BASE`、`API_KEY`、`MODEL_NAME` 即可切换到第三方服务。

#### 阿里云 DashScope（推荐国内用户）

DashScope 兼容 OpenAI API 格式，支持 Qwen 系列模型和 Embedding：

**.env 配置：**

```bash
# LLM - 通义千问
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL_NAME=qwen-plus

# Embedding - 通义文本向量
EMBEDDING_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
EMBEDDING_MODEL_NAME=text-embedding-v3
EMBEDDING_DIMENSION=1024
```

**可用模型：**

| 模型类型 | 模型名称 | 说明 |
|---------|---------|------|
| LLM | `qwen-turbo` | 速度快，成本低，适合日常问答 |
| LLM | `qwen-plus` | 性能均衡，推荐默认使用 |
| LLM | `qwen-max` | 最强性能，复杂推理场景 |
| LLM | `qwen-long` | 超长上下文（1M tokens），长文档场景 |
| Embedding | `text-embedding-v3` | 最新版中文 Embedding |

#### OpenAI

**.env 配置：**

```bash
# LLM
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL_NAME=gpt-4o

# Embedding
EMBEDDING_API_BASE=https://api.openai.com/v1
EMBEDDING_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
EMBEDDING_MODEL_NAME=text-embedding-3-large
EMBEDDING_DIMENSION=1024
```

**可用模型：**

| 模型类型 | 模型名称 | 说明 |
|---------|---------|------|
| LLM | `gpt-4o` | 综合能力强 |
| LLM | `gpt-4o-mini` | 成本低，速度快 |
| LLM | `gpt-4-turbo` | 推理能力强 |
| Embedding | `text-embedding-3-large` | 3072 维，可降维至 1024 |
| Embedding | `text-embedding-3-small` | 1536 维，性价比高 |

#### 智谱 AI (BigModel)

**.env 配置：**

```bash
# LLM
LLM_API_BASE=https://open.bigmodel.cn/api/paas/v4
LLM_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxx
LLM_MODEL_NAME=glm-4-plus

# Embedding
EMBEDDING_API_BASE=https://open.bigmodel.cn/api/paas/v4
EMBEDDING_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxx
EMBEDDING_MODEL_NAME=embedding-3
EMBEDDING_DIMENSION=2048
```

#### DeepSeek

**.env 配置：**

```bash
LLM_API_BASE=https://api.deepseek.com/v1
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL_NAME=deepseek-chat
```

#### Jina AI（Embedding + Reranker）

**.env 配置：**

```bash
# Embedding
EMBEDDING_API_BASE=https://api.jina.ai/v1
EMBEDDING_API_KEY=jina_xxxxxxxxxxxxxxxx
EMBEDDING_MODEL_NAME=jina-embeddings-v3
EMBEDDING_DIMENSION=1024

# Reranker
RERANKER_API_BASE=https://api.jina.ai/v1
RERANKER_API_KEY=jina_xxxxxxxxxxxxxxxx
RERANKER_MODEL_NAME=jina-reranker-v2-base-multilingual
```

#### Cohere（Reranker）

**.env 配置：**

```bash
RERANKER_API_BASE=https://api.cohere.ai/v1
RERANKER_API_KEY=xxxxxxxxxxxxxxxxxx
RERANKER_MODEL_NAME=rerank-multilingual-v3.0
```

> ⚠️ 注意：Cohere Rerank API 格式与 TEI 不同，如需使用需适配 `Reranker` 类的请求/响应格式。

### 混合部署示例

可以灵活组合本地部署和第三方 API，例如：

| 场景 | LLM | Embedding | Reranker | 说明 |
|------|-----|-----------|----------|------|
| 全私有化 | 本地 Qwen2.5-72B | 本地 bge-large-zh | 本地 bge-reranker | 数据不出内网，需 GPU |
| 全 API | DashScope qwen-plus | DashScope text-embedding | Jina Reranker | 无需 GPU，按量付费 |
| 混合（推荐） | DashScope qwen-plus | 本地 bge-large-zh | 本地 bge-reranker | LLM 用 API 省资源，Embedding/Reranker 本地保障数据安全 |
| 最小化 | DashScope qwen-turbo | DashScope text-embedding | 关闭 Rerank | 成本最低，适合试用 |

### 关闭 Reranker（可选）

如果不需要重排序功能，可以在初始化 `HybridRetriever` 时设置 `use_rerank=False`，此时跳过 Rerank 步骤，直接使用 RRF 融合结果。

### Embedding 维度匹配

切换 Embedding 模型时，**必须确保 `EMBEDDING_DIMENSION` 与模型输出维度一致**，且 Milvus Collection 需要重建：

| 模型 | 输出维度 | `EMBEDDING_DIMENSION` 设置 |
|------|---------|---------------------------|
| bge-large-zh-v1.5 | 1024 | `1024` |
| text-embedding-v3 (DashScope) | 1024/768 | `1024` |
| text-embedding-3-large (OpenAI) | 3072（可降维） | `1024`（降维）或 `3072` |
| text-embedding-3-small (OpenAI) | 1536 | `1536` |
| jina-embeddings-v3 | 1024 | `1024` |

> ⚠️ 切换 Embedding 模型后，需要清空 Milvus Collection 并重新索引所有文档，因为不同模型的向量空间不兼容。

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
| `EMBEDDING_API_BASE` | `http://localhost:8001` | Embedding API 地址（兼容 OpenAI 格式） |
| `EMBEDDING_API_KEY` | — | API 密钥（本地部署留空） |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-large-zh-v1.5` | Embedding 模型名称 |
| `EMBEDDING_DIMENSION` | `1024` | 向量维度（需与模型匹配） |

#### Reranker 配置

| 变量名 | 默认值 | 说明 |
|-------|--------|------|
| `RERANKER_API_BASE` | `http://localhost:8002` | Reranker API 地址 |
| `RERANKER_API_KEY` | — | API 密钥（本地部署留空） |
| `RERANKER_MODEL_NAME` | `BAAI/bge-reranker-v2-m3` | Reranker 模型名称 |
| `RERANKER_THRESHOLD` | `0.3` | 相关性阈值，低于此分数的结果被剔除 |

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
  api_key: "empty"
  model_name: "Qwen2.5-72B-Instruct"
  temperature: 0.1

embedding:
  api_base: "http://localhost:8001"
  api_key: ""
  model_name: "BAAI/bge-large-zh-v1.5"
  dimension: 1024

reranker:
  api_base: "http://localhost:8002"
  api_key: ""
  model_name: "BAAI/bge-reranker-v2-m3"
  threshold: 0.3

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
