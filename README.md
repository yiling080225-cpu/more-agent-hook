# 多模态 Agent 联邦 — 12 Agent 四层架构 + 13步全流程工作流

> **哪个 Agent 能力强就用哪个** — 本地可运行的 Agent Federation

12 个协作 AI Agent 分为 4 层（设计/工程/战略/基础），通过 Gateway 统一调度。支持 13 步 LangGraph 全流程工作流（需求→交付）、3 条协作管道、Sub-Agent 并行编排、4 个人工审批检查点、A2A 协议通信。

---

## 快速开始

```bash
# 1. 安装依赖
pip install -e .

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，至少填入 DEEPSEEK_KEY

# 3. 校验配置
python validate_setup.py

# 4. 启动全部服务 (Gateway + 12 Agent)
python run.py
```

浏览器打开 http://127.0.0.1:8000/docs 查看 API 文档。

---

## 架构概览

```
Claude Code (Sub-Agent 编排层)
  ├─ Agent("office-hours")  → 步骤1 需求调研
  ├─ Agent("general-purpose") → 步骤2-5 设计
  └─ Agent("general-purpose") → 步骤6-13 开发交付
         │ FederationClient SDK
         ▼
[Gateway :8000] — 路由 + A2A 调度 + 管道编排 + LangGraph 工作流
   │    │    │    │    │    │    │    │    │    │    │    │
   ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼
[设计层 8001-8003]  [工程层 8004-8007]  [战略层 8008-8010] [基础层 8011-8012]
 Multimodal :8001    Code      :8004     Architect :8008    Knowledge :8011
 UX         :8002    Test      :8005     Prompt    :8009    Security  :8012
 Brand      :8003    DevOps    :8006     Crew      :8010
                     Review    :8007
         │                       │
         └─────── A2A ───────────┘
         │
    [LangGraph 工作流引擎]
     ├─ 13步全流程 (需求→交付)
     ├─ 3组并行执行
     ├─ 4个人工审批点
     └─ SQLite Checkpoint 断点恢复
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

## 13步全流程工作流 (LangGraph)

触发关键词: **全流程 / 端到端 / 从需求到交付 / 一条龙**

```
步骤1: 需求调研 [Crew] ──→ 步骤2: 需求文档 [Prompt]
                              │
                    [审批点1: PRD确认]
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    步骤3: 原型设计      步骤4: 可行性评估    步骤5: 技术选型
    [UX]                [Architect]          [Architect]
          └───────────────────┼───────────────────┘
                              ▼
                    步骤6: 架构设计 [Architect]
                              │
                    [审批点2: 架构确认]
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              步骤7: 数据库设计    步骤8: 接口文档
              [Code]              [Code]
                    └─────────┬─────────┘
                              ▼
                    步骤9: 编码开发 [Code]
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              步骤10: 代码审查    步骤11: 测试验证
              [Review]           [Test]
                    └─────────┬─────────┘
                              ▼
                    [审批点3: 质量确认]
                              │
                              ▼
                    步骤12: 部署上线 [DevOps]
                              │
                              ▼
                    步骤13: 验收交付 [Crew + Knowledge]
                              │
                    [审批点4: 最终验收]
```

### 特性

| 特性 | 说明 |
|------|------|
| **3组并行** | 步骤3-5(设计)∥步骤7-8(DB/API)∥步骤10-11(审查/测试) |
| **4个审批点** | PRD→架构→质量→验收，每步可 approve/reject/modify |
| **断点恢复** | SQLite Checkpoint，工作流中断后从断点继续 |
| **步骤1联动** | office-hours skill 做 YC 风格需求脑暴 |
| **两步降级** | LangGraph 不可用时 → Supervisor 并行管道 |

### 全流程 API

```bash
# 启动全流程工作流
curl -X POST http://127.0.0.1:8000/full-flow/start \
  -H "Content-Type: application/json" \
  -d '{"input": {"text": "做一个在线教育平台"}}'

# 查询工作流状态 (含各步骤完成情况)
curl http://127.0.0.1:8000/full-flow/{thread_id}/status

# 获取审批上下文
curl http://127.0.0.1:8000/full-flow/{thread_id}/approval-context

# 审批通过/驳回/修改
curl -X POST http://127.0.0.1:8000/full-flow/{thread_id}/resume \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve"}'

# 列出所有全流程工作流
curl http://127.0.0.1:8000/full-flows
```

---

## 协作管道

| 管道 | Agent 链 | 触发条件 |
|------|---------|---------|
| **设计** | Brand → UX → Multimodal | 品牌全案、视觉系统 |
| **工程** | Architect → Code → Review → Test → DevOps | 全栈项目、完整系统 |
| **战略** | Prompt → Crew → Review | 产品战略、技术方案 |
| **全流程** | 13步 LangGraph 工作流 | 全流程/端到端/从需求到交付 |

管道支持嵌套列表: 扁平列表顺序执行，嵌套列表组内 `asyncio.gather` 并行。

---

## Sub-Agent 两层编排

| 层级 | 职责 | 技术 |
|------|------|------|
| **第1层: Claude Code** | 高层并行编排，独立步骤用 `Agent` 工具并行分派 | Claude Code Agent |
| **第2层: Agent Federation** | 底层执行，12 专项 Agent + LangGraph 工作流 | A2A + LangGraph |

Claude Code 端通过 `agent-federation` skill 自动识别任务类型，选择执行模式：
- "全流程" → LangGraph 工作流（步骤1 office-hours + 后端 full-flow）
- 复杂多步 → Sub-Agent 并行编排
- 简单任务 → Gateway 单 Agent 路由

---

## 通用 API

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 列出 12 Agent
curl http://127.0.0.1:8000/agents

# 路由并执行
curl -X POST http://127.0.0.1:8000/supervisor/execute \
  -H "Content-Type: application/json" \
  -d '{"text": "帮我设计一个电商网站的品牌视觉系统"}'

# Token 用量统计
curl http://127.0.0.1:8000/system/tokens

# 系统诊断
curl http://127.0.0.1:8000/system/diagnostics
```

## CLI 客户端

```bash
python fedcli.py                          # 对话模式
python fedcli.py new "做个登录页"          # 提交任务
python fedcli.py system                   # 系统状态
```

## FederationClient SDK

```python
from federation_sdk import FederationClient
client = FederationClient(base_url='http://127.0.0.1:8000')

# 单 Agent 执行
result = client.execute(text="做一个登录页面")

# 带偏好设置
result = client.execute(
    text="做一个Dashboard",
    style="现代极简",
    theme="暗色",
    output_format="html",
    files=["需求文档.pdf"],
)
```

## 环境要求

- Python 3.11+
- 至少 1 个 API Key（DeepSeek 推荐）
- 可选：GLM Key（视觉）、GPT Key（代码设计）、Opus Key（安全/架构）

---

**版本**: 3.0.0 | **许可**: MIT
