# 多模态 Agent 联邦 — 12 Agent 四层架构

> **哪个 Agent 能力强就用哪个** — 本地可运行的 Agent Federation

12 个协作 AI Agent 分为 4 层（设计/工程/战略/基础），通过 Gateway 统一调度，支持 LangGraph 工作流编排、A2A 协议通信、MCP 工具集成、3 条协作管道。

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

# 4. 启动全部服务 (Gateway + 12 Agent)
python run.py

# 按层启动 (节省资源)
python run.py --layer design        # 设计层 (3 Agent)
python run.py --layer engineering   # 工程层 (4 Agent)
python run.py --layer strategy      # 战略层 (3 Agent)
python run.py --layer foundation    # 基础层 (2 Agent)

# 5. 浏览器打开 Dashboard
# http://127.0.0.1:8000/dashboard
```

---

## 架构概览

```
用户输入 (Dashboard / API / CLI)
        |
[Gateway :8000] — 智能路由 + A2A 调度 + 协作管道编排 + 工作流控制
   |    |    |    |    |    |    |    |    |    |    |    |
   v    v    v    v    v    v    v    v    v    v    v    v

  [设计层 8001-8003]    [工程层 8004-8007]    [战略层 8008-8010]   [基础层 8011-8012]
  Multimodal :8001      Code      :8004       Architect :8008      Knowledge :8011
  UX         :8002      Test      :8005       Prompt    :8009      Security  :8012
  Brand      :8003      DevOps    :8006       Crew      :8010
                        Review    :8007
```

## 12 Agent 详表

### 设计层 (8001-8003)

| Agent | 端口 | LLM | 职责 |
|-------|------|-----|------|
| **Multimodal Design** | 8001 | GLM | 图像理解、UI设计规范、网页/SVG/CAD产出 |
| **UX/Interaction** | 8002 | GPT | 交互设计、动效设计、可用性分析、线框图 |
| **Brand/Creative** | 8003 | DeepSeek | 品牌视觉系统、色彩/字体、设计Token |

### 工程层 (8004-8007)

| Agent | 端口 | LLM | 职责 |
|-------|------|-----|------|
| **Secure Code** | 8004 | GPT | 前端/后端代码、API设计、类型安全 |
| **Testing/QA** | 8005 | DeepSeek | 测试用例、自动化测试、覆盖率 |
| **DevOps/Deploy** | 8006 | DeepSeek | CI/CD、Docker/K8s、部署脚本 |
| **Code Review** | 8007 | **Opus** | 安全审查、多轮辩论、漏洞检测 |

### 战略层 (8008-8010)

| Agent | 端口 | LLM | 职责 |
|-------|------|-----|------|
| **Project Architect** | 8008 | **Opus** | 架构规划、技术选型、系统设计 |
| **Prompt Engineer** | 8009 | GPT | 提示词设计/调试/优化/A/B测试 |
| **Crew Collaboration** | 8010 | GPT | 多角色协作、内容文案、市场分析 |

### 基础层 (8011-8012)

| Agent | 端口 | LLM | 职责 |
|-------|------|-----|------|
| **Knowledge/RAG** | 8011 | DeepSeek | 文档解析、向量检索、RAG问答 |
| **Security Audit** | 8012 | **Opus** | 渗透测试、OWASP扫描、合规检查 |

---

## 协作管道

复杂任务自动触发多 Agent 顺序协作：

| 管道 | Agent 链 | 触发条件 |
|------|---------|---------|
| **设计** | Brand → UX → Multimodal | 品牌全案、视觉系统 |
| **工程** | Architect → Code → Review → Test → DevOps | 全栈项目、完整系统 |
| **战略** | Prompt → Crew → Review | 产品战略、技术方案 |

普通请求仍只走 1 个 Agent，不影响成本。

## API 文档

启动后访问 http://127.0.0.1:8000/docs

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 列出 12 Agent
curl http://127.0.0.1:8000/agents

# 路由并执行
curl -X POST http://127.0.0.1:8000/supervisor/execute \
  -H "Content-Type: application/json" \
  -d '{"text": "帮我设计一个电商网站的品牌视觉系统"}'
```

## CLI 客户端

```bash
python fedcli.py                          # 对话模式
python fedcli.py new "做个登录页"          # 提交任务
python fedcli.py system                   # 系统状态
```

## 部署 (Docker)

```bash
cp .env.example .env
docker-compose up -d
```

## 环境要求

- Python 3.11+
- 至少 1 个 API Key（DeepSeek 推荐）
- 可选：GLM Key（视觉）、GPT Key（代码设计）、Opus Key（安全/架构）

---

**版本**: 2.0.0 | **许可**: MIT
