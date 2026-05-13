# SDK + CLI 客户端设计规格

**日期**: 2026-05-14 | **版本**: 1.1 | **状态**: 草稿

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
├── models.py                # TaskResult, TaskStatus, SystemInfo
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

    # === 简便层 (5个方法) ===

    def execute(self, text: str, *,
                images: list[str] | None = None,
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
        style:       设计风格，见下方风格列表
        theme:       主题色，hex 或预设名（如 "#2563EB" 或 "ocean"）
        output_format: 输出框架 html / react / vue / flutter / both
        allow_search: 是否允许联网搜索，None 表示交给用户决定
        sandbox:      True 在隔离沙盒中生成代码，False 直接写入 preview/
        wait=False 时立即返回不等待。
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

### 2.3 WorkflowHandle

`workflow.start()` 返回此对象，用于跟踪和等待工作流。提供 `on_progress` 回调。

```python
class WorkflowHandle:
    thread_id: str
    status: str
    result: dict | None

    def wait(self, timeout: int = 600) -> TaskResult: ...
    def on_progress(self, callback: callable) -> None: ...
```

### 2.4 数据模型

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

### 2.5 异常体系

```
FederationError (基类)
├── ConnectionError        # 连不上 Gateway
├── TimeoutError           # 请求超时
├── NotFoundError          # 资源不存在
└── TaskFailedError        # 远程任务执行失败
```

### 2.6 同步实现策略

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
  --images <paths>           附加图片（逗号分隔）
  --output <fmt>             输出框架：html/react/vue/flutter/both（默认 both）
  --style <name>             设计风格（默认 modern，见下方风格列表）
  --theme <color>            主题色 hex 或预设名（如 "#2563EB" 或 "ocean"）
  --search / --no-search     是否允许联网搜索参考资料（默认询问）
  --sandbox / --no-sandbox   是否沙盒隔离生成（默认开启）
  --timeout <seconds>        超时秒数（默认 600）
  -w, --wait / --no-wait     是否等待完成（默认等待）
  --form                     打开表单模式

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
│  输出框架:  ○ HTML  ○ React  ○ Vue             │
│             ○ Flutter  ● 全都要                │
│  设计风格:  [modern ▼]  (12 种可选)             │
│  主题色:    [ocean ▼]    (10 种预设 + 自定义)    │
│  联网搜索:  ○ 允许  ● 不允许  ○ 让我决定         │
│  沙盒模式:  ● 开启  ○ 关闭                      │
│  等待结果:  ● 是       ○ 否                     │
│                                               │
│  ⚠ 需求描述和图片将发送到 Agent 联邦平台          │
│                                               │
│           [取消]              [提交]            │
└──────────────────────────────────────────────┘
```

### 3.7 菜单模式详细

```
$ fedcli
  欢迎使用 Agent 联邦平台

  ▶ 1) 提交新需求
    2) 查看任务 (1 个进行中)
    3) 审批待处理 (2 个等待中)
    4) 系统信息
    5) 退出

  ↑↓ 移动  ↵ 确认
```

菜单选项动态显示待处理数量（通过后台查询 `client.workflow.list()`）。

---

## 4. preview 文件夹

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

## 5. 沙盒模式

### 5.1 概念

沙盒模式开启时，Agent 生成的代码在隔离环境中执行，不影响宿主机文件系统。

| 模式 | 行为 | 适用场景 |
|------|------|---------|
| `sandbox=True`（默认） | 代码在临时 Docker 容器或虚拟环境中运行，结果只写入 preview/ | 安全优先、不信任生成代码 |
| `sandbox=False` | 代码直接写入 preview/，可自由访问本地文件 | 信任生成代码、需要本地调试 |

### 5.2 安全提醒

切换沙盒关闭时，**必须高亮警告**：

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

默认选项为 N（否），用户必须显式输入 y 才能继续。

---

## 6. 信息安全

### 6.1 数据传输安全

- SDK 与 Gateway 之间所有请求通过 HTTP，`base_url` 强制校验协议前缀（`http://` 或 `https://`），拒绝裸 IP
- `base_url` 禁止包含用户名密码（如 `http://user:pass@host`），检测到时抛出 `FederationError`
- 所有请求头中不传输任何用户身份信息（当前 MVP 无鉴权，未来扩展时在此补充）

### 6.2 API Key 与敏感配置保护

- SDK 从环境变量或配置文件读取 API Key 时，**绝不**在日志、异常信息、CLI 输出中明文打印
- `--output json` 输出时自动脱敏：任何字段名匹配 `key`、`token`、`secret`、`password`（不区分大小写）时，值替换为 `***`
- CLI 打印连接信息时，URL 中的敏感部分做掩码处理

### 6.3 本地文件访问提醒

当 CLI/SDK 需要读取或写入本地文件时，**必须在终端高亮显示提醒**：

```
$ fedcli new "做一个网站" --images design.png

⚠ 【本地文件访问提醒】
  读取: D:\projects\design.png
  写入: D:\projects\preview\

  是否继续？[Y/n]
```

适用场景：
- `fedcli new --images <paths>`  读取用户指定图片
- `fedcli new` 表单模式中的文件选择
- 写入 `preview/` 文件夹前首次确认

高亮格式要求（rich 库实现）：
- 边框用 `[bold red]` 红色
- 文件路径用 `[bold yellow]` 黄色
- ⚠ 符号用 `[bold yellow]`

### 6.4 本地数据库访问提醒

当 CLI 命令需要查询本地数据（如 SQLite checkpoint、缓存等）时，**必须高亮提醒**：

```
$ fedcli system

⚠ 【本地数据访问提醒】
  正在读取本地数据库:
  - SQLite: D:\projects\data\checkpoints.db

  此操作仅读取，不会修改数据。
```

适用场景：
- `fedcli system` 查询系统信息时涉及本地数据
- `fedcli status <id>` 查询本地 checkpoint 状态
- `fedcli list` 列出本地工作流记录

### 6.5 联网搜索权限提醒

当用户允许联网搜索时，**必须高亮提醒数据外传风险**：

```
$ fedcli new "参考最新设计趋势做一个网站" --search

⚠ 【联网搜索提醒】
  Agent 将联网搜索参考资料，以下信息可能被发送到搜索引擎：
  - 需求描述中的关键词
  - 设计风格和主题偏好
  - 不会发送：本地文件路径、个人信息

  搜索提供商: DuckDuckGo（默认，不追踪用户）

  确认允许联网搜索？[y/N]
```

默认选项为 N（否），用户必须显式输入 y 才能开启搜索。

搜索提供商可配置：
```
$ fedcli new "..." --search --search-provider google
  (可选: duckduckgo / google / bing，默认 duckduckgo)

⚠ 【联网搜索提醒】
  ...
  搜索提供商: Google（可能收集搜索记录）
  ...
```

不同搜索提供商的隐私等级在提醒中区分显示。

### 6.6 用户数据采集提醒

CLI 询问用户信息时，对敏感字段做醒目提示：

```
$ fedcli new --form
┌──────────────────────────────────────────────┐
│                 提交新需求                     │
│                                               │
│  需求描述:  _______________________________    │
│  附加图片:  [design.png]          [选择文件]    │
│  ───────────────────────────────────────────  │
│  ⚠ 以下信息将发送到 Agent 联邦平台              │
│  ───────────────────────────────────────────  │
│  输出框架:  ○ HTML  ○ React  ○ Vue  ...        │
│  设计风格:  [modern ▼]                          │
│  主题色:    [ocean ▼]                           │
│  联网搜索:  ○ 允许  ● 不允许  ○ 让我决定         │
│  沙盒模式:  ● 开启  ○ 关闭                      │
│  等待结果:  ● 是       ○ 否                     │
│                                               │
│           [取消]              [提交]            │
└──────────────────────────────────────────────┘
```

表单底部加分隔线和 "以下信息将发送到..." 提示。

### 6.7 preview 文件夹安全

- `preview/` 目录默认加入 `.gitignore`（防止生成代码意外提交）
- 每次写入前清空旧内容，写入后打印文件列表供用户确认
- SDK 的 `TaskResult.preview_path` 返回绝对路径，附带安全提醒注释

### 6.8 路径安全

- SDK 和 CLI 中所有文件路径操作必须校验：拒绝包含 `..` 的路径穿越、拒绝绝对路径写入到 `preview/` 以外的目录
- `--images` 参数中的路径解析后，确保在项目根目录范围内

---

## 7. 依赖

```
# SDK (最小化)
httpx>=0.27.0
pydantic>=2.0

# CLI (额外)
rich>=13.0          # 彩色表格、进度条、高亮安全提醒
questionary>=2.0    # 交互式菜单
click>=8.0          # 命令行框架
```

---

## 8. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `federation_sdk/__init__.py` | 新增 | 包入口，导出公共 API |
| `federation_sdk/client.py` | 新增 | FederationClient 实现 |
| `federation_sdk/_http.py` | 新增 | httpx 内部封装 |
| `federation_sdk/exceptions.py` | 新增 | 异常类 |
| `federation_sdk/models.py` | 新增 | 数据模型 |
| `federation_sdk/resources/__init__.py` | 新增 | 资源类导出 |
| `federation_sdk/resources/supervisor.py` | 新增 | SupervisorResource |
| `federation_sdk/resources/workflow.py` | 新增 | WorkflowResource + WorkflowHandle |
| `federation_sdk/resources/agents.py` | 新增 | AgentsResource |
| `federation_sdk/resources/system.py` | 新增 | SystemResource |
| `fedcli.py` | 新增 | CLI 入口 |
| `preview/.gitkeep` | 新增 | 预览文件夹 |
| `requirements.txt` | 修改 | 添加新依赖 |

---

## 9. 测试要点

- SDK: 同步/异步调用正确性、异常处理、超时重试、沙盒参数传递
- CLI: 三种模式切换、六种输出格式、风格/主题选择、搜索权限确认、沙盒安全提示
- 安全: API Key 脱敏、路径防穿越、文件访问提醒、联网搜索提醒、沙盒关闭警告
- 集成: 连接真实 Gateway 后的端到端流程
