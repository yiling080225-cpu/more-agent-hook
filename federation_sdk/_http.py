from __future__ import annotations

import httpx
from federation_sdk.exceptions import ConnectionError, TimeoutError, NotFoundError


class _HttpClient:
    """内部 httpx 封装：重试、超时、错误映射。"""

    def __init__(self, base_url: str, timeout: int = 300):
        if "://" not in base_url:
            base_url = f"http://{base_url}"
        if "@" in base_url.replace("://", ""):
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
