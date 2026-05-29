# 多模态 Agent 联邦 MVP

> **哪个 Agent 能力强就用哪个** — 本地可运行的 Agent Federation 最小可行产品

5 个协作 AI Agent（多模态设计 / 安全代码生成 / 代码审查 / 提示词工程 / 项目架构）通过 Gateway 统一调度，支持 LangGraph 工作流编排、A2A 协议通信、MCP 工具集成。

---

## 快速开始

```bash
# 1. 安装依赖
pip install -e .

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，至少填入 DEEPSEEK_KEY
# 免费获取: https://platform.deepseek.com/api_keys

# 3. 校验配置
python validate_setup.py

# 4. 启动全部服务 (Gateway + 5 Agent)
python run.py

# 5. 浏览器打开 Dashboard
# http://127.0.0.1:8000/dashboard
```

### 支持的 API 供应商

| 供应商 | 环境变量 | 获取地址 |
|--------|---------|---------|
| DeepSeek (推荐) | `DEEPSEEK_KEY` | platform.deepseek.com |
| 智谱 GLM | `GLM_KEY` | open.bigmodel.cn |
| Gemini | `GEMINI_KEY` | aistudio.google.com |
| GPT / Opus (代理) | `GPT_KEY` / `OPUS_KEY` | 需配置代理 URL |

---

## 架构概览

```
用户输入 (Dashboard / API / CLI)
        |
[Gateway :8000] — 总调度 + A2A 路由 + 工作流控制
   |     |     |     |     |
   | A2A | A2A | A2A | A2A | A2A
   v     v     v     v     v
[Multi] [Code] [Review] [Prompt] [Architect]
 :8001  :8002   :8003    :8004     :8005

LangGraph 工作流:
  需求解析 -> 多模态分析 -> 人工审批 -> 代码生成 -> 审查 -> 完成
                  ↑ Checkpoint (SQLite) ↑ 断点恢复
```

## 5 个核心 Agent

| Agent | 端口 | 能力 | 默认模型 |
|-------|------|------|------|
| **Multimodal** | 8001 | 图像理解、UI 设计规范生成、网页/SVG/CAD 产出 | deepseek-chat |
| **Code** | 8002 | 前端/后端代码生成、API 设计 | deepseek-chat |
| **Review** | 8003 | 多轮代码审查、安全漏洞检测 | deepseek-chat |
| **Prompt Engineer** | 8004 | 提示词设计/调试/优化、A/B 测试 | deepseek-chat |
| **Project Architect** | 8005 | 架构规划、技术选型、系统设计 | deepseek-chat |

所有模型可通过 `.env` 文件中的 `*_MODEL` 变量自由替换。

## API 文档

启动后访问 http://127.0.0.1:8000/docs 查看完整的 Swagger API 文档。

### 关键端点

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 列出所有 Agent
curl http://127.0.0.1:8000/agents

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
```

---

## CLI 客户端

```bash
# 对话模式
python fedcli.py

# 命令行模式
python fedcli.py system              # 系统状态
python fedcli.py estimate "做个登录页"  # 预估费用
python fedcli.py new "做个登录页"       # 提交任务
python fedcli.py status               # 查看任务列表
```

---

## 项目结构

```
├── run.py                          # 统一启动入口
├── fedcli.py / fedcli_gui.py       # CLI / GUI 客户端
├── pyproject.toml                   # 项目配置 (pip install -e .)
├── requirements.txt                # Python 依赖
├── Dockerfile / docker-compose.yml # 容器化部署
├── .env.example                    # 环境配置模板
├── mcp_config.yaml                 # MCP 工具配置
├── agent_cards/                    # 5 个 Agent Card (JSON)
├── src/
│   ├── config.py                   # 配置管理
│   ├── api/       (routes, schemas)
│   ├── agents/    (base, multimodal, code, review, prompt, architect)
│   ├── gateway/   (supervisor, registry, a2a_client)
│   ├── workflow/  (ecommerce_workflow, checkpoint)
│   ├── mcp/       (registry, tools/)
│   └── ui/        (dashboard.html)
├── federation_sdk/                 # Python SDK
└── tests/                          # 测试用例
```

## MVP 简化说明

| 原始方案 | MVP 实现 |
|---------|---------|
| 8 Agent (GCP 部署) | 5 Agent (本地多端口) |
| Firestore Checkpoint | SQLite Checkpoint |
| Cloud Run / GKE | 单进程 asyncio |
| 11 个外部 MCP Server | 6 个内置工具 |
| A2A gRPC + HTTP | HTTP REST A2A |
| Gemini + Claude + GPT | DeepSeek (Anthropic 兼容) |

## 运行测试

```bash
pip install -e ".[test]"
pytest tests/ -v
```

## 部署 (Docker)

```bash
cp .env.example .env
# 编辑 .env 填入 API Key
docker-compose up -d
# Dashboard: http://localhost:8000/dashboard
```

## 环境要求

- Python 3.11+
- DeepSeek API Key（或其他 Anthropic 兼容供应商）
- 可选：Gemini API Key（多模态理解）、GLM API Key（视觉能力）

---

**版本**: 1.0.0-mvp | **许可**: MIT
