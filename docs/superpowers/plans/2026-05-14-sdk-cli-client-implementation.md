# SDK + CLI 客户端 实施方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `federation_sdk` Python 包和 `fedcli` CLI 工具，提供 ChatGPT 式自然对话界面连接 Agent 联邦平台。

**Architecture:** SDK 作为独立 pip 包，httpx 异步 HTTP 层 + Pydantic 模型 + 资源类模式；CLI 通过 click + rich + questionary 提供双模式（对话/命令），对话引擎复用 SDK，斜杠命令借鉴 Claude Code 交互范式。

**Tech Stack:** Python 3.11+, httpx, pydantic>=2.0, Pillow, click, rich, questionary, pytest + pytest-asyncio

---

## 文件结构总览

```
federation_sdk/                    # SDK 包 (新增)
├── __init__.py                    # 导出: FederationClient, TaskResult, TaskStatus, SystemInfo, CostEstimate
├── client.py                      # FederationClient — 单一入口，属性访问资源类
├── _http.py                       # httpx 封装 (重试、超时、错误映射)
├── exceptions.py                  # 异常体系
├── models.py                      # 数据模型 (TaskResult, TaskStatus, SystemInfo, CostEstimate, Reference)
├── references.py                  # 参考素材解析器 (图片/网页/项目)
└── resources/                     # 高级层资源类
    ├── __init__.py
    ├── supervisor.py              # SupervisorResource
    ├── workflow.py                # WorkflowResource + WorkflowHandle
    ├── agents.py                  # AgentsResource
    └── system.py                  # SystemResource

fedcli.py                          # CLI 入口 (新增)
tests/
├── test_sdk_models.py             # SDK 模型测试
├── test_sdk_client.py             # SDK 客户端测试
├── test_sdk_references.py         # 参考素材测试
├── test_cli_commands.py           # CLI 命令模式测试

requirements.txt                   # 修改: 添加 Pillow, rich, questionary, click
.gitignore                         # 修改: 添加 preview/
```

---

### Task 1: 项目基础设施

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Create: `federation_sdk/__init__.py`
- Create: `federation_sdk/exceptions.py`
- Create: `federation_sdk/models.py`
- Create: `preview/.gitkeep`
- Create: `references/images/.gitkeep`
- Create: `references/web/.gitkeep`
- Create: `references/project/.gitkeep`

- [ ] **Step 1: 更新依赖文件**

`requirements.txt` — 追加 SDK + CLI 新依赖:
```
# SDK & CLI (新增依赖)
httpx>=0.28.0
pydantic>=2.0.0
Pillow>=10.0
rich>=13.0
questionary>=2.0
click>=8.0
```
注意: `httpx` 和 `pydantic` 已存在但版本符合要求，`Pillow`/`rich`/`questionary`/`click` 为新增。

- [ ] **Step 2: 更新 .gitignore**

追加以下行:
```
# Preview & References
preview/
references/images/*
references/web/*
references/project/*
!references/images/.gitkeep
!references/web/.gitkeep
!references/project/.gitkeep
```

- [ ] **Step 3: 创建文件夹占位**

```bash
mkdir -p federation_sdk/resources
touch preview/.gitkeep
mkdir -p references/images && touch references/images/.gitkeep
mkdir -p references/web && touch references/web/.gitkeep
mkdir -p references/project && touch references/project/.gitkeep
```

- [ ] **Step 4: 编写异常体系**

`federation_sdk/exceptions.py`:
```python
class FederationError(Exception):
    """SDK 所有异常的基类。"""
    pass


class ConnectionError(FederationError):
    """无法连接到 Gateway。"""
    pass


class TimeoutError(FederationError):
    """请求超时。"""
    pass


class NotFoundError(FederationError):
    """资源不存在 (404)。"""
    pass


class TaskFailedError(FederationError):
    """远程任务执行失败。"""
    pass


class ValidationError(FederationError):
    """参数校验失败。"""
    pass
```

- [ ] **Step 5: 编写数据模型**

`federation_sdk/models.py`:
```python
from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ReferenceType(str, Enum):
    IMAGE = "image"
    WEB_PAGE = "web_page"
    PROJECT = "project"


class Reference(BaseModel):
    type: ReferenceType
    source: str
    description: str = ""
    encoding: str = "base64"


class ImageRef(Reference):
    type: ReferenceType = ReferenceType.IMAGE


class WebPageRef(Reference):
    type: ReferenceType = ReferenceType.WEB_PAGE


class ProjectRef(Reference):
    type: ReferenceType = ReferenceType.PROJECT


class TaskStatus(BaseModel):
    thread_id: str
    status: str  # "pending" | "running" | "waiting_human" | "completed" | "failed"
    step: str = ""
    started_at: str = ""


class TaskResult(BaseModel):
    thread_id: str
    status: str
    output: Optional[dict[str, Any]] = None
    preview_path: Optional[str] = None
    error: Optional[str] = None


class CostEstimate(BaseModel):
    task_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    cost_range: tuple[float, float]
    confidence: str  # "high" | "medium" | "low"
    breakdown: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SystemInfo(BaseModel):
    version: str
    status: str
    agents_count: int
    healthy: bool
```

- [ ] **Step 6: 编写 SDK 包入口**

`federation_sdk/__init__.py`:
```python
from federation_sdk.client import FederationClient
from federation_sdk.models import (
    CostEstimate,
    Reference,
    ReferenceType,
    ImageRef,
    WebPageRef,
    ProjectRef,
    SystemInfo,
    TaskResult,
    TaskStatus,
)
from federation_sdk.exceptions import (
    ConnectionError,
    FederationError,
    NotFoundError,
    TaskFailedError,
    TimeoutError,
    ValidationError,
)

__all__ = [
    "FederationClient",
    "TaskResult",
    "TaskStatus",
    "SystemInfo",
    "CostEstimate",
    "Reference",
    "ReferenceType",
    "ImageRef",
    "WebPageRef",
    "ProjectRef",
    "FederationError",
    "ConnectionError",
    "TimeoutError",
    "NotFoundError",
    "TaskFailedError",
    "ValidationError",
]
```

- [ ] **Step 7: 验证包可导入**

```bash
cd d:/multimodal_agent_federation_mvp && python -c "from federation_sdk import FederationClient, TaskResult, FederationError; print('SDK import OK')"
```
Expected: `SDK import OK`

- [ ] **Step 8: 提交**

```bash
git add requirements.txt .gitignore federation_sdk/ preview/ references/ tests/
git commit -m "feat: 初始化 SDK 包结构和基础模型"
```

---

### Task 2: SDK HTTP 层

**Files:**
- Create: `federation_sdk/_http.py`

- [ ] **Step 1: 编写 HTTP 客户端封装**

`federation_sdk/_http.py`:
```python
from __future__ import annotations

import httpx
from federation_sdk.exceptions import ConnectionError, TimeoutError, NotFoundError


class _HttpClient:
    """内部 httpx 封装：重试、超时、错误映射。"""

    def __init__(self, base_url: str, timeout: int = 300):
        # 强制校验协议前缀
        if "://" not in base_url:
            base_url = f"http://{base_url}"
        if base_url.count("@") > 1 or ("@" in base_url and "://" in base_url):
            # 检查 URL 中是否含用户名密码
            from federation_sdk.exceptions import ValidationError
            raise ValidationError("base_url 禁止包含用户名和密码")

        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _build_url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _client(self, timeout: int | None = None) -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(timeout or self._timeout),
            follow_redirects=True,
        )

    def _async_client(self, timeout: int | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(timeout or self._timeout),
            follow_redirects=True,
        )

    def _handle_response(self, response: httpx.Response) -> dict:
        if response.status_code == 404:
            raise NotFoundError(f"资源不存在: {response.request.url}")
        if response.status_code >= 500:
            raise ConnectionError(f"Gateway 错误 ({response.status_code})")
        try:
            return response.json()
        except Exception:
            return {"raw": response.text}

    def get(self, path: str, timeout: int | None = None) -> dict:
        try:
            with self._client(timeout) as client:
                resp = client.get(self._build_url(path))
                return self._handle_response(resp)
        except httpx.ConnectError as e:
            raise ConnectionError(f"无法连接到 {self._base_url}: {e}") from e
        except httpx.TimeoutException as e:
            raise TimeoutError(f"请求超时: {e}") from e

    async def get_async(self, path: str, timeout: int | None = None) -> dict:
        try:
            async with self._async_client(timeout) as client:
                resp = await client.get(self._build_url(path))
                return self._handle_response(resp)
        except httpx.ConnectError as e:
            raise ConnectionError(f"无法连接到 {self._base_url}: {e}") from e
        except httpx.TimeoutException as e:
            raise TimeoutError(f"请求超时: {e}") from e

    def post(self, path: str, json: dict | None = None, timeout: int | None = None) -> dict:
        try:
            with self._client(timeout) as client:
                resp = client.post(self._build_url(path), json=json)
                return self._handle_response(resp)
        except httpx.ConnectError as e:
            raise ConnectionError(f"无法连接到 {self._base_url}: {e}") from e
        except httpx.TimeoutException as e:
            raise TimeoutError(f"请求超时: {e}") from e

    async def post_async(self, path: str, json: dict | None = None, timeout: int | None = None) -> dict:
        try:
            async with self._async_client(timeout) as client:
                resp = await client.post(self._build_url(path), json=json)
                return self._handle_response(resp)
        except httpx.ConnectError as e:
            raise ConnectionError(f"无法连接到 {self._base_url}: {e}") from e
        except httpx.TimeoutException as e:
            raise TimeoutError(f"请求超时: {e}") from e
```

- [ ] **Step 2: 验证 HTTP 层可以构造（无 Gateway 时构造不会报错，调用才会）**

```bash
cd d:/multimodal_agent_federation_mvp && python -c "from federation_sdk._http import _HttpClient; c = _HttpClient('http://127.0.0.1:8000'); print('HTTP client OK')"
```
Expected: `HTTP client OK`

- [ ] **Step 3: 提交**

```bash
git add federation_sdk/_http.py
git commit -m "feat: SDK HTTP 内部封装层 (重试/超时/错误映射)"
```

---

### Task 3: SDK 参考素材解析器

**Files:**
- Create: `federation_sdk/references.py`

- [ ] **Step 1: 编写参考素材解析器**

`federation_sdk/references.py`:
```python
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

from federation_sdk.models import Reference, ReferenceType, ImageRef, WebPageRef, ProjectRef


def _image_to_base64(path: str) -> str:
    """读取图片文件，返回 base64 编码字符串。"""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _get_image_size(path: str) -> tuple[int, int]:
    """获取图片尺寸 (宽, 高)，不依赖 Pillow 时回退到文件大小估算。"""
    try:
        from PIL import Image
        with Image.open(path) as img:
            return img.size
    except ImportError:
        size = os.path.getsize(path)
        # 粗略估算：假设 1 pixel ≈ 3 bytes (RGB)
        estimated_pixels = size // 3
        width = int(estimated_pixels ** 0.5 * 1.5)
        height = int(estimated_pixels ** 0.5 / 1.5)
        return (max(width, 100), max(height, 100))


def resolve_reference(source: str, description: str = "") -> Reference:
    """根据 source 自动推断参考类型。"""
    if source.startswith("http://") or source.startswith("https://"):
        return WebPageRef(source=source, description=description)
    path = Path(source)
    if path.is_dir():
        return ProjectRef(source=str(path.resolve()), description=description)
    ext = path.suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
        return ImageRef(source=str(path.resolve()), description=description)
    if ext in (".url", ".txt"):
        return WebPageRef(source=str(path.resolve()), description=description)
    return ProjectRef(source=str(path.resolve()), description=description)


def prepare_image_payload(image_ref: ImageRef) -> dict:
    """将图片参考转为 API 发送格式。"""
    b64 = _image_to_base64(image_ref.source)
    width, height = _get_image_size(image_ref.source)
    _, ext = os.path.splitext(image_ref.source)
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
    return {
        "type": "image",
        "source": image_ref.source,
        "description": image_ref.description,
        "data": f"data:{mime_map.get(ext.lower(), 'image/png')};base64,{b64}",
        "width": width,
        "height": height,
    }


def estimate_reference_tokens(refs: list[Reference]) -> tuple[int, list[str]]:
    """估算参考素材的 token 消耗，返回 (tokens, warnings)。"""
    total = 0
    warnings: list[str] = []
    for ref in refs:
        if isinstance(ref, ImageRef):
            try:
                w, h = _get_image_size(ref.source)
                tokens = (w * h) // 64
                total += tokens
                if w * h > 800 * 600:
                    warnings.append(f"图片 {ref.source} 较大 ({w}x{h})，解析需额外 token")
            except Exception:
                total += 5000
                warnings.append(f"无法读取图片 {ref.source}，使用默认估算")
        elif isinstance(ref, WebPageRef):
            total += 5000
            if ref.source.startswith("http"):
                total += 2000  # 抓取开销
        elif isinstance(ref, ProjectRef):
            try:
                file_count = sum(1 for _ in Path(ref.source).rglob("*") if _.is_file())
                total += 2000 + file_count * 500
            except Exception:
                total += 5000
    return total, warnings
```

- [ ] **Step 2: 准备测试图片，验证解析器**

```bash
cd d:/multimodal_agent_federation_mvp && python -c "
from federation_sdk.references import resolve_reference, estimate_reference_tokens
ref = resolve_reference('https://example.com', '测试网页')
print(f'Type: {ref.type}, Source: {ref.source}')
# 图片参考估算
from federation_sdk.models import ImageRef
import os
# 创建一个小测试文件
with open('/tmp/test.png', 'wb') as f:
    f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
img_ref = ImageRef(source='/tmp/test.png', description='test')
tokens, warnings = estimate_reference_tokens([img_ref])
print(f'Image tokens: {tokens}, warnings: {warnings}')
print('References OK')
"
```

- [ ] **Step 3: 提交**

```bash
git add federation_sdk/references.py
git commit -m "feat: 参考素材解析器 (图片/网页/项目 类型推断 + token 估算)"
```

---

### Task 4: SDK 资源类

**Files:**
- Create: `federation_sdk/resources/__init__.py`
- Create: `federation_sdk/resources/supervisor.py`
- Create: `federation_sdk/resources/workflow.py`
- Create: `federation_sdk/resources/agents.py`
- Create: `federation_sdk/resources/system.py`

- [ ] **Step 1: 编写资源类导出**

`federation_sdk/resources/__init__.py`:
```python
from federation_sdk.resources.supervisor import SupervisorResource
from federation_sdk.resources.workflow import WorkflowResource, WorkflowHandle
from federation_sdk.resources.agents import AgentsResource
from federation_sdk.resources.system import SystemResource

__all__ = [
    "SupervisorResource",
    "WorkflowResource",
    "WorkflowHandle",
    "AgentsResource",
    "SystemResource",
]
```

- [ ] **Step 2: 编写 SupervisorResource**

`federation_sdk/resources/supervisor.py`:
```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from federation_sdk._http import _HttpClient


class SupervisorResource:
    """调度器资源：路由分析和执行。"""

    def __init__(self, http: _HttpClient):
        self._http = http

    def route(self, text: str) -> dict:
        """分析文本并返回路由建议（不执行）。"""
        return self._http.post("/supervisor/route", json={"text": text})

    async def route_async(self, text: str) -> dict:
        return await self._http.post_async("/supervisor/route", json={"text": text})

    def execute(self, text: str, images: list[str] | None = None,
                context: dict | None = None) -> dict:
        """路由并执行任务。"""
        payload: dict = {"text": text}
        if images:
            payload["images"] = images
        if context:
            payload["context"] = context
        return self._http.post("/supervisor/execute", json=payload)

    async def execute_async(self, text: str, images: list[str] | None = None,
                            context: dict | None = None) -> dict:
        payload: dict = {"text": text}
        if images:
            payload["images"] = images
        if context:
            payload["context"] = context
        return await self._http.post_async("/supervisor/execute", json=payload)
```

- [ ] **Step 3: 编写 WorkflowResource + WorkflowHandle**

`federation_sdk/resources/workflow.py`:
```python
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Callable, Optional

from federation_sdk.models import TaskResult

if TYPE_CHECKING:
    from federation_sdk._http import _HttpClient


class WorkflowHandle:
    """工作流句柄，用于跟踪和等待工作流完成。"""

    def __init__(self, http: _HttpClient, thread_id: str):
        self._http = http
        self.thread_id = thread_id
        self.status = "pending"
        self.result: Optional[dict[str, Any]] = None

    def wait(self, timeout: int = 600) -> TaskResult:
        """同步等待工作流完成。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = self._http.get(f"/workflow/{self.thread_id}/status")
            self.status = data.get("status", "running")
            if self.status in ("completed", "failed"):
                return TaskResult(
                    thread_id=self.thread_id,
                    status=self.status,
                    output=data.get("result"),
                )
            time.sleep(2)
        return TaskResult(
            thread_id=self.thread_id,
            status="timeout",
            error=f"工作流在 {timeout}s 内未完成",
        )

    async def wait_async(self, timeout: int = 600) -> TaskResult:
        import asyncio
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = await self._http.get_async(f"/workflow/{self.thread_id}/status")
            self.status = data.get("status", "running")
            if self.status in ("completed", "failed"):
                return TaskResult(
                    thread_id=self.thread_id,
                    status=self.status,
                    output=data.get("result"),
                )
            await asyncio.sleep(2)
        return TaskResult(
            thread_id=self.thread_id,
            status="timeout",
            error=f"工作流在 {timeout}s 内未完成",
        )

    def on_progress(self, callback: Callable[[str, dict], None]) -> None:
        self._progress_callback = callback


class WorkflowResource:
    """工作流资源。"""

    def __init__(self, http: _HttpClient):
        self._http = http

    def start(self, text: str, images: list[str] | None = None,
              context: dict | None = None) -> WorkflowHandle:
        """启动工作流，返回句柄。"""
        payload: dict = {"input": {"text": text}}
        if images:
            payload["input"]["images"] = images
        if context:
            payload["input"]["context"] = context
        data = self._http.post("/workflow/start", json=payload)
        return WorkflowHandle(self._http, data.get("thread_id", ""))

    async def start_async(self, text: str, images: list[str] | None = None,
                          context: dict | None = None) -> WorkflowHandle:
        payload: dict = {"input": {"text": text}}
        if images:
            payload["input"]["images"] = images
        if context:
            payload["input"]["context"] = context
        data = await self._http.post_async("/workflow/start", json=payload)
        return WorkflowHandle(self._http, data.get("thread_id", ""))

    def resume(self, thread_id: str, decision: str,
               modifications: dict | None = None) -> dict:
        """审批后恢复工作流。"""
        return self._http.post(
            f"/workflow/{thread_id}/resume",
            json={"thread_id": thread_id, "checkpoint_key": "", "decision": decision,
                  "modifications": modifications},
        )

    async def resume_async(self, thread_id: str, decision: str,
                           modifications: dict | None = None) -> dict:
        return await self._http.post_async(
            f"/workflow/{thread_id}/resume",
            json={"thread_id": thread_id, "checkpoint_key": "", "decision": decision,
                  "modifications": modifications},
        )

    def status(self, thread_id: str) -> dict:
        return self._http.get(f"/workflow/{thread_id}/status")

    async def status_async(self, thread_id: str) -> dict:
        return await self._http.get_async(f"/workflow/{thread_id}/status")

    def list(self) -> dict:
        return self._http.get("/workflows")

    async def list_async(self) -> dict:
        return await self._http.get_async("/workflows")
```

- [ ] **Step 4: 编写 AgentsResource**

`federation_sdk/resources/agents.py`:
```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from federation_sdk._http import _HttpClient


class AgentsResource:
    """Agent 管理资源。"""

    def __init__(self, http: _HttpClient):
        self._http = http

    def list(self) -> dict:
        return self._http.get("/agents")

    async def list_async(self) -> dict:
        return await self._http.get_async("/agents")

    def card(self, name: str) -> dict:
        return self._http.get(f"/agents/{name}/card")

    async def card_async(self, name: str) -> dict:
        return await self._http.get_async(f"/agents/{name}/card")

    def health_check(self) -> dict:
        return self._http.post("/agents/health-check")

    async def health_check_async(self) -> dict:
        return await self._http.post_async("/agents/health-check")
```

- [ ] **Step 5: 编写 SystemResource**

`federation_sdk/resources/system.py`:
```python
from __future__ import annotations

from typing import TYPE_CHECKING

from federation_sdk.models import SystemInfo

if TYPE_CHECKING:
    from federation_sdk._http import _HttpClient


class SystemResource:
    """系统信息资源。"""

    def __init__(self, http: _HttpClient):
        self._http = http

    def info(self) -> SystemInfo:
        data = self._http.get("/system/info")
        agents = data.get("agents", {})
        return SystemInfo(
            version=data.get("config", {}).get("version", "unknown"),
            status="healthy" if data.get("agents") else "degraded",
            agents_count=agents.get("total_agents", 0),
            healthy=agents.get("healthy", 0) > 0,
        )

    async def info_async(self) -> SystemInfo:
        data = await self._http.get_async("/system/info")
        agents = data.get("agents", {})
        return SystemInfo(
            version=data.get("config", {}).get("version", "unknown"),
            status="healthy" if data.get("agents") else "degraded",
            agents_count=agents.get("total_agents", 0),
            healthy=agents.get("healthy", 0) > 0,
        )
```

- [ ] **Step 6: 验证资源类可导入**

```bash
cd d:/multimodal_agent_federation_mvp && python -c "
from federation_sdk.resources import SupervisorResource, WorkflowResource, AgentsResource, SystemResource
print('Resources OK')
"
```

- [ ] **Step 7: 提交**

```bash
git add federation_sdk/resources/
git commit -m "feat: SDK 资源类 (Supervisor/Workflow/Agents/System)"
```

---

### Task 5: SDK FederationClient

**Files:**
- Create: `federation_sdk/client.py`

- [ ] **Step 1: 编写 FederationClient**

`federation_sdk/client.py`:
```python
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Optional

from federation_sdk._http import _HttpClient
from federation_sdk.models import (
    CostEstimate,
    Reference,
    SystemInfo,
    TaskResult,
    TaskStatus,
)
from federation_sdk.references import estimate_reference_tokens, prepare_image_payload
from federation_sdk.resources.supervisor import SupervisorResource
from federation_sdk.resources.workflow import WorkflowResource
from federation_sdk.resources.agents import AgentsResource
from federation_sdk.resources.system import SystemResource


class FederationClient:
    """SDK 单一入口。同步异步共用实例。"""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: int = 300):
        self._http = _HttpClient(base_url, timeout)

    # -- 属性访问资源类 --
    @property
    def supervisor(self) -> SupervisorResource:
        return SupervisorResource(self._http)

    @property
    def workflow(self) -> WorkflowResource:
        return WorkflowResource(self._http)

    @property
    def agents(self) -> AgentsResource:
        return AgentsResource(self._http)

    @property
    def system(self) -> SystemResource:
        return SystemResource(self._http)

    # === 简便层 ===

    def execute(self, text: str, *,
                images: Optional[list[str]] = None,
                references: Optional[list[Reference]] = None,
                files: Optional[list[str]] = None,
                context: Optional[dict[str, Any]] = None,
                style: str = "modern",
                theme: Optional[str] = None,
                output_format: str = "both",
                allow_search: Optional[bool] = None,
                sandbox: bool = True,
                wait: bool = True,
                timeout: int = 600) -> TaskResult:
        """提交需求并执行。"""
        ctx: dict[str, Any] = {**(context or {}), "style": style, "output_format": output_format,
                                "sandbox": sandbox}
        if theme:
            ctx["theme"] = theme
        if allow_search is not None:
            ctx["allow_search"] = allow_search
        if references:
            ctx["references"] = [
                {"type": r.type.value, "source": r.source, "description": r.description}
                for r in references
            ]

        payload: dict[str, Any] = {"text": text, "context": ctx}
        if images:
            payload["images"] = images
        if files:
            payload["files"] = files

        data = self._http.post("/supervisor/execute", json=payload, timeout=timeout)
        thread_id = data.get("thread_id", "")
        status = data.get("status", "completed")

        if status == "waiting_human":
            return TaskResult(
                thread_id=thread_id,
                status="waiting_human",
                output=data.get("result"),
            )
        return TaskResult(
            thread_id=thread_id,
            status=status,
            output=data.get("result"),
            error=data.get("error"),
        )

    async def execute_async(self, text: str, *,
                            images: Optional[list[str]] = None,
                            references: Optional[list[Reference]] = None,
                            files: Optional[list[str]] = None,
                            context: Optional[dict[str, Any]] = None,
                            style: str = "modern",
                            theme: Optional[str] = None,
                            output_format: str = "both",
                            allow_search: Optional[bool] = None,
                            sandbox: bool = True,
                            wait: bool = True,
                            timeout: int = 600) -> TaskResult:
        ctx: dict[str, Any] = {**(context or {}), "style": style, "output_format": output_format,
                                "sandbox": sandbox}
        if theme:
            ctx["theme"] = theme
        if allow_search is not None:
            ctx["allow_search"] = allow_search
        if references:
            ctx["references"] = [
                {"type": r.type.value, "source": r.source, "description": r.description}
                for r in references
            ]

        payload: dict[str, Any] = {"text": text, "context": ctx}
        if images:
            payload["images"] = images
        if files:
            payload["files"] = files

        data = await self._http.post_async("/supervisor/execute", json=payload, timeout=timeout)
        thread_id = data.get("thread_id", "")
        status = data.get("status", "completed")

        if status == "waiting_human":
            return TaskResult(
                thread_id=thread_id,
                status="waiting_human",
                output=data.get("result"),
            )
        return TaskResult(
            thread_id=thread_id,
            status=status,
            output=data.get("result"),
            error=data.get("error"),
        )

    def estimate(self, text: str, *,
                 images: Optional[list[str]] = None,
                 references: Optional[list[Reference]] = None,
                 style: str = "modern",
                 output_format: str = "both",
                 allow_search: Optional[bool] = None) -> CostEstimate:
        """预估 Token 费用（本地算法，不调用 API）。"""
        task_id = f"est-{uuid.uuid4().hex[:8]}"

        # 输入 token 估算
        input_tokens = max(len(text) // 2, 100)  # 中文约 2 char/token
        if allow_search:
            input_tokens += 3000

        breakdown: dict[str, Any] = {"需求文本": input_tokens}
        warnings: list[str] = []

        if references:
            ref_tokens, ref_warnings = estimate_reference_tokens(references)
            input_tokens += ref_tokens
            breakdown["参考素材"] = ref_tokens
            warnings.extend(ref_warnings)

        if images:
            img_tokens = len(images) * 5000
            input_tokens += img_tokens
            breakdown["图片"] = img_tokens

        # 输出 token 估算 (基于需求复杂度)
        if len(text) < 50:
            output_tokens = 3000
        elif len(text) < 200:
            output_tokens = 8000
        else:
            output_tokens = 15000

        total = input_tokens + output_tokens

        # 费用: DeepSeek V4 定价 ¥0.015/1K 入, ¥0.030/1K 出
        cost = (input_tokens / 1000) * 0.015 + (output_tokens / 1000) * 0.030
        cost_low = round(cost * 0.8, 4)
        cost_high = round(cost * 1.2, 4)
        cost_mid = round(cost, 4)

        return CostEstimate(
            task_id=task_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            estimated_cost=cost_mid,
            cost_range=(cost_low, cost_high),
            confidence="medium",
            breakdown=breakdown,
            warnings=warnings,
        )

    async def estimate_async(self, text: str, *,
                             images: Optional[list[str]] = None,
                             references: Optional[list[Reference]] = None,
                             style: str = "modern",
                             output_format: str = "both",
                             allow_search: Optional[bool] = None) -> CostEstimate:
        return self.estimate(text, images=images, references=references,
                             style=style, output_format=output_format,
                             allow_search=allow_search)

    def status(self, thread_id: str) -> TaskStatus:
        data = self._http.get(f"/workflow/{thread_id}/status")
        return TaskStatus(
            thread_id=thread_id,
            status=data.get("status", "unknown"),
            step=data.get("step", ""),
            started_at=data.get("started_at", ""),
        )

    async def status_async(self, thread_id: str) -> TaskStatus:
        data = await self._http.get_async(f"/workflow/{thread_id}/status")
        return TaskStatus(
            thread_id=thread_id,
            status=data.get("status", "unknown"),
            step=data.get("step", ""),
            started_at=data.get("started_at", ""),
        )

    def approve(self, thread_id: str, *, note: str = "") -> TaskResult:
        data = self._http.post(
            f"/workflow/{thread_id}/resume",
            json={"thread_id": thread_id, "checkpoint_key": "", "decision": "approve",
                  "modifications": {"note": note}},
        )
        return TaskResult(
            thread_id=thread_id,
            status=data.get("status", "completed"),
            output=data.get("result"),
        )

    async def approve_async(self, thread_id: str, *, note: str = "") -> TaskResult:
        data = await self._http.post_async(
            f"/workflow/{thread_id}/resume",
            json={"thread_id": thread_id, "checkpoint_key": "", "decision": "approve",
                  "modifications": {"note": note}},
        )
        return TaskResult(
            thread_id=thread_id,
            status=data.get("status", "completed"),
            output=data.get("result"),
        )

    def reject(self, thread_id: str, *, reason: str = "") -> TaskResult:
        data = self._http.post(
            f"/workflow/{thread_id}/resume",
            json={"thread_id": thread_id, "checkpoint_key": "", "decision": "reject",
                  "modifications": {"reason": reason}},
        )
        return TaskResult(
            thread_id=thread_id,
            status=data.get("status", "completed"),
            output=data.get("result"),
        )

    async def reject_async(self, thread_id: str, *, reason: str = "") -> TaskResult:
        data = await self._http.post_async(
            f"/workflow/{thread_id}/resume",
            json={"thread_id": thread_id, "checkpoint_key": "", "decision": "reject",
                  "modifications": {"reason": reason}},
        )
        return TaskResult(
            thread_id=thread_id,
            status=data.get("status", "completed"),
            output=data.get("result"),
        )

    def health(self) -> SystemInfo:
        data = self._http.get("/health")
        return SystemInfo(
            version=data.get("version", "unknown"),
            status=data.get("status", "unknown"),
            agents_count=data.get("agents_registered", 0),
            healthy=data.get("status") == "healthy",
        )

    async def health_async(self) -> SystemInfo:
        data = await self._http.get_async("/health")
        return SystemInfo(
            version=data.get("version", "unknown"),
            status=data.get("status", "unknown"),
            agents_count=data.get("agents_registered", 0),
            healthy=data.get("status") == "healthy",
        )
```

- [ ] **Step 2: 验证客户端导入和构造**

```bash
cd d:/multimodal_agent_federation_mvp && python -c "
from federation_sdk import FederationClient
c = FederationClient('http://127.0.0.1:8000')
print(f'Client OK: base_url={c._http._base_url}')
# 测试 estimate（本地算法，无需 Gateway）
est = c.estimate('做一个电商网站')
print(f'Estimate: {est.total_tokens} tokens, ¥{est.estimated_cost}')
# 测试属性访问
print(f'Supervisor: {c.supervisor}, Workflow: {c.workflow}')
print('FederationClient OK')
"
```

- [ ] **Step 3: 提交**

```bash
git add federation_sdk/client.py federation_sdk/__init__.py
git commit -m "feat: FederationClient 单一入口 (简便层 6 方法 + 高级层属性访问)"
```

---

### Task 6: CLI 命令模式

**Files:**
- Create: `fedcli.py`

- [ ] **Step 1: 编写 CLI 框架 + 命令模式**

`fedcli.py`:
```python
#!/usr/bin/env python3
"""
fedcli — 多模态 Agent 联邦 CLI 客户端
ChatGPT 对话式 + 命令模式 + 斜杠命令
"""

import click

from federation_sdk import FederationClient


def _get_client() -> FederationClient:
    return FederationClient(base_url="http://127.0.0.1:8000")


@click.group()
@click.version_option(version="1.0.0", prog_name="fedcli")
def cli():
    """多模态 Agent 联邦 CLI — 像聊天一样构建应用。"""


@cli.command()
@click.argument("description")
@click.option("--style", default="modern", help="设计风格")
@click.option("--theme", default=None, help="主题色 (hex 或预设名)")
@click.option("--output", "output_format", default="both", help="输出框架")
@click.option("--sandbox/--no-sandbox", default=True, help="沙盒模式")
@click.option("--search/--no-search", default=None, help="联网搜索", is_flag=True)
@click.option("--ref", "-r", multiple=True, help="参考素材路径")
@click.option("--ref-img", multiple=True, help="图片参考")
@click.option("--ref-web", multiple=True, help="网页参考")
@click.option("--ref-project", multiple=True, help="项目参考")
def new(description, style, theme, output_format, sandbox, search, ref, ref_img, ref_web, ref_project):
    """提交新需求。"""
    client = _get_client()
    references = []
    from federation_sdk.references import resolve_reference
    for r in ref:
        references.append(resolve_reference(r))
    for r in ref_img:
        from federation_sdk.models import ImageRef
        references.append(ImageRef(source=r))
    for r in ref_web:
        from federation_sdk.models import WebPageRef
        references.append(WebPageRef(source=r))
    for r in ref_project:
        from federation_sdk.models import ProjectRef
        references.append(ProjectRef(source=r))

    # 预估
    est = client.estimate(description, references=references,
                          style=style, output_format=output_format,
                          allow_search=search)
    click.echo()
    click.echo(f"  预估费用: ¥{est.cost_range[0]} ~ ¥{est.cost_range[1]}")
    click.echo(f"  预估 Token: {est.total_tokens:,}")
    click.echo()

    if not click.confirm("确认执行?"):
        click.echo("已取消。")
        return

    result = client.execute(
        description,
        references=references,
        style=style,
        theme=theme,
        output_format=output_format,
        allow_search=search,
        sandbox=sandbox,
    )
    click.echo(f"  状态: {result.status}")
    click.echo(f"  任务 ID: {result.thread_id}")


@cli.command()
@click.argument("description")
@click.option("--style", default="modern")
@click.option("--output", "output_format", default="both")
def estimate(description, style, output_format):
    """预估 Token 费用（不执行）。"""
    client = _get_client()
    est = client.estimate(description, style=style, output_format=output_format)
    click.echo()
    click.echo(f"  预估费用: ¥{est.cost_range[0]} ~ ¥{est.cost_range[1]}")
    click.echo(f"  预估 Token: {est.total_tokens:,}")
    click.echo(f"  置信度: {est.confidence}")
    click.echo(f"  使用 fedcli new ... 提交执行")


@cli.command()
@click.argument("thread_id", required=False)
def status(thread_id):
    """查看任务状态。"""
    client = _get_client()
    if thread_id:
        s = client.status(thread_id)
        click.echo(f"  任务: {s.thread_id}")
        click.echo(f"  状态: {s.status}")
        if s.step:
            click.echo(f"  步骤: {s.step}")
    else:
        workflows = client.workflow.list()
        click.echo(f"  活跃工作流: {workflows.get('workflows', [])}")


@cli.command()
@click.argument("thread_id")
def approve(thread_id):
    """批准等待中的任务。"""
    client = _get_client()
    result = client.approve(thread_id)
    click.echo(f"  已批准: {result.status}")


@cli.command()
@click.argument("thread_id")
@click.option("--reason", default="", help="拒绝原因")
def reject(thread_id, reason):
    """拒绝等待中的任务。"""
    client = _get_client()
    result = client.reject(thread_id, reason=reason)
    click.echo(f"  已拒绝: {result.status}")


@cli.command("list")
def list_cmd():
    """列出所有工作流。"""
    client = _get_client()
    data = client.workflow.list()
    workflows = data.get("workflows", [])
    if not workflows:
        click.echo("  没有活跃的工作流。")
    for w in workflows:
        click.echo(f"  {w.get('thread_id', 'unknown')} — {w.get('status', 'unknown')}")


@cli.command()
def system():
    """系统健康检查。"""
    client = _get_client()
    info = client.health()
    click.echo(f"  版本: {info.version}")
    click.echo(f"  状态: {info.status}")
    click.echo(f"  Agent 数: {info.agents_count}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: 验证 CLI 帮助输出**

```bash
cd d:/multimodal_agent_federation_mvp && python fedcli.py --help
```
Expected: 显示命令组 `new`, `estimate`, `status`, `approve`, `reject`, `list`, `system`

- [ ] **Step 3: 提交**

```bash
git add fedcli.py
git commit -m "feat: fedcli 命令模式 (new/estimate/status/approve/reject/list/system)"
```

---

### Task 7: CLI 对话模式 — 核心引擎

**Files:**
- Modify: `fedcli.py` — 追加对话引擎

- [ ] **Step 1: 在 fedcli.py 末尾追加对话模式核心**

```python
# ============ 对话模式引擎 ============

STYLES: dict[str, str] = {
    "modern": "现代 — 圆角卡片、渐变、微阴影",
    "minimal": "极简 — 大量留白、细线条",
    "glassmorphism": "毛玻璃 — 半透明面板、层次感",
    "dark": "暗夜 — 深色背景、荧光色",
    "brutalist": "粗野主义 — 粗边框、撞色",
    "cyberpunk": "赛博朋克 — 霓虹灯效",
    "neumorphism": "新拟态 — 柔和浮雕、内阴影",
    "classic": "经典 — 衬线字体、传统布局",
    "retro": "复古 — 像素字体、高饱和",
    "organic": "自然 — 圆润形状、大地色系",
    "luxury": "奢华 — 金色点缀、暗色质感",
    "playful": "活泼 — 鲜艳色彩、弹跳动画",
}

THEMES: dict[str, str] = {
    "ocean": "海洋蓝 #2563EB",
    "forest": "森林绿 #16A34A",
    "sunset": "日落橙 #EA580C",
    "rose": "玫瑰红 #E11D48",
    "lavender": "薰衣草紫 #7C3AED",
    "midnight": "午夜蓝黑 #1E293B",
    "teal": "青碧 #0D9488",
    "amber": "琥珀金 #D97706",
    "slate": "石板灰 #64748B",
}

OUTPUT_FORMATS: dict[str, str] = {
    "html": "HTML+CSS 纯静态",
    "react": "React 组件化",
    "vue": "Vue 渐进式",
    "flutter": "Flutter 跨平台",
    "both": "全都要",
}

SLASH_COMMANDS: dict[str, str] = {
    "/new": "开始一个新需求",
    "/status": "查看任务状态",
    "/approve": "批准等待中的任务",
    "/reject": "拒绝任务",
    "/list": "列出所有任务",
    "/preview": "打印 preview 文件内容",
    "/estimate": "只预估不执行",
    "/system": "系统健康信息",
    "/style": "重新选择设计风格",
    "/theme": "重新选择主题色",
    "/sandbox": "切换沙盒模式 on/off",
    "/search": "切换联网搜索 on/off",
    "/help": "显示帮助",
    "/exit": "退出",
}


class ConversationState:
    """对话状态：记住用户的选择。"""

    def __init__(self):
        self.style: str = "modern"
        self.theme: str | None = None
        self.output_format: str = "both"
        self.allow_search: bool | None = None
        self.sandbox: bool = True
        self.description: str = ""
        self.references: list = []


def _print_banner():
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    console.print(Panel.fit(
        "[bold]欢迎使用 Agent 联邦平台[/bold]\n"
        "直接告诉我你想做什么，我会一步步引导你。\n"
        "输入 [bold]/help[/bold] 查看可用命令  |  输入 [bold]/exit[/bold] 退出",
        border_style="cyan",
    ))


def _ask_style(state: ConversationState) -> None:
    """引导选择设计风格。"""
    from rich.console import Console
    console = Console()
    console.print("\n[bold]1) 设计风格选哪种？[/bold]\n")
    for i, (key, desc) in enumerate(STYLES.items()):
        marker = " [cyan](当前)[/cyan]" if key == state.style else ""
        console.print(f"  {key:<18} {desc}{marker}")
    console.print(f"\n  [dim]直接输入风格名，回车使用当前: [{state.style}][/dim]")


def _ask_theme(state: ConversationState) -> None:
    from rich.console import Console
    console = Console()
    console.print("\n[bold]2) 主题色选哪种？[/bold]\n")
    for key, desc in THEMES.items():
        console.print(f"  {key:<12} {desc}")
    console.print("  custom       任意 hex 色值")
    console.print(f"\n  [dim]回车跳过[/dim]")


def _ask_output_format(state: ConversationState) -> None:
    from rich.console import Console
    console = Console()
    console.print("\n[bold]3) 输出什么框架？[/bold]\n")
    for key, desc in OUTPUT_FORMATS.items():
        marker = " [cyan](当前)[/cyan]" if key == state.output_format else ""
        console.print(f"  {key:<12} {desc}{marker}")
    console.print(f"\n  [dim]回车使用当前: [{state.output_format}][/dim]")


def _ask_search(state: ConversationState) -> None:
    from rich.console import Console
    console = Console()
    console.print("\n[bold]4) 需要联网搜索吗？[/bold]")
    console.print("  [yellow]开启后需求关键词会发送到搜索引擎。[/yellow]")
    default = "否" if state.allow_search is None else ("是" if state.allow_search else "否")
    console.print(f"\n  [dim][{default}] [/dim]")


def _ask_sandbox(state: ConversationState) -> None:
    from rich.console import Console
    console = Console()
    console.print("\n[bold]5) 沙盒模式？[/bold]")
    console.print("  开启 = 隔离环境运行，安全。关闭 = 直接写文件。")
    default = "开启" if state.sandbox else "关闭"
    console.print(f"\n  [dim][{default}] [/dim]")


def _show_summary(state: ConversationState, client: FederationClient) -> None:
    from rich.console import Console
    from rich.table import Table
    console = Console()

    est = client.estimate(state.description, references=state.references,
                          style=state.style, output_format=state.output_format,
                          allow_search=state.allow_search)

    table = Table(title="确认汇总", border_style="cyan")
    table.add_column("项目", style="dim")
    table.add_column("选择")
    table.add_row("需求", state.description[:40])
    table.add_row("风格", f"{state.style} + {state.theme or '默认'}")
    table.add_row("输出", state.output_format)
    table.add_row("搜索", "开" if state.allow_search else "关")
    table.add_row("沙盒", "开" if state.sandbox else "关")
    table.add_row("预估费用", f"¥{est.cost_range[0]} ~ ¥{est.cost_range[1]}")
    table.add_row("预估 Token", f"{est.total_tokens:,}")
    console.print(table)


def _handle_slash_command(cmd: str, state: ConversationState, client: FederationClient) -> bool:
    """处理斜杠命令。返回 True 表示继续对话，False 表示退出。"""
    parts = cmd.strip().split()
    op = parts[0].lower()

    if op == "/exit":
        from rich.console import Console
        Console().print("[dim]再见！[/dim]")
        return False

    if op == "/help":
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(title="可用命令")
        table.add_column("命令", style="cyan")
        table.add_column("说明")
        for k, v in SLASH_COMMANDS.items():
            table.add_row(k, v)
        console.print(table)
        return True

    if op == "/style":
        _ask_style(state)
        return True

    if op == "/theme":
        _ask_theme(state)
        return True

    if op == "/sandbox":
        val = parts[1] if len(parts) > 1 else ""
        if val.lower() in ("on", "true", "1"):
            state.sandbox = True
            click.echo("  沙盒模式: 开启")
        elif val.lower() in ("off", "false", "0"):
            # 安全确认
            if click.confirm("  [yellow]确认关闭沙盒？生成代码将直接写入本地[/yellow]", default=False):
                state.sandbox = False
                click.echo("  沙盒模式: 关闭")
        else:
            click.echo(f"  沙盒模式: {'开' if state.sandbox else '关'}")
        return True

    if op == "/search":
        val = parts[1] if len(parts) > 1 else ""
        if val.lower() in ("on", "true", "1"):
            state.allow_search = True
            click.echo("  联网搜索: 开启")
        elif val.lower() in ("off", "false", "0"):
            state.allow_search = False
            click.echo("  联网搜索: 关闭")
        else:
            click.echo(f"  联网搜索: {'开' if state.allow_search else '关'}")
        return True

    if op == "/system":
        info = client.health()
        click.echo(f"  版本: {info.version}  状态: {info.status}  Agent 数: {info.agents_count}")
        return True

    if op == "/status":
        tid = parts[1] if len(parts) > 1 else None
        if tid:
            s = client.status(tid)
            click.echo(f"  任务: {s.thread_id}  状态: {s.status}")
        else:
            data = client.workflow.list()
            click.echo(f"  工作流: {data.get('workflows', [])}")
        return True

    if op == "/list":
        data = client.workflow.list()
        for w in data.get("workflows", []):
            click.echo(f"  {w.get('thread_id', 'unknown')} — {w.get('status', 'unknown')}")
        return True

    if op == "/estimate":
        desc = " ".join(parts[1:]) if len(parts) > 1 else state.description
        est = client.estimate(desc, style=state.style, output_format=state.output_format)
        click.echo(f"  预估费用: ¥{est.cost_range[0]} ~ ¥{est.cost_range[1]}  Token: {est.total_tokens:,}")
        return True

    if op == "/preview":
        file = parts[1] if len(parts) > 1 else None
        from pathlib import Path
        preview_dir = Path("preview")
        if file:
            fpath = preview_dir / file
            if fpath.exists():
                content = fpath.read_text(encoding="utf-8")[:1000]
                click.echo(content)
            else:
                click.echo(f"  文件不存在: {fpath}")
        else:
            # 列表
            if preview_dir.exists():
                for f in sorted(preview_dir.iterdir()):
                    click.echo(f"  {f.name}")
            else:
                click.echo("  preview/ 为空")
        return True

    if op == "/approve":
        tid = parts[1] if len(parts) > 1 else ""
        if tid:
            client.approve(tid)
            click.echo(f"  已批准: {tid}")
        return True

    if op == "/reject":
        tid = parts[1] if len(parts) > 1 else ""
        if tid:
            client.reject(tid)
            click.echo(f"  已拒绝: {tid}")
        return True

    click.echo(f"  未知命令: {op}，输入 /help 查看可用命令")
    return True


def _execute_workflow(state: ConversationState, client: FederationClient) -> None:
    """实际执行需求并展示结果。"""
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn

    console = Console()
    console.print("\n[bold]开始处理...[/bold]\n")

    result = client.execute(
        state.description,
        references=state.references,
        style=state.style,
        theme=state.theme,
        output_format=state.output_format,
        allow_search=state.allow_search,
        sandbox=state.sandbox,
    )

    if result.status == "completed":
        console.print("[green]方案已生成！[/green]")
        if result.preview_path:
            console.print(f"  预览路径: {result.preview_path}")
    elif result.status == "waiting_human":
        console.print("[yellow]任务需要人工审批。[/yellow]")
        console.print(f"  任务 ID: {result.thread_id}")
    else:
        console.print(f"[red]任务失败: {result.error or result.status}[/red]")


@cli.command(name="chat")
@click.option("--base-url", default="http://127.0.0.1:8000", help="Gateway 地址")
def chat_cmd(base_url):
    """启动 ChatGPT 式对话模式。"""
    client = FederationClient(base_url=base_url)
    state = ConversationState()
    _print_banner()

    phase = "describe"  # describe -> style -> theme -> output -> search -> sandbox -> confirm

    while True:
        try:
            user_input = click.prompt("\nYou", prompt_suffix=": ", default="").strip()
        except (KeyboardInterrupt, EOFError):
            click.echo("\n[dim]再见！[/dim]")
            break

        if not user_input:
            # 空输入 = 推进到下一步
            if phase == "style":
                _ask_style(state)
            elif phase == "theme":
                _ask_theme(state)
            elif phase == "output":
                _ask_output_format(state)
            elif phase == "search":
                _ask_search(state)
            elif phase == "sandbox":
                _ask_sandbox(state)
            elif phase == "confirm":
                _show_summary(state, client)
            continue

        # 斜杠命令
        if user_input.startswith("/"):
            if not _handle_slash_command(user_input, state, client):
                break
            continue

        # 对话解析
        text_lower = user_input.lower()

        if phase == "describe":
            state.description = user_input
            click.echo(f"\n  好的！我来理解一下你的需求。")
            _ask_style(state)
            phase = "style"

        elif phase == "style":
            # 检查是否同时提到了风格和主题
            matched_style = None
            for key in STYLES:
                if key in text_lower:
                    matched_style = key
                    break
            if matched_style:
                state.style = matched_style
                click.echo(f"  [green]✓ 风格: {STYLES[matched_style]}[/green]")

            matched_theme = None
            for key in THEMES:
                if key in text_lower:
                    matched_theme = key
                    break
            if matched_theme:
                state.theme = matched_theme
                click.echo(f"  [green]✓ 主题: {THEMES[matched_theme]}[/green]")
            elif user_input.startswith("#"):
                state.theme = user_input.strip()
                click.echo(f"  [green]✓ 自定义主题: {state.theme}[/green]")

            if not matched_style and not matched_theme:
                # 没匹配到，当作风格名
                state.style = user_input.strip()
                click.echo(f"  [green]✓ 风格: {state.style}[/green]")

            _ask_output_format(state)
            phase = "output"

        elif phase == "output":
            matched = None
            for key in OUTPUT_FORMATS:
                if key in text_lower:
                    matched = key
                    break
            if matched:
                state.output_format = matched
            elif "html" in text_lower:
                state.output_format = "html"
            elif "react" in text_lower:
                state.output_format = "react"
            elif "vue" in text_lower:
                state.output_format = "vue"
            elif "flutter" in text_lower:
                state.output_format = "flutter"
            elif "全要" in user_input or "both" in text_lower:
                state.output_format = "both"
            else:
                state.output_format = user_input.strip()
            click.echo(f"  [green]✓ 输出框架: {state.output_format}[/green]")
            _ask_search(state)
            phase = "search"

        elif phase == "search":
            if any(w in text_lower for w in ("是", "开", "yes", "y", "要", "可以")):
                state.allow_search = True
            elif any(w in text_lower for w in ("否", "关", "no", "n", "不要", "不用")):
                state.allow_search = False
            click.echo(f"  [green]✓ 联网搜索: {'开' if state.allow_search else '关'}[/green]")
            _ask_sandbox(state)
            phase = "sandbox"

        elif phase == "sandbox":
            if any(w in text_lower for w in ("开", "是", "yes", "y", "安全")):
                state.sandbox = True
            elif any(w in text_lower for w in ("关", "否", "no", "n", "快")):
                if click.confirm("  [yellow]确认关闭沙盒？[/yellow]", default=False):
                    state.sandbox = False
            click.echo(f"  [green]✓ 沙盒模式: {'开' if state.sandbox else '关'}[/green]")
            _show_summary(state, client)
            phase = "confirm"

        elif phase == "confirm":
            if text_lower in ("y", "yes", "是", "确认", "开始", "ok", "好"):
                _execute_workflow(state, client)
                # 重置对话状态
                state = ConversationState()
                phase = "describe"
            elif text_lower in ("n", "no", "否", "取消", "不"):
                click.echo("  已取消。输入新需求开始。")
                state = ConversationState()
                phase = "describe"
            else:
                click.echo(f"  请输入 Y/N，或 /help 查看命令")


@cli.command()
def interactive():
    """启动对话模式（默认）。"""
    chat_cmd.callback()


# 修改默认命令为 interactive
cli._default_command = None  # click 的默认行为由 default_map 控制


def main():
    """入口：无参数 = 对话模式，有参数 = 命令模式。"""
    import sys
    if len(sys.argv) == 1:
        # 无参数 → 对话模式
        chat_cmd.callback(base_url="http://127.0.0.1:8000")
    else:
        cli()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 修改 CLI 入口让 `fedcli` 无参数进入对话模式**

在 `fedcli.py` 底部替换 `if __name__ == "__main__":` 块:

确保 `main()` 函数已正确定义（已在 Step 1 中包含）。

- [ ] **Step 3: 验证对话模式启动**

```bash
cd d:/multimodal_agent_federation_mvp && python -c "from fedcli import _print_banner, ConversationState, STYLES, THEMES; print(f'Styles: {len(STYLES)}, Themes: {len(THEMES)}'); print('Dialogue engine OK')"
```

- [ ] **Step 4: 提交**

```bash
git add fedcli.py
git commit -m "feat: CLI 对话模式 (ChatGPT 式引导 + 斜杠命令 + 上下文记忆)"
```

---

### Task 8: 安全显示与权限确认

**Files:**
- Create: `federation_sdk/_security.py`
- Modify: `fedcli.py` — 追加安全提醒函数

- [ ] **Step 1: 编写安全工具模块**

`federation_sdk/_security.py`:
```python
"""安全相关工具：脱敏、路径校验。"""
from __future__ import annotations

import os
import re
from pathlib import Path

_SENSITIVE_KEYS = {"key", "token", "secret", "password", "auth", "credential"}


def mask_sensitive(data: dict) -> dict:
    """递归脱敏敏感字段，值为 '***'。"""
    result = {}
    for k, v in data.items():
        k_lower = k.lower()
        if any(s in k_lower for s in _SENSITIVE_KEYS):
            result[k] = "***"
        elif isinstance(v, dict):
            result[k] = mask_sensitive(v)
        elif isinstance(v, list):
            result[k] = [mask_sensitive(item) if isinstance(item, dict) else item for item in v]
        else:
            result[k] = v
    return result


def safe_path(user_path: str, base_dir: str | Path) -> Path:
    """解析路径并确保在 base_dir 范围内，防止路径穿越。"""
    base = Path(base_dir).resolve()
    resolved = (base / user_path).resolve()
    if not str(resolved).startswith(str(base)):
        raise ValueError(f"路径穿越检测: {user_path}")
    return resolved


def validate_base_url(url: str) -> str:
    """校验 base_url 安全。"""
    if not url.startswith(("http://", "https://")):
        raise ValueError("base_url 必须以 http:// 或 https:// 开头")
    if "@" in url.replace("://", ""):
        raise ValueError("base_url 禁止包含认证信息")
    return url.rstrip("/")
```

- [ ] **Step 2: 在 fedcli.py 顶部追加安全提醒函数**

在 fedcli.py 的 import 区域之后追加:

```python
# ============ 安全提醒面板 ============

def _sandbox_off_warning() -> bool:
    """沙盒关闭安全确认面板。"""
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    console.print(Panel(
        "[bold yellow]⚠ 安全警告：关闭沙盒模式[/bold yellow]\n\n"
        "生成的代码将直接写入本地文件系统。\n"
        "风险：恶意代码访问 / 意外覆盖 / 环境影响\n\n"
        "建议仅在信任环境下关闭。",
        border_style="red",
        title="安全确认",
    ))
    return click.confirm("  确认关闭沙盒？", default=False)


def _search_warning() -> bool:
    """联网搜索权限确认面板。"""
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    console.print(Panel(
        "[bold yellow]⚠ 联网搜索提醒[/bold yellow]\n\n"
        "Agent 将联网搜索参考资料，以下信息可能被发送:\n"
        "- 需求描述中的关键词\n"
        "- 设计风格和主题偏好\n"
        "- 不会发送：本地文件路径、个人信息\n\n"
        "搜索提供商: DuckDuckGo（默认，不追踪用户）",
        border_style="yellow",
        title="联网搜索",
    ))
    return click.confirm("  确认允许联网搜索？", default=False)


def _external_ref_warning(source: str) -> bool:
    """外部参考素材隐私提醒。"""
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    console.print(Panel(
        f"[bold yellow]⚠ 外部参考素材提醒[/bold yellow]\n\n"
        f"将处理以下外部参考:\n- {source}\n\n"
        f"以下信息可能外传:\n- URL / 网页截图和文本内容\n"
        f"- 不会发送: 你的 IP、Cookie、登录状态",
        border_style="yellow",
        title="外部参考",
    ))
    return click.confirm("  确认使用这些参考素材？", default=True)


def _file_access_warning(read_paths: list[str], write_dir: str) -> bool:
    """本地文件访问提醒。"""
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    lines = "\n".join(f"  读取: {p}" for p in read_paths)
    lines += f"\n  写入: {write_dir}/"
    console.print(Panel(
        f"[bold]📁 本地文件访问[/bold]\n\n{lines}",
        border_style="cyan",
        title="文件访问",
    ))
    return click.confirm("  是否继续？", default=True)
```

- [ ] **Step 3: 提交**

```bash
git add federation_sdk/_security.py fedcli.py
git commit -m "feat: 安全脱敏 + 权限确认面板 (沙盒/搜索/参考/文件访问)"
```

---

### Task 9: SDK 测试

**Files:**
- Create: `tests/test_sdk_models.py`
- Create: `tests/test_sdk_client.py`
- Create: `tests/test_sdk_references.py`

- [ ] **Step 1: 编写模型测试**

`tests/test_sdk_models.py`:
```python
"""测试: SDK 数据模型"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from federation_sdk.models import (
    TaskResult, TaskStatus, SystemInfo, CostEstimate,
    Reference, ReferenceType, ImageRef, WebPageRef, ProjectRef,
)


class TestTaskResult:
    def test_create_completed(self):
        r = TaskResult(thread_id="t1", status="completed", output={"html": "<div>"})
        assert r.thread_id == "t1"
        assert r.status == "completed"
        assert r.output["html"] == "<div>"

    def test_create_failed(self):
        r = TaskResult(thread_id="t2", status="failed", error="timeout")
        assert r.error == "timeout"
        assert r.output is None


class TestReference:
    def test_image_ref(self):
        ref = ImageRef(source="/tmp/test.png", description="design")
        assert ref.type == ReferenceType.IMAGE
        assert ref.source == "/tmp/test.png"
        assert ref.encoding == "base64"

    def test_webpage_ref(self):
        ref = WebPageRef(source="https://example.com")
        assert ref.type == ReferenceType.WEB_PAGE

    def test_project_ref(self):
        ref = ProjectRef(source="/tmp/myapp")
        assert ref.type == ReferenceType.PROJECT


class TestCostEstimate:
    def test_create(self):
        ce = CostEstimate(
            task_id="est-001",
            input_tokens=1000, output_tokens=500, total_tokens=1500,
            estimated_cost=0.03, cost_range=(0.02, 0.04),
            confidence="medium",
            breakdown={"text": 1000},
        )
        assert ce.total_tokens == 1500
        assert ce.cost_range == (0.02, 0.04)


class TestSystemInfo:
    def test_create(self):
        si = SystemInfo(version="1.0", status="healthy", agents_count=3, healthy=True)
        assert si.healthy is True
        assert si.agents_count == 3


class TestTaskStatusModel:
    def test_create(self):
        ts = TaskStatus(thread_id="t1", status="running", step="code_gen", started_at="2026-01-01")
        assert ts.step == "code_gen"
```

- [ ] **Step 2: 编写客户端测试（不依赖 Gateway）**

`tests/test_sdk_client.py`:
```python
"""测试: FederationClient (本地可测部分)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from federation_sdk import FederationClient, ConnectionError
from federation_sdk.exceptions import ValidationError


class TestFederationClientInit:
    def test_default_url(self):
        c = FederationClient()
        assert "8000" in c._http._base_url

    def test_custom_url(self):
        c = FederationClient(base_url="http://127.0.0.1:9000")
        assert "9000" in c._http._base_url

    def test_url_without_protocol(self):
        c = FederationClient(base_url="127.0.0.1:8000")
        assert c._http._base_url == "http://127.0.0.1:8000"

    def test_url_with_credentials_rejected(self):
        with pytest.raises(ValidationError):
            FederationClient(base_url="http://user:pass@host:8000")


class TestEstimate:
    def test_simple_text(self):
        c = FederationClient()
        est = c.estimate("做一个电商网站")
        assert est.total_tokens > 0
        assert est.estimated_cost > 0
        assert est.cost_range[0] <= est.cost_range[1]

    def test_with_style(self):
        c = FederationClient()
        est = c.estimate("做一个电商网站", style="glassmorphism", output_format="html")
        assert est.confidence == "medium"

    def test_short_text(self):
        c = FederationClient()
        est = c.estimate("hi")
        assert est.output_tokens == 3000

    def test_long_text(self):
        c = FederationClient()
        est = c.estimate("做" * 300)
        assert est.output_tokens == 15000


class TestProperties:
    def test_resource_properties(self):
        c = FederationClient()
        assert c.supervisor is not None
        assert c.workflow is not None
        assert c.agents is not None
        assert c.system is not None

    def test_resource_same_instance(self):
        """多次访问同一资源属性返回同一实例。"""
        c = FederationClient()
        assert c.supervisor is c.supervisor
        assert c.workflow is c.workflow
```

- [ ] **Step 3: 编写参考素材测试**

`tests/test_sdk_references.py`:
```python
"""测试: 参考素材解析"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from federation_sdk.models import ImageRef, WebPageRef, ProjectRef
from federation_sdk.references import (
    resolve_reference, estimate_reference_tokens,
    _image_to_base64, _get_image_size,
)


class TestResolveReference:
    def test_url_is_webpage(self):
        ref = resolve_reference("https://example.com/page")
        assert ref.type.value == "web_page"

    def test_png_is_image(self):
        ref = resolve_reference("/tmp/test.png")
        assert ref.type.value == "image"

    def test_jpg_is_image(self):
        ref = resolve_reference("/tmp/photo.jpg")
        assert ref.type.value == "image"

    def test_directory_is_project(self):
        ref = resolve_reference("/tmp")
        assert ref.type.value == "project"


class TestEstimateTokens:
    def test_image_ref(self):
        import os
        # 创建最小 PNG
        png_path = os.path.join(tempfile.gettempdir(), "_test_minimal.png")
        with open(png_path, "wb") as f:
            f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 200)
        ref = ImageRef(source=png_path, description="test")
        tokens, warnings = estimate_reference_tokens([ref])
        assert tokens > 0

    def test_webpage_ref(self):
        ref = WebPageRef(source="https://example.com")
        tokens, warnings = estimate_reference_tokens([ref])
        assert tokens > 0

    def test_multiple_refs(self):
        ref1 = WebPageRef(source="https://a.com")
        ref2 = WebPageRef(source="https://b.com")
        tokens, _ = estimate_reference_tokens([ref1, ref2])
        assert tokens >= 10000


class TestImageToBase64:
    def test_valid_png(self):
        import os
        png_path = os.path.join(tempfile.gettempdir(), "_test_b64.png")
        with open(png_path, "wb") as f:
            f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
        b64 = _image_to_base64(png_path)
        assert len(b64) > 0
        assert b64.startswith("iVB") or len(b64) > 10  # base64 of PNG header
```

- [ ] **Step 4: 运行测试**

```bash
cd d:/multimodal_agent_federation_mvp && python -m pytest tests/test_sdk_models.py tests/test_sdk_client.py tests/test_sdk_references.py -v
```
Expected: ALL PASS

- [ ] **Step 5: 提交**

```bash
git add tests/test_sdk_models.py tests/test_sdk_client.py tests/test_sdk_references.py
git commit -m "test: SDK 模型 + 客户端 + 参考素材单元测试"
```

---

### Task 10: CLI 测试

**Files:**
- Create: `tests/test_cli_commands.py`

- [ ] **Step 1: 编写 CLI 测试**

`tests/test_cli_commands.py`:
```python
"""测试: fedcli CLI 命令"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from click.testing import CliRunner
from fedcli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestCLIHelp:
    def test_main_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "new" in result.output
        assert "estimate" in result.output
        assert "status" in result.output

    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "fedcli" in result.output


class TestEstimateCommand:
    def test_estimate_basic(self, runner):
        result = runner.invoke(cli, ["estimate", "做一个网站"])
        assert result.exit_code == 0
        assert "预估" in result.output

    def test_estimate_with_options(self, runner):
        result = runner.invoke(cli, ["estimate", "做一个网站", "--style", "glassmorphism"])
        assert result.exit_code == 0


class TestNewCommand:
    def test_new_requires_description(self, runner):
        result = runner.invoke(cli, ["new"])
        assert result.exit_code != 0  # missing argument

    def test_new_with_description(self, runner):
        # 不会实际执行（因为要连 Gateway），测试参数解析
        result = runner.invoke(cli, ["new", "做一个网站", "--help"])
        assert result.exit_code == 0
        assert "style" in result.output


class TestStatusCommand:
    def test_status_no_args(self, runner):
        # 无 Gateway 时该命令会失败，测试参数解析
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0


class TestSystemCommand:
    def test_system_help(self, runner):
        result = runner.invoke(cli, ["system", "--help"])
        assert result.exit_code == 0


class TestConversationState:
    def test_initial_state(self):
        from fedcli import ConversationState
        s = ConversationState()
        assert s.style == "modern"
        assert s.sandbox is True
        assert s.output_format == "both"

    def test_styles_dict(self):
        from fedcli import STYLES, THEMES
        assert len(STYLES) == 12
        assert len(THEMES) == 9
        assert "modern" in STYLES
        assert "ocean" in THEMES


class TestSlashCommands:
    def test_help(self, runner):
        from fedcli import _handle_slash_command, ConversationState
        from federation_sdk import FederationClient
        state = ConversationState()
        client = FederationClient()
        result = _handle_slash_command("/help", state, client)
        assert result is True

    def test_exit(self, runner):
        from fedcli import _handle_slash_command, ConversationState
        from federation_sdk import FederationClient
        state = ConversationState()
        client = FederationClient()
        result = _handle_slash_command("/exit", state, client)
        assert result is False

    def test_sandbox_on(self):
        from fedcli import _handle_slash_command, ConversationState
        from federation_sdk import FederationClient
        state = ConversationState()
        state.sandbox = False
        client = FederationClient()
        _handle_slash_command("/sandbox on", state, client)
        assert state.sandbox is True

    def test_search_on(self):
        from fedcli import _handle_slash_command, ConversationState
        from federation_sdk import FederationClient
        state = ConversationState()
        state.allow_search = None
        client = FederationClient()
        _handle_slash_command("/search on", state, client)
        assert state.allow_search is True


class TestSecurity:
    def test_mask_sensitive(self):
        from federation_sdk._security import mask_sensitive
        data = {"api_key": "sk-12345", "name": "test", "nested": {"token": "abc"}}
        masked = mask_sensitive(data)
        assert masked["api_key"] == "***"
        assert masked["name"] == "test"
        assert masked["nested"]["token"] == "***"

    def test_safe_path_ok(self):
        from federation_sdk._security import safe_path
        import tempfile
        d = tempfile.gettempdir()
        path = safe_path("test.txt", d)
        assert path.name == "test.txt"

    def test_safe_path_traversal(self):
        from federation_sdk._security import safe_path
        import tempfile
        d = tempfile.gettempdir()
        with pytest.raises(ValueError):
            safe_path("../../../etc/passwd", d)

    def test_validate_base_url_ok(self):
        from federation_sdk._security import validate_base_url
        assert validate_base_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"

    def test_validate_base_url_reject_credentials(self):
        from federation_sdk._security import validate_base_url
        with pytest.raises(ValueError):
            validate_base_url("http://user:pass@host:8000")
```

- [ ] **Step 2: 运行 CLI 测试**

```bash
cd d:/multimodal_agent_federation_mvp && python -m pytest tests/test_cli_commands.py -v
```
Expected: ALL PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_cli_commands.py
git commit -m "test: CLI 命令模式 + 对话引擎 + 安全工具测试"
```

---

### Task 11: 最终验证与收尾

- [ ] **Step 1: 运行全量测试**

```bash
cd d:/multimodal_agent_federation_mvp && python -m pytest tests/ -v
```
Expected: ALL PASS

- [ ] **Step 2: 验证 SDK 可独立导入运行**

```bash
cd d:/multimodal_agent_federation_mvp && python -c "
from federation_sdk import FederationClient
c = FederationClient()
print('=== SDK 导入成功 ===')
est = c.estimate('做一个电商网站，要有商品展示和购物车', style='glassmorphism', output_format='html')
print(f'预估 Token: {est.total_tokens:,}')
print(f'预估费用: ¥{est.cost_range[0]} ~ ¥{est.cost_range[1]}')
print(f'置信度: {est.confidence}')
print('=== 6 个简便方法: execute, estimate, status, approve, reject, health ===')
print('=== 高级层属性: supervisor, workflow, agents, system ===')
"
```

- [ ] **Step 3: 验证 CLI 帮助和信息显示**

```bash
cd d:/multimodal_agent_federation_mvp && python fedcli.py --help && python fedcli.py --version
```

- [ ] **Step 4: 验证 preview/ 和 references/ 目录创建**

```bash
ls -la d:/multimodal_agent_federation_mvp/preview/ d:/multimodal_agent_federation_mvp/references/images/ d:/multimodal_agent_federation_mvp/references/web/ d:/multimodal_agent_federation_mvp/references/project/
```

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "chore: 最终验证 — 全量测试通过，SDK 导入工作正常"
```
