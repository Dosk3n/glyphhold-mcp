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

    @staticmethod
    def _params(**values: Any) -> dict[str, Any]:
        return {key: value for key, value in values.items() if value is not None}

    @staticmethod
    def _json(**values: Any) -> dict[str, Any]:
        return {key: value for key, value in values.items() if value is not None}

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/health")

    async def list_categories(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/v1/categories")

    async def list_memories(
        self,
        *,
        category: str | None = None,
        tag: str | None = None,
        include_archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return await self._request(
            "GET",
            "/api/v1/memories",
            params=self._params(
                category=category,
                tag=tag,
                include_archived=include_archived,
                limit=limit,
                offset=offset,
            ),
        )

    async def get_memory(self, *, memory_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/memories/{memory_id}")

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

    async def find_similar_memories(
        self,
        *,
        title: str,
        body: str,
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/memories/find-similar",
            json={
                "category": category,
                "title": title,
                "body": body,
                "tags": tags or [],
                "limit": limit,
            },
        )

    async def prepare_memory_write(
        self,
        *,
        title: str,
        body: str,
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/memories/prepare-write",
            json={
                "category": category,
                "title": title,
                "body": body,
                "tags": tags or [],
                "limit": limit,
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

    async def update_memory(
        self,
        *,
        memory_id: str,
        category_id: str | None = None,
        title: str | None = None,
        summary: str | None = None,
        body: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        source: str | None = None,
        confidence: int | None = None,
        auto_prefetch_level: str | None = None,
        archived: bool | None = None,
        superseded_by: str | None = None,
        change_reason: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/api/v1/memories/{memory_id}",
            json=self._json(
                category_id=category_id,
                title=title,
                summary=summary,
                body=body,
                tags=tags,
                metadata=metadata,
                source=source,
                confidence=confidence,
                auto_prefetch_level=auto_prefetch_level,
                archived=archived,
                superseded_by=superseded_by,
                change_reason=change_reason,
            ),
        )

    async def delete_memory(self, *, memory_id: str) -> None:
        return await self._request("DELETE", f"/api/v1/memories/{memory_id}")

    async def update_memory_confidence(
        self,
        *,
        memory_id: str,
        confidence: int,
        change_reason: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/memories/{memory_id}/confidence",
            json=self._json(confidence=confidence, change_reason=change_reason),
        )

    async def archive_memory(self, *, memory_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/api/v1/memories/{memory_id}/archive", json={})

    async def supersede_memory(self, *, memory_id: str, superseded_by: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/memories/{memory_id}/supersede",
            json={"superseded_by": superseded_by},
        )

    async def list_memory_revisions(self, *, memory_id: str) -> list[dict[str, Any]]:
        return await self._request("GET", f"/api/v1/memories/{memory_id}/revisions")

    async def restore_memory_revision(
        self,
        *,
        memory_id: str,
        revision_id: str,
        change_reason: str | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/memories/{memory_id}/revisions/{revision_id}/restore",
            json=self._json(change_reason=change_reason),
        )

    async def list_secrets(
        self,
        *,
        query: str | None = None,
        service: str | None = None,
        host: str | None = None,
        scope: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return await self._request(
            "GET",
            "/api/v1/secrets",
            params=self._params(
                query=query,
                service=service,
                host=host,
                scope=scope,
                limit=limit,
                offset=offset,
            ),
        )

    async def get_secret_metadata(self, *, id_or_name: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/secrets/{id_or_name}")

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
        allowed_agents: list[str] | None = None,
        allowed_tools: list[str] | None = None,
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
                "allowed_agents": allowed_agents or [],
                "allowed_tools": allowed_tools or [],
            },
        )

    async def update_secret(
        self,
        *,
        id_or_name: str,
        name: str | None = None,
        value: str | None = None,
        description: str | None = None,
        value_type: str | None = None,
        service: str | None = None,
        host: str | None = None,
        scope: str | None = None,
        tags: list[str] | None = None,
        allowed_agents: list[str] | None = None,
        allowed_tools: list[str] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/api/v1/secrets/{id_or_name}",
            json=self._json(
                name=name,
                value=value,
                description=description,
                value_type=value_type,
                service=service,
                host=host,
                scope=scope,
                tags=tags,
                allowed_agents=allowed_agents,
                allowed_tools=allowed_tools,
            ),
        )

    async def delete_secret(self, *, id_or_name: str) -> None:
        return await self._request("DELETE", f"/api/v1/secrets/{id_or_name}")

    async def reveal_secret(
        self,
        *,
        id_or_name: str,
        requesting_agent: str | None = "codex",
        tool: str | None = None,
        purpose: str = "MCP reveal requested by Codex",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/secrets/{id_or_name}/reveal",
            json=self._json(requesting_agent=requesting_agent, tool=tool, purpose=purpose),
        )

    async def reveal_secret_env(
        self,
        *,
        scope: str | None = None,
        requesting_agent: str | None = "codex",
        purpose: str = "MCP env reveal requested by Codex",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/secrets/env",
            json=self._json(scope=scope, requesting_agent=requesting_agent, purpose=purpose),
        )
