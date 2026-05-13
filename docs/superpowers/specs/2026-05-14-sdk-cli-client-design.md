# SDK + CLI 客户端设计规格

**日期**: 2026-05-14 | **版本**: 1.0 | **状态**: 草稿

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
                wait: bool = True,
                timeout: int = 600) -> TaskResult:
        """提交需求并执行。wait=False 时立即返回不等待。"""

    def status(self, thread_id: str) -> TaskStatus:
        """查询任务进度。"""

    def approve(self, thread_id: str, *, note: str = "") -> TaskResult:
        """批准等待中的任务。"""

    def reject(self, thread_id: str, *, reason: str = "") -> TaskResult:
        """拒绝等待中的任务。"""

    def health(self) -> SystemInfo:
        """系统健康检查。"""

    # === 异步版本 (方法名加 _async 后缀) ===

    async def execute_async(self, text, *, images=..., wait=True, timeout=600) -> TaskResult: ...
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
  --output <fmt>             输出格式：html/react/both（默认 both）
  --style <name>             设计风格：minimal/modern/classic（默认 modern）
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

### 3.2 输出格式

全局参数 `--output`，适用所有命令。

| 格式 | 说明 | 示例 |
|------|------|------|
| `table` | 彩色表格（rich 库） | Agent 列表、任务列表 |
| `json` | 标准 JSON | 脚本管道 `| jq` |
| `summary` | 一句话摘要 | "✅ 已生成 3 个 HTML 到 preview/" |
| `tree` | 目录树 | preview 文件夹结构 |
| `preview` | 代码内容摘录 | 打印文件前 20 行 |
| `url` | 文件路径链接 | `file:///D:/.../preview/index.html` |

每条命令有默认格式，用 `--output` 可覆盖。

### 3.3 进度显示

等待模式下显示进度条：
```
[分析需求中...] ████████░░ 80%
[生成代码中...] ████████████ 100%
```

### 3.4 表单模式详细

```
$ fedcli new --form
┌──────────────────────────────────────┐
│           提交新需求                   │
│                                       │
│  需求描述:  ________________________   │
│  附加图片:  [design.png]  [选择文件]    │
│  输出格式:  ○ HTML  ○ React  ● 都生成   │
│  设计风格:  ○ 简约   ● 现代   ○ 经典    │
│  等待结果:  ● 是       ○ 否            │
│                                       │
│         [取消]          [提交]        │
└──────────────────────────────────────┘
```

### 3.5 菜单模式详细

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

## 5. 依赖

```
# SDK (最小化)
httpx>=0.27.0
pydantic>=2.0

# CLI (额外)
rich>=13.0          # 彩色表格、进度条
questionary>=2.0    # 交互式菜单
click>=8.0          # 命令行框架
```

---

## 6. 文件变更清单

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

## 7. 测试要点

- SDK: 同步/异步调用正确性、异常处理、超时重试
- CLI: 三种模式切换、六种输出格式、错误提示
- 集成: 连接真实 Gateway 后的端到端流程
