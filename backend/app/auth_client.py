from __future__ import annotations

from typing import Any

import httpx

from .provider import ProviderError


class Sub2APIAuthClient:
    def __init__(self, timeout_seconds: float = 60):
        self.timeout = httpx.Timeout(timeout_seconds, connect=20)

    async def public_settings(self, base_url: str) -> dict[str, Any]:
        return await self._request(base_url, "GET", "/api/v1/settings/public")

    async def send_verify_code(self, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(base_url, "POST", "/api/v1/auth/send-verify-code", json=payload)

    async def register(self, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(base_url, "POST", "/api/v1/auth/register", json=payload)

    async def login(self, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(base_url, "POST", "/api/v1/auth/login", json=payload)

    async def login_2fa(self, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(base_url, "POST", "/api/v1/auth/login/2fa", json=payload)

    async def list_keys(self, base_url: str, access_token: str) -> list[dict[str, Any]]:
        data = await self._request(
            base_url,
            "GET",
            "/api/v1/keys?page=1&page_size=100&sort_by=created_at&sort_order=desc",
            access_token=access_token,
        )
        if isinstance(data, dict):
            items = data.get("items")
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return []

    async def list_available_groups(self, base_url: str, access_token: str) -> list[dict[str, Any]]:
        data = await self._request(
            base_url,
            "GET",
            "/api/v1/groups/available",
            access_token=access_token,
        )
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    async def create_key(self, base_url: str, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = await self._request(
            base_url,
            "POST",
            "/api/v1/keys",
            json=payload,
            access_token=access_token,
        )
        if not isinstance(data, dict):
            raise ProviderError(502, "JokoAI 返回的 API Key 数据格式不正确", data)
        return data

    async def list_usage(self, base_url: str, access_token: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        data = await self._request(
            base_url,
            "GET",
            "/api/v1/usage",
            params=params or {},
            access_token=access_token,
        )
        if isinstance(data, dict):
            items = data.get("items")
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    async def _request(
        self,
        base_url: str,
        method: str,
        path: str,
        *,
        access_token: str | None = None,
        **kwargs: Any,
    ) -> Any:
        url = _join_base(base_url, path)
        headers = kwargs.pop("headers", {})
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.request(method, url, headers=headers, **kwargs)

        payload = _safe_json(response)
        if response.status_code >= 400:
            raise ProviderError(response.status_code, _extract_error_message(payload, response), payload)

        if isinstance(payload, dict) and payload.get("code") not in (None, 0):
            raise ProviderError(response.status_code, _extract_error_message(payload, response), payload)

        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload


def _join_base(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:1000]


def _extract_error_message(payload: Any, response: httpx.Response) -> str:
    if isinstance(payload, dict):
        if payload.get("message"):
            return str(payload["message"])
        if payload.get("reason"):
            return str(payload["reason"])
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if error:
            return str(error)
    return response.text[:1000] or f"JokoAI returned HTTP {response.status_code}"
