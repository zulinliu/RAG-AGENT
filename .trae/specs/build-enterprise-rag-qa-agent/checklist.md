# 企业多源项目知识问答Agent - 验证清单

## P0: 基础架构搭建

- [x] Python项目结构创建完成，依赖管理配置正确（pyproject.toml）
- [x] Docker Compose开发环境可正常启动所有基础设施服务（Milvus、ES、PG、Redis、MinIO）
- [x] PostgreSQL数据库Schema迁移脚本可正常执行，所有表创建成功
- [x] Milvus Collection创建成功，Partition Key和HNSW索引配置正确
- [x] Elasticsearch Index Mapping创建成功，ik分词器配置正确
- [x] FastAPI应用可正常启动，API路由结构完整，JWT认证中间件工作正常
- [x] 统一元数据Schema定义完成，Pydantic模型验证通过

## P1: 数据源接入

- [x] BaseConnector抽象基类定义完整，Connector工厂模式可正常工作
- [x] 钉钉Connector可连接钉钉API获取知识库文档列表和内容
- [x] Seafile Connector可连接Seafile API遍历资料库并下载文件
- [x] NAS Connector可通过SMB/NFS/WebDAV协议访问NAS文件
- [x] 本地文件Connector可通过watchdog监听目录变更事件
- [x] 增量同步逻辑正确，基于modifiedTime/mtime/内容哈希检测变更
- [x] 同步任务调度框架（Celery + Redis Streams）可正常执行和监控
- [x] 数据源管理API端点CRUD操作正常，连接测试功能可用

## P2: 文档处理管道

- [x] PDF解析器可正确提取原生PDF文本和扫描件OCR文字
- [x] Word解析器可正确提取段落、表格、标题层级
- [x] Excel解析器可将表格转为Markdown/文本描述，多Sheet分别处理
- [x] PPT解析器可提取文本框、备注和表格内容
- [x] Markdown解析器可保留标题层级和代码块
- [x] 中文智能分块引擎按结构感知+递归字符策略正确分块
- [x] 分块结果块大小在目标范围内（500-1000字符），重叠正确
- [x] jieba分词语义完整性检查工作正常
- [x] 元数据提取器可正确提取标题、作者、日期、项目归属
- [x] Embedding服务可正常将文本块转为1024维向量
- [x] 端到端文档处理管道可从原始文件到索引写入完整运行

## P3: 检索引擎

- [x] Milvus向量检索可返回Top-K相似文档块，project_id过滤正确
- [x] Elasticsearch BM25检索可返回Top-K关键词匹配文档块，中文分词正确
- [x] RRF融合算法可正确合并多路检索结果
- [x] bge-reranker-v2-m3重排序可对候选文档精排，阈值过滤正确
- [x] 查询意图识别可区分事实查询/方案查询/对比查询/流程查询
- [x] Query改写可将口语化问题转为清晰的检索Query
- [x] 混合检索编排器完整流程可正常运行

## P4: 问答引擎

- [x] LLM推理服务（Qwen2.5 + vLLM）可正常生成文本，支持流式输出
- [x] System Prompt模板正确约束引用来源和拒绝回答行为
- [x] 上下文构建模块可正确组装结构化Prompt上下文
- [x] 答案生成模块可生成带[来源N]引用的答案
- [x] 当知识库无相关内容时，系统正确回答"我没有找到相关信息"
- [x] 引用验证后处理可过滤虚假引用
- [x] 置信度评估模块可计算分数，低置信度答案添加提示
- [x] 多轮对话可理解上下文指代
- [x] 问答API端点正常工作，SSE流式输出正确
- [x] 反幻觉策略端到端测试通过

## P5: 前端与管理后台

- [x] React项目可正常启动，路由结构完整
- [x] 对话界面可正常发送消息和显示流式回复
- [x] 来源引用展示组件可点击展开文档详情
- [x] 用户反馈（点赞/点踩）功能正常
- [x] 项目管理页面CRUD操作正常
- [x] 数据源配置页面CRUD和连接测试正常
- [x] 同步任务监控页面可查看状态和手动触发
- [x] 用户权限管理页面角色分配正常
- [x] 质量监控仪表盘可显示核心指标

## P6: 测试与优化

- [ ] 评测数据集构建完成（100+问答对）
- [x] RAGAS评估管道可自动计算Faithfulness、Answer Relevancy等指标
- [ ] Faithfulness >= 0.90
- [ ] Answer Relevancy >= 0.85
- [ ] Context Precision >= 0.80
- [ ] Context Recall >= 0.85
- [ ] 端到端响应时间 P95 <= 5秒
- [ ] 并发用户数 >= 50
- [ ] 权限隔离测试通过（跨项目数据不可见）
- [ ] 数据泄露测试通过（无权限用户无法访问受限内容）

## P7: 部署与上线

- [x] 生产环境Docker Compose可正常部署所有服务
- [x] Prometheus + Grafana监控体系可正常采集和展示指标
- [x] 钉钉机器人可在群内接收和回复问答消息
- [x] 所有组件间通信使用HTTPS/TLS加密
