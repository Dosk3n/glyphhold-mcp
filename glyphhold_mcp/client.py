from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx


class GlyphHoldError(RuntimeError):
    pass


class GlyphHoldClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 20.0,
        verify_ssl: bool | str = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.verify_ssl = verify_ssl
        self.transport = transport

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout_seconds,
            verify=self.verify_ssl,
            transport=self.transport,
        ) as client:
            response = await client.request(method, path, json=json, params=params)

        if response.status_code >= 400:
            detail = response.text
            try:
                payload = response.json()
                detail = str(payload.get("detail") or detail)
            except ValueError:
                pass
            raise GlyphHoldError(f"Glyph Hold request failed: HTTP {response.status_code}: {detail}")

        if not response.content:
            return None
        return response.json()

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/health")

    async def list_categories(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/v1/categories")

    async def search_memories(
        self,
        *,
        query: str,
        category: str | None = None,
        limit: int = 10,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "include_archived": include_archived,
        }
        if category:
            payload["category"] = category
        return await self._request("POST", "/api/v1/memories/search", json=payload)

    async def prefetch_memories(
        self,
        *,
        message: str,
        agent: str | None = None,
        max_memories: int = 3,
        max_chars: int = 1200,
        max_tokens: int = 300,
        summaries_only: bool = True,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/agent/prefetch",
            json={
                "message": message,
                "agent": agent,
                "max_memories": max_memories,
                "max_chars": max_chars,
                "max_tokens": max_tokens,
                "summaries_only": summaries_only,
            },
        )

    async def create_memory(
        self,
        *,
        category_id: str,
        title: str,
        body: str,
        summary: str | None = None,
        tags: list[str] | None = None,
        confidence: int = 3,
        auto_prefetch_level: str = "normal",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/memories",
            json={
                "category_id": category_id,
                "title": title,
                "summary": summary,
                "body": body,
                "tags": tags or [],
                "confidence": confidence,
                "auto_prefetch_level": auto_prefetch_level,
            },
        )

    async def create_secret(
        self,
        *,
        name: str,
        value: str,
        description: str | None = None,
        value_type: str = "text",
        service: str | None = None,
        host: str | None = None,
        scope: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/secrets",
            json={
                "name": name,
                "value": value,
                "description": description,
                "value_type": value_type,
                "service": service,
                "host": host,
                "scope": scope,
                "tags": tags or [],
            },
        )

    async def reveal_secret(
        self,
        *,
        id_or_name: str,
        purpose: str = "MCP reveal requested by Codex",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/secrets/{id_or_name}/reveal",
            json={"purpose": purpose},
        )
