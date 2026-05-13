# 企业多源项目知识问答Agent Spec

## Why

公司各项目知识资产分散在钉钉知识库、Seafile、NAS、本地电脑等多个数据源中，项目成员跨平台手动查找资料效率低（平均10-30分钟/次），知识复用率差，新人培训成本高，且通用大模型无法获取内部资料容易产生幻觉。需要构建一个基于RAG架构的企业级知识问答系统，整合多数据源项目材料，提供精准、可追溯的知识问答服务。

## What Changes

- 新建Python后端项目（FastAPI框架），包含数据源接入层、文档处理层、检索增强层、业务服务层、接口层
- 新建React前端项目（Next.js），包含Web对话界面和管理后台
- 新建Docker Compose编排文件，统一管理所有基础设施组件
- 新建统一元数据Schema定义，标准化所有文档的索引结构
- 新建反幻觉机制，包含多层防御策略（检索层、生成层、后处理层、评估层）
- 新建RBAC权限模型，实现项目级数据隔离
- 新建评估与监控体系，持续跟踪问答质量

## Impact

- 新增完整后端服务：数据源Connector、文档处理管道、RAG引擎、业务API
- 新增前端应用：对话界面、管理后台
- 新增基础设施：Milvus、Elasticsearch、PostgreSQL、Redis、MinIO
- 新增LLM/Embedding/Rerank模型服务部署

## ADDED Requirements

### Requirement: 数据源接入层

系统SHALL提供统一的数据源Connector框架，支持钉钉知识库、Seafile、NAS、本地文件系统四种数据源的自动文档采集和同步。

#### Scenario: 钉钉知识库同步
- **WHEN** 管理员配置钉钉知识库数据源并启用同步
- **THEN** 系统通过钉钉API或dingtalk-workspace-cli获取知识库文档列表和内容，自动下载文档至本地存储

#### Scenario: Seafile文件同步
- **WHEN** 管理员配置Seafile数据源并启用同步
- **THEN** 系统通过Seafile Web API递归遍历资料库目录，下载文件供后续解析

#### Scenario: NAS文件同步
- **WHEN** 管理员配置NAS数据源（SMB/NFS/WebDAV）并启用同步
- **THEN** 系统通过对应协议访问NAS存储，监听文件变更事件实现准实时同步

#### Scenario: 本地文件同步
- **WHEN** 管理员配置本地目录数据源并启用同步
- **THEN** 系统通过watchdog实时监听指定目录的文件创建、修改、删除事件

#### Scenario: 增量同步
- **WHEN** 数据源中有新增或修改的文档
- **THEN** 系统仅处理变更部分，基于modifiedTime/mtime/内容哈希检测变更，避免重复处理

#### Scenario: 定时全量扫描
- **WHEN** 到达配置的全量扫描时间（默认凌晨2:00）
- **THEN** 系统对所有数据源执行全量扫描，确保数据完整性

### Requirement: 文档处理管道

系统SHALL提供完整的文档处理管道，支持PDF、Word、Excel、PPT、Markdown、纯文本、图片（OCR）等格式的解析、清洗、分块和向量化。

#### Scenario: PDF文档解析
- **WHEN** 系统接收到PDF文档
- **THEN** 对原生PDF使用MinerU/PyMuPDF提取文本和结构，对扫描件PDF使用PaddleOCR进行文字识别

#### Scenario: Office文档解析
- **WHEN** 系统接收到Word/Excel/PPT文档
- **THEN** 使用对应解析器提取文本、表格、标题层级，保留文档结构信息

#### Scenario: 中文智能分块
- **WHEN** 文档解析完成后
- **THEN** 系统采用结构感知+递归字符混合分块策略，目标块大小500-1000字符，重叠100-200字符，使用jieba分词确保中文语义完整性

#### Scenario: 元数据提取
- **WHEN** 文档处理完成
- **THEN** 系统提取标题、作者、日期、项目归属等元数据，标准化为统一Schema格式

#### Scenario: 向量化与索引构建
- **WHEN** 文档分块完成
- **THEN** 系统使用bge-large-zh-v1.5模型将文本块转为向量写入Milvus，同时将原文写入Elasticsearch建立BM25索引

### Requirement: 检索引擎

系统SHALL提供多路检索+RRF融合+Cross-Encoder精排的三阶段混合检索能力。

#### Scenario: 混合检索
- **WHEN** 用户提交查询
- **THEN** 系统同时执行Milvus向量语义检索（Top-50）和Elasticsearch BM25关键词检索（Top-50），使用RRF算法融合结果

#### Scenario: 重排序
- **WHEN** 检索结果融合完成
- **THEN** 系统使用bge-reranker-v2-m3对Top-30候选进行Cross-Encoder精排，输出Top-10，剔除相关性分数低于0.3的文档

#### Scenario: 查询优化
- **WHEN** 用户提交口语化或模糊的查询
- **THEN** 系统通过LLM进行Query改写，支持HyDE假设性文档嵌入和多查询扩展

#### Scenario: 项目范围限定
- **WHEN** 用户指定或系统识别出查询的项目范围
- **THEN** 检索时自动附加project_id过滤条件，确保结果限定在指定项目范围内

### Requirement: 问答引擎

系统SHALL提供基于RAG的精准问答能力，包含答案生成、引用溯源、反幻觉机制和置信度评估。

#### Scenario: 答案生成与引用
- **WHEN** 检索结果准备就绪
- **THEN** 系统将Top-K文档块组装为结构化Prompt上下文，调用Qwen2.5生成答案，每个事实声明附带[来源N]引用

#### Scenario: 拒绝回答
- **WHEN** 知识库中无相关内容或检索结果不足
- **THEN** 系统明确回答"根据现有项目资料，我没有找到相关信息"，不猜测或编造

#### Scenario: 引用验证
- **WHEN** 答案生成完成
- **THEN** 系统验证答案中每个[来源N]引用是否对应真实的检索结果，过滤虚假引用

#### Scenario: 置信度评估
- **WHEN** 答案后处理完成
- **THEN** 系统综合检索相关性均值、引用覆盖率等因素计算置信度分数，低于0.6时添加低置信度提示

#### Scenario: 多轮对话
- **WHEN** 用户在对话中提出后续问题
- **THEN** 系统理解上下文指代，维护会话历史，支持连续问答

### Requirement: 用户交互层

系统SHALL提供Web端对话界面和管理后台。

#### Scenario: Web对话界面
- **WHEN** 用户通过浏览器访问系统
- **THEN** 提供自然语言对话界面，支持流式输出、Markdown渲染、来源引用展示、点赞/点踩反馈

#### Scenario: 管理后台
- **WHEN** 管理员登录系统
- **THEN** 提供项目管理、数据源配置、同步任务监控、用户权限管理、质量监控仪表盘等功能

### Requirement: 管理与运维

系统SHALL提供项目级管理、数据源管理、RBAC权限控制和同步任务管理。

#### Scenario: 项目管理
- **WHEN** 管理员创建/编辑/删除项目
- **THEN** 系统维护项目信息，配置关联数据源和成员，确保项目级数据隔离

#### Scenario: RBAC权限控制
- **WHEN** 用户访问系统
- **THEN** 根据用户角色（系统管理员/项目管理员/知识库管理员/普通用户/只读用户）控制访问范围

#### Scenario: 数据隔离
- **WHEN** 用户执行查询
- **THEN** 系统通过中间件自动注入用户的项目权限上下文，Milvus使用Partition Key按project_id分区，Elasticsearch使用project_id字段过滤，PostgreSQL查询自动附加项目条件

### Requirement: 评估与监控体系

系统SHALL提供RAGAS自动化评估和BadCase管理能力。

#### Scenario: RAGAS评估
- **WHEN** 每周执行评估任务
- **THEN** 系统自动计算Faithfulness(>=0.90)、Answer Relevancy(>=0.85)、Context Precision(>=0.80)、Context Recall(>=0.85)等指标

#### Scenario: BadCase管理
- **WHEN** 用户点踩反馈或评估发现异常
- **THEN** 系统自动收集BadCase，分类为检索问题或生成问题，支持人工分析和优化闭环

### Requirement: 部署架构

系统SHALL支持Docker Compose容器化部署，所有组件私有化运行。

#### Scenario: 容器化部署
- **WHEN** 执行部署
- **THEN** 通过Docker Compose编排api-server、worker、frontend、milvus、elasticsearch、postgresql、redis、minio、llm-server等容器

#### Scenario: 最小化部署
- **WHEN** GPU资源有限
- **THEN** 支持将所有服务部署在1-2台服务器上，LLM可暂时使用API调用替代私有部署

## MODIFIED Requirements

无（全新项目）

## REMOVED Requirements

无（全新项目）
