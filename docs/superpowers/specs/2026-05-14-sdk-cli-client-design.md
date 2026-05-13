# SDK + CLI 客户端设计规格

**日期**: 2026-05-14 | **版本**: 1.2 | **状态**: 草稿

---

## 1. 概述

为「多模态 Agent 联邦 MVP」提供面向用户的客户端：Python SDK 库 (`federation_sdk`) 和 CLI 命令行工具 (`fedcli`)。

**设计原则**: 隐藏 A2A 协议、Agent 路由、工作流内部机制。不要求用户理解技术架构。

---

## 2. SDK 设计

### 2.1 包结构

```
federation_sdk/
├── __init__.py              # 导出 FederationClient, TaskResult, TaskStatus, SystemInfo
├── client.py                # FederationClient — 唯一入口
├── _http.py                 # 内部 httpx 封装 (重试、超时)
├── exceptions.py            # FederationError, TimeoutError, NotFoundError
├── models.py                # TaskResult, TaskStatus, SystemInfo, CostEstimate
├── references.py            # 参考素材解析 (图片/网页/项目)
└── resources/               # 高级层资源类
    ├── __init__.py
    ├── supervisor.py        # SupervisorResource
    ├── workflow.py          # WorkflowResource + WorkflowHandle
    ├── agents.py            # AgentsResource
    └── system.py            # SystemResource
```

### 2.2 FederationClient

单一入口类，资源类通过属性访问。支持同步和异步双模式。

```python
class FederationClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: int = 300):
        """初始化客户端。同步异步共用同一个实例。"""

    # === 简便层 (6个方法) ===

    def execute(self, text: str, *,
                images: list[str] | None = None,
                references: list[Reference] | None = None,
                files: list[str] | None = None,
                context: dict | None = None,
                style: str = "modern",
                theme: str | None = None,
                output_format: str = "both",
                allow_search: bool | None = None,
                sandbox: bool = True,
                wait: bool = True,
                timeout: int = 600) -> TaskResult:
        """
        提交需求并执行。
        references:   参考素材列表 (Reference 对象)
        style:        设计风格，见风格列表
        theme:        主题色，hex 或预设名
        output_format: 输出框架 html / react / vue / flutter / both
        allow_search: 是否允许联网搜索，None 表示交给用户决定
        sandbox:      True 在隔离沙盒中生成，False 直接写入 preview/
        wait=False 时立即返回不等待。
        """

    def estimate(self, text: str, *,
                 images: list[str] | None = None,
                 references: list[Reference] | None = None,
                 style: str = "modern",
                 output_format: str = "both",
                 allow_search: bool | None = None) -> CostEstimate:
        """
        预估本次需求的 Token 费用（不执行）。
        返回 CostEstimate，包含预估 token 数、费用区间、置信度。
        """

    def status(self, thread_id: str) -> TaskStatus:
        """查询任务进度。"""

    def approve(self, thread_id: str, *, note: str = "") -> TaskResult:
        """批准等待中的任务。"""

    def reject(self, thread_id: str, *, reason: str = "") -> TaskResult:
        """拒绝等待中的任务。"""

    def health(self) -> SystemInfo:
        """系统健康检查。"""

    # === 异步版本 (方法名加 _async 后缀) ===
    async def execute_async(self, ...): ...
    async def estimate_async(self, ...): ...
    async def status_async(self, thread_id: str) -> TaskStatus: ...
    async def approve_async(self, thread_id, *, note="") -> TaskResult: ...
    async def reject_async(self, thread_id, *, reason="") -> TaskResult: ...
    async def health_async(self) -> SystemInfo: ...

    # === 高级层 (通过属性访问) ===
    client.supervisor.route(text)       # 路由分析
    client.supervisor.execute(text)      # 路由并执行
    client.workflow.start(text, ...)     # 启动工作流 → WorkflowHandle
    client.workflow.resume(id, decision) # 审批后继续
    client.workflow.status(id)           # 查状态
    client.workflow.list()               # 列所有工作流
    client.agents.list()                 # 列 Agent
    client.agents.card(name)             # 看 Agent Card
    client.agents.health_check()         # 批量健康检查
    client.system.info()                 # 系统详细信息
```

### 2.3 参考素材模型 (Reference)

```python
class ReferenceType(str, Enum):
    IMAGE = "image"           # 图片截图
    WEB_PAGE = "web_page"     # 网页 URL
    PROJECT = "project"       # 本地项目目录

class Reference(BaseModel):
    type: ReferenceType
    source: str               # 文件路径 / URL / 目录路径
    description: str = ""     # 用户备注，如 "参考这个首页布局"
    encoding: str = "base64"  # 图片发送时的编码方式

class ImageRef(Reference):
    """图片参考：用户截图、设计稿"""
    type: ReferenceType = ReferenceType.IMAGE

class WebPageRef(Reference):
    """网页参考：在线设计参考、文档"""
    type: ReferenceType = ReferenceType.WEB_PAGE

class ProjectRef(Reference):
    """项目参考：已有代码仓库或目录"""
    type: ReferenceType = ReferenceType.PROJECT
```

### 2.4 Token 费用预估模型

```python
class CostEstimate(BaseModel):
    """Token 费用预估"""
    task_id: str              # 预估编号 (未执行，仅用于追踪)
    input_tokens: int         # 预估输入 token 数 (含参考素材)
    output_tokens: int        # 预估输出 token 数
    total_tokens: int         # 预估总 token 数
    estimated_cost: float     # 预估费用 (人民币元)
    cost_range: tuple[float, float]  # 费用区间 [最低, 最高]
    confidence: str           # 置信度: "high" / "medium" / "low"
    breakdown: dict           # 分项预估明细
    warnings: list[str]       # 费用提醒 (如 "参考图片较大，解析需额外 token")
```

### 2.5 WorkflowHandle

`workflow.start()` 返回此对象，用于跟踪和等待工作流。

```python
class WorkflowHandle:
    thread_id: str
    status: str
    result: dict | None

    def wait(self, timeout: int = 600) -> TaskResult: ...
    def on_progress(self, callback: callable) -> None: ...
```

### 2.6 数据模型

```python
class TaskResult:
    thread_id: str
    status: str             # "completed" | "waiting_human" | "failed" | "running"
    output: dict | None     # 结果内容
    preview_path: str | None # 本地预览文件夹路径

class TaskStatus:
    thread_id: str
    status: str
    step: str               # 当前步骤名称
    started_at: str

class SystemInfo:
    version: str
    status: str
    agents_count: int
    healthy: bool
```

### 2.7 异常体系

```
FederationError (基类)
├── ConnectionError        # 连不上 Gateway
├── TimeoutError           # 请求超时
├── NotFoundError          # 资源不存在
└── TaskFailedError        # 远程任务执行失败
```

### 2.8 同步实现策略

同步方法是异步方法的薄包装，内部用 `asyncio.run()` 调用。对于 `wait()` 的轮询场景，在同步版中使用单次 `asyncio.run()` 包裹轮询循环。

---

## 3. CLI 设计

### 3.1 命令行接口

#### 三种交互模式

| 模式 | 触发方式 | 适用场景 |
|------|---------|---------|
| C 命令行 | `fedcli <子命令>` | 脚本化、管道、自动化 |
| A 表单 | `fedcli new --form` | 一次性填完提交，无逐步交互 |
| B 菜单 | `fedcli` 无参数 | 逐步引导，最友好 |

#### 所有子命令

```
fedcli new <需求描述>        提交新需求
  --ref <sources>            参考素材（逗号分隔，支持图片/URL/目录）
  --ref-img <paths>          参考图片（逗号分隔）
  --ref-web <urls>           参考网页（逗号分隔）
  --ref-project <path>       参考项目目录
  --images <paths>           附加图片（逗号分隔）
  --output <fmt>             输出框架：html/react/vue/flutter/both（默认 both）
  --style <name>             设计风格（默认 modern，见下方风格列表）
  --theme <color>            主题色 hex 或预设名（如 "#2563EB" 或 "ocean"）
  --search / --no-search     是否允许联网搜索参考资料（默认询问）
  --sandbox / --no-sandbox   是否沙盒隔离生成（默认开启）
  --timeout <seconds>        超时秒数（默认 600）
  -w, --wait / --no-wait     是否等待完成（默认等待）
  --form                     打开表单模式

fedcli estimate <需求描述>   预估 Token 费用（不执行）
  --ref <sources>            参考素材
  --ref-img <paths>          参考图片
  --ref-web <urls>           参考网页
  --ref-project <path>       参考项目
  --output <fmt>             输出框架
  --style <name>             设计风格
  --search / --no-search     是否联网搜索

fedcli status <thread-id>    查询任务状态
fedcli approve <thread-id>   批准等待中的任务
  --note <text>              批准备注
fedcli reject <thread-id>    拒绝等待中的任务
  --reason <text>            拒绝原因

fedcli list                  列出所有工作流
fedcli system                系统信息和健康检查
```

### 3.2 设计风格预设（12 种）

| 预设名 | 中文名 | 特点 |
|--------|--------|------|
| `minimal` | 极简 | 大量留白、细线条、无阴影 |
| `modern` | 现代 | 圆角卡片、渐变、微阴影（默认） |
| `classic` | 经典 | 衬线字体、传统布局、稳重配色 |
| `glassmorphism` | 毛玻璃 | 半透明面板、背景模糊、层次感 |
| `neumorphism` | 新拟态 | 柔和浮雕、单色系、内阴影 |
| `brutalist` | 粗野主义 | 粗边框、撞色、Raw 风格 |
| `dark` | 暗夜 | 深色背景、低亮度荧光色 |
| `retro` | 复古 | 像素字体、高饱和、80-90 年代风格 |
| `cyberpunk` | 赛博朋克 | 霓虹灯效、深紫/青绿配色 |
| `organic` | 自然 | 圆润形状、大地色系、柔和过渡 |
| `luxury` | 奢华 | 金色点缀、衬线体、暗色质感 |
| `playful` | 活泼 | 鲜艳色彩、弹跳动画、卡通元素 |

### 3.3 主题色预设（10 种）

| 预设名 | 色值 | 感觉 |
|--------|------|------|
| `ocean` | #2563EB | 蓝色海洋 |
| `forest` | #16A34A | 绿色森林 |
| `sunset` | #EA580C | 橙色日落 |
| `rose` | #E11D48 | 玫瑰红 |
| `lavender` | #7C3AED | 薰衣草紫 |
| `midnight` | #1E293B | 午夜蓝黑 |
| `teal` | #0D9488 | 青碧 |
| `amber` | #D97706 | 琥珀金 |
| `slate` | #64748B | 石板灰 |
| `custom` | 用户自填 | 任意 hex |

### 3.4 输出格式

全局参数 `--output`，适用所有命令。

| 格式 | 说明 | 示例 |
|------|------|------|
| `table` | 彩色表格（rich 库） | Agent 列表、任务列表 |
| `json` | 标准 JSON | 脚本管道 `\| jq` |
| `summary` | 一句话摘要 | "已生成 3 个 HTML 到 preview/" |
| `tree` | 目录树 | preview 文件夹结构 |
| `preview` | 代码内容摘录 | 打印文件前 20 行 |
| `url` | 文件路径链接 | `file:///D:/.../preview/index.html` |

每条命令有默认格式，用 `--output` 可覆盖。

### 3.5 进度显示

等待模式下显示进度条：
```
[分析需求中...] ████████░░ 80%
[生成代码中...] ████████████ 100%
```

### 3.6 表单模式详细

```
$ fedcli new --form
┌──────────────────────────────────────────────┐
│                 提交新需求                     │
│                                               │
│  需求描述:  _______________________________    │
│  附加图片:  [design.png]          [选择文件]    │
│  参考图片:  [ref1.png,ref2.png]   [选择文件]    │
│  参考网页:  https://example.com               │
│  参考项目:  D:\projects\my-app\               │
│  ───────────────────────────────────────────  │
│  输出框架:  ○ HTML  ○ React  ○ Vue             │
│             ○ Flutter  ● 全都要                │
│  设计风格:  [modern ▼]  (12 种可选)             │
│  主题色:    [ocean ▼]    (10 种预设 + 自定义)    │
│  联网搜索:  ○ 允许  ● 不允许  ○ 让我决定         │
│  沙盒模式:  ● 开启  ○ 关闭                      │
│  等待结果:  ● 是       ○ 否                     │
│  ───────────────────────────────────────────  │
│  ⚠ 需求描述和图片将发送到 Agent 联邦平台          │
│                                               │
│       [预估Token费用]     [取消]    [提交]      │
└──────────────────────────────────────────────┘
```

点击「预估Token费用」后弹出费用预估弹窗（见 3.8）。

### 3.7 菜单模式详细

```
$ fedcli
  欢迎使用 Agent 联邦平台

  ▶ 1) 提交新需求
    2) Token 费用预估
    3) 查看任务 (1 个进行中)
    4) 审批待处理 (2 个等待中)
    5) 系统信息
    6) 退出

  ↑↓ 移动  ↵ 确认
```

菜单选项动态显示待处理数量。

---

## 4. 参考素材输入

### 4.1 三种参考类型

| 类型 | 参数 | 示例 | 处理方式 |
|------|------|------|---------|
| **图片** | `--ref-img` | 设计截图、UI 参考图 | 调用视觉 LLM 解析图片内容，提取布局/配色/组件信息 |
| **网页** | `--ref-web` | 竞品页面、设计参考站 | 抓取网页截图 + HTML 文本，解析页面结构和样式 |
| **项目** | `--ref-project` | 已有代码项目目录 | 读取项目结构、关键文件内容，提取技术栈和样式模式 |

### 4.2 通用简写

`--ref` 参数自动推断类型：
```
fedcli new "重设计官网首页" --ref ref.png,https://example.com,D:\my-app
```
- `.png/.jpg/.gif` 结尾 → 图片参考
- `http://` 或 `https://` 开头 → 网页参考
- 目录路径 → 项目参考

### 4.3 参考素材解析流程

```
用户提供参考 → SDK 本地预处理 → 发送到 Gateway → Agent 解析

图片: 本地读取 → base64 编码 → 发送到 Multimodal Agent (视觉 LLM)
网页: SDK 抓取 → 截图 + HTML → 文本发送文本模型 + 截图发视觉模型
项目: 本地读取 → 目录树 + 关键文件列表 → 发送到 Code Agent
```

解析结果融合到需求上下文中，供后续方案生成使用。

### 4.4 参考素材安全

当用户提供参考素材时，**必须高亮提醒**：

```
$ fedcli new "做一个网站" --ref-web https://example.com

⚠ 【外部参考素材提醒】
  将处理以下外部参考:
  - 网页: https://example.com → Agent 将抓取并分析该网页
  
  以下信息可能外传:
  - 网页 URL
  - 网页截图和文本内容
  - 不会发送: 你的 IP、Cookie、登录状态

  确认使用这些参考素材？[Y/n]
```

对于本地项目参考：
```
$ fedcli new "重构项目" --ref-project D:\my-app

⚠ 【本地项目参考提醒】
  将读取以下目录:
  - D:\my-app\ (包含 127 个文件)
  
  仅读取以下信息发送到 Agent:
  - 目录结构树
  - package.json / requirements.txt (依赖声明)
  - 入口文件 (app.py, index.js 等)
  - 不会发送: .env、node_modules/、__pycache__/

  确认发送项目结构？[y/N] [查看将发送的文件列表]
```

---

## 5. Token 费用预估

### 5.1 预估时机

**方案生成前**，系统自动提供费用预估，用户确认后再执行。

执行流程：
```
用户提交需求
  → 解析参考素材
  → 计算预估 Token → 展示给用户 ← 用户可以取消或调整
  → 用户确认
  → 开始执行方案生成
```

`--wait` 模式下，预估在提交需求后、生成方案前展示。

### 5.2 预估展示格式

```
$ fedcli new "做一个电商网站" --ref-img design.png --output both

  正在解析参考素材...
  ✓ design.png (1200x800, 分析完成)

╔══════════════════════════════════════════════╗
║            Token 费用预估                     ║
╠══════════════════════════════════════════════╣
║  预估输入 Token:      12,500                  ║
║  预估输出 Token:       8,000                  ║
║  预估总 Token:        20,500                  ║
║                                               ║
║  预估费用:            ¥0.25 ～ ¥0.41          ║
║  置信度:              中 (基于相似历史任务)      ║
║                                               ║
║  分项:                                        ║
║  ├─ 需求分析:          2,000 tokens (¥0.03)    ║
║  ├─ 参考图片解析:      8,000 tokens (¥0.12)    ║
║  ├─ 方案生成:          6,500 tokens (¥0.10)    ║
║  └─ 代码生成:          4,000 tokens (¥0.06)    ║
║                                               ║
║  ⚠ 参考图片较大 (1200x800)，解析消耗较多 Token   ║
║  💡 关闭联网搜索可节省约 3,000 tokens            ║
║                                               ║
║  模型: DeepSeek V4 | 输入 ¥0.015/1K | 输出 ¥0.030/1K ║
╚══════════════════════════════════════════════╝

  是否继续？[Y/n/调整参数]
```

### 5.3 单独预估命令

```
$ fedcli estimate "做一个电商网站" --output both --style modern

  预估费用: ¥0.18 ～ ¥0.30
  预估 Token: 15,000
  置信度: 高

  使用 fedcli new ... 提交执行
```

### 5.4 预估算法

```
预估 Token = 输入 Token + 输出 Token

输入 Token 计算:
  - 需求文本: len(text) / 2  (中文约 2 字符/token)
  - 每张参考图片: 图片面积 / 64  (vision transformer 基准)
  - 每个参考网页: 5000 + HTML 文本长度 / 3
  - 每个参考项目: 2000 + 文件数 * 500

输出 Token 计算:
  - 基于需求复杂度 (LLM 快速分类) * 历史平均倍率
  - 简单需求: 2,000-5,000
  - 中等需求: 5,000-15,000
  - 复杂需求: 15,000-40,000

费用计算:
  - 使用 settings 中配置的模型定价
  - 当前 DeepSeek V4: ¥0.015/1K 入, ¥0.030/1K 出
  - 区间 = [最低, 最高] = [total*0.8, total*1.2]
```

### 5.5 费用预估安全提醒

预估本身不消耗用户 Token（使用本地算法），但涉及解析参考素材时提醒：

```
$ fedcli estimate "..." --ref-web https://...

⚠ 【预估说明】
  分析参考网页将产生少量网络请求（页面抓取）。
  预估费用仅基于当前模型定价，实际可能有 ±20% 波动。
  本操作不执行任务，不产生 AI Token 费用。
```

---

## 6. preview 文件夹

- CLI 运行时自动创建 `preview/` 于项目根目录
- 每次任务完成后写入最新结果，同目录覆盖
- 用户双击打开文件即可预览，无需了解路径

```
preview/
├── index.html
├── design_spec.md
├── app.py
└── ...
```

---

## 7. 沙盒模式

### 7.1 概念

| 模式 | 行为 | 适用场景 |
|------|------|---------|
| `sandbox=True`（默认） | 代码在隔离环境中运行，结果只写入 preview/ | 安全优先、不信任生成代码 |
| `sandbox=False` | 代码直接写入 preview/，可自由访问本地文件 | 信任生成代码、需要本地调试 |

### 7.2 安全提醒

关闭时**必须高亮警告**：
```
$ fedcli new "做一个网站" --no-sandbox

⚠ 【安全警告】沙盒模式已关闭
  生成的代码将直接写入本地文件系统，可能存在以下风险：
  - 恶意代码访问本地文件
  - 意外覆盖系统文件
  - 依赖安装影响系统环境

  建议仅在信任环境下关闭沙盒。

  确认关闭沙盒？[y/N]
```

---

## 8. 信息安全

### 8.1 数据传输安全

- SDK 与 Gateway 之间所有请求通过 HTTP，`base_url` 强制校验协议前缀，拒绝裸 IP
- `base_url` 禁止包含用户名密码，检测到时抛出 `FederationError`
- 所有请求头中不传输任何用户身份信息

### 8.2 API Key 与敏感配置保护

- SDK **绝不**在日志、异常、CLI 输出中明文打印 API Key
- `--output json` 输出时自动脱敏：`key/token/secret/password` 字段值替换为 `***`
- CLI 打印连接信息时 URL 敏感部分掩码

### 8.3 本地文件访问提醒

```
$ fedcli new "做一个网站" --images design.png

⚠ 【本地文件访问提醒】
  读取: D:\projects\design.png
  写入: D:\projects\preview\

  是否继续？[Y/n]
```

### 8.4 本地数据库访问提醒

```
$ fedcli system

⚠ 【本地数据访问提醒】
  正在读取本地数据库:
  - SQLite: D:\projects\data\checkpoints.db

  此操作仅读取，不会修改数据。
```

### 8.5 联网搜索权限提醒

```
$ fedcli new "参考最新设计趋势" --search

⚠ 【联网搜索提醒】
  Agent 将联网搜索参考资料，以下信息可能被发送:
  - 需求描述中的关键词
  - 设计风格和主题偏好
  - 不会发送：本地文件路径、个人信息

  搜索提供商: DuckDuckGo（默认，不追踪用户）

  确认允许联网搜索？[y/N]
```

### 8.6 外部参考素材隐私提醒

```
$ fedcli new "..." --ref-web https://competitor.com

⚠ 【外部参考素材提醒】
  将抓取 https://competitor.com 的截图和内容发送给 Agent。
  该网站的 IP 和 User-Agent 可能被目标服务器记录。
  
  确认发送？[Y/n]
```

### 8.7 用户数据采集提醒

表单底部用分隔线醒目提示 "以下信息将发送到 Agent 联邦平台"。

### 8.8 preview 文件夹安全

- `preview/` 加入 `.gitignore`（防止生成代码意外提交）
- 每次写入前清空旧内容，写入后打印文件列表
- `TaskResult.preview_path` 返回绝对路径，附带安全提醒注释

### 8.9 路径安全

- 拒绝包含 `..` 的路径穿越
- 拒绝绝对路径写入到 `preview/` 以外的目录
- `--images`、`--ref-img`、`--ref-project` 路径解析后确保在项目根目录范围内

---

## 9. 依赖

```
# SDK (最小化)
httpx>=0.27.0
pydantic>=2.0
Pillow>=10.0         # 图片读取与尺寸分析

# CLI (额外)
rich>=13.0           # 彩色表格、进度条、高亮安全提醒、预估面板
questionary>=2.0     # 交互式菜单
click>=8.0           # 命令行框架
```

---

## 10. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `federation_sdk/__init__.py` | 新增 | 包入口，导出公共 API |
| `federation_sdk/client.py` | 新增 | FederationClient 实现 |
| `federation_sdk/_http.py` | 新增 | httpx 内部封装 |
| `federation_sdk/exceptions.py` | 新增 | 异常类 |
| `federation_sdk/models.py` | 新增 | 数据模型 (含 Reference, CostEstimate) |
| `federation_sdk/references.py` | 新增 | 参考素材解析 (图片/网页/项目) |
| `federation_sdk/resources/__init__.py` | 新增 | 资源类导出 |
| `federation_sdk/resources/supervisor.py` | 新增 | SupervisorResource |
| `federation_sdk/resources/workflow.py` | 新增 | WorkflowResource + WorkflowHandle |
| `federation_sdk/resources/agents.py` | 新增 | AgentsResource |
| `federation_sdk/resources/system.py` | 新增 | SystemResource |
| `fedcli.py` | 新增 | CLI 入口 |
| `preview/.gitkeep` | 新增 | 预览文件夹 |
| `requirements.txt` | 修改 | 添加新依赖 (Pillow, rich, questionary, click) |

---

## 11. 测试要点

- SDK: 同步/异步调用、异常处理、超时重试、参考素材解析、Token 预估准确性
- CLI: 三种模式切换、六种输出格式、风格/主题选择、搜索权限确认、沙盒安全提示
- 安全: API Key 脱敏、路径防穿越、文件/数据库/搜索/外部参考提醒、预估不泄密
- 集成: 连接真实 Gateway 后端到端流程
