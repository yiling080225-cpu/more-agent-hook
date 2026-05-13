# 多模态 Agent 联邦 MVP

> **哪个 Agent 能力强就用哪个** — 本地可运行的 Agent Federation 最小可行产品

基于 [原始架构方案](../multimodal_agent_federation/README.md) 的完整可运行实现。
原始方案需要 GCP + 12 周，本 MVP 压缩为**零云依赖、3 个核心 Agent、本地一键启动**。

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动全部服务 (Gateway + 3 Agent)
python run.py

# 3. 浏览器打开 Dashboard
# http://127.0.0.1:8000/dashboard
```

**API Key 自动配置**: 代码会自动从 `~/.claude/settings.json` (CC Switch 配置文件) 读取 DeepSeek API Key，无需手动设置 `.env` 文件。

---

## 架构概览

```
用户输入 (Dashboard / API)
        |
[Gateway :8000] — 总调度 + A2A 路由 + 工作流控制
   |         |         |
   | A2A     | A2A     | A2A
   v         v         v
[Multimodal] [Code]   [Review]
  :8001      :8002    :8003

LangGraph 工作流:
  需求解析 → 多模态分析 → 人工审批 → 代码生成 → 审查 → 完成
                  ↑ Checkpoint (SQLite) ↑ 断点恢复
```

## 3 个核心 Agent

| Agent | 端口 | 能力 | 模型 |
|-------|------|------|------|
| **Multimodal** | 8001 | 图像理解、UI 设计规范生成 | DeepSeek V4 (带视觉) |
| **Code** | 8002 | 前端/后端代码生成、API 设计 | DeepSeek V4 |
| **Review** | 8003 | 多轮代码审查、安全漏洞检测 | DeepSeek V4 |

## API 文档

启动后访问 http://127.0.0.1:8000/docs 查看完整的 Swagger API 文档。

### 关键端点

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 列出所有 Agent
curl http://127.0.0.1:8000/agents

# Agent 健康检查
curl -X POST http://127.0.0.1:8000/agents/health-check

# 智能路由分析 (不执行)
curl -X POST http://127.0.0.1:8000/supervisor/route \
  -H "Content-Type: application/json" \
  -d '{"text": "帮我生成一个用户登录的API接口"}'

# 路由并执行
curl -X POST http://127.0.0.1:8000/supervisor/execute \
  -H "Content-Type: application/json" \
  -d '{"text": "审查这段代码: eval(user_input)"}'

# 启动完整工作流
curl -X POST http://127.0.0.1:8000/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"input": {"text": "做一个电商网站，需要商品展示和购物车"}}'

# 查看 MCP 工具
curl http://127.0.0.1:8000/mcp/tools
```

---

## 项目结构

```
multimodal_agent_federation_mvp/
├── run.py                          # 统一启动入口
├── requirements.txt                # Python 依赖
├── Dockerfile / docker-compose.yml # 容器化部署
├── .env / .env.example             # 环境配置
├── mcp_config.yaml                 # MCP 工具配置
├── agent_cards/                    # 9 个 Agent Card (JSON)
├── src/
│   ├── config.py                   # 配置管理 (自动读 cc-switch)
│   ├── api/
│   │   ├── routes.py               # FastAPI 路由 (A2A + 管理 API)
│   │   └── schemas.py              # Pydantic 数据模型
│   ├── agents/
│   │   ├── base.py                 # Agent 基类 (A2A 协议)
│   │   ├── multimodal_agent.py     # 多模态 Agent
│   │   ├── code_agent.py           # 代码生成 Agent
│   │   └── review_agent.py         # 代码审查 Agent
│   ├── gateway/
│   │   ├── supervisor.py           # 总调度器 (LLM 智能路由)
│   │   ├── registry.py             # Agent Card 注册中心
│   │   └── a2a_client.py           # A2A HTTP 客户端
│   ├── workflow/
│   │   ├── ecommerce_workflow.py   # LangGraph 端到端工作流
│   │   └── checkpoint.py           # SQLite Checkpoint 持久化
│   ├── mcp/
│   │   ├── registry.py             # MCP 工具注册中心
│   │   └── tools/                  # 内置工具 (文件/搜索/代码)
│   └── ui/
│       └── dashboard.html          # 监控面板
└── tests/                          # 38 个测试用例
```

## MVP 简化说明

| 原始方案 | MVP 实现 |
|---------|---------|
| 8 Agent (GCP 部署) | 3 Agent (本地多端口) |
| Firestore Checkpoint | SQLite Checkpoint |
| Cloud Run / GKE | 单进程 asyncio |
| 11 个外部 MCP Server | 6 个内置工具 |
| A2A gRPC + HTTP | HTTP REST A2A |
| Gemini + Claude + GPT | DeepSeek V4 (Anthropic 兼容) |

## 运行测试

```bash
pytest tests/ -v
# 38 passed
```

## 部署 (Docker)

```bash
docker-compose up -d
# Dashboard: http://localhost:8000/dashboard
```

---

**版本**: 1.0.0-mvp | **日期**: 2026-05-14
