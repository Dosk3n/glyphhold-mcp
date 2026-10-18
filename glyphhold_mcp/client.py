from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

SAFE_VAULT_ERRORS = {
    "vault_item_not_found": "Vault item not found; search again and use a current ID",
    "vault_unavailable": "External vault unavailable; test the saved connection.",
    "secret_values_differ": "Values differ; both secrets retained. Ask the user.",
    "vault_status_failed": "Vault status failed. Test the saved connection or repeat this read.",
    "vault_config_failed": "Vault config failed. Test the saved connection or repeat this read.",
    "vault_login_failed": "Vault login failed. Test the saved connection or repeat this read.",
    "vault_unlock_failed": "Vault unlock failed. Test the saved connection or repeat this read.",
    "vault_sync_failed": "Vault sync failed. Test the saved connection or repeat this read.",
    "vault_get_failed": "Vault get failed. Test the saved connection or repeat this read.",
    "vault_list_failed": "Vault list failed. Test the saved connection or repeat this read.",
    "vault_create_failed": "Vault create failed. Check the destination before retrying.",
    "vault_edit_failed": "Vault edit failed. Check the destination before retrying.",
    "vault_operation_failed": "Vault operation failed. Test the saved connection.",
}


class GlyphHoldError(RuntimeError):
    """A safe, structured failure returned by the Glyph Hold API client."""

    def __init__(
        self,
        message: str,
        *,
        kind: str = "glyphhold_error",
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code
        self.retryable = retryable

    def as_tool_error(self) -> dict[str, Any]:
        error: dict[str, Any] = {
            "type": self.kind,
            "message": str(self),
            "retryable": self.retryable,
        }
        if self.status_code is not None:
            error["status"] = self.status_code
        return error


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
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=max(self.timeout_seconds, 90)
                if path.startswith("/api/v2/secrets")
                else self.timeout_seconds,
                verify=self.verify_ssl,
                transport=self.transport,
            ) as client:
                response = await client.request(method, path, json=json, params=params)
        except httpx.TimeoutException as exc:
            raise GlyphHoldError(
                "Glyph Hold request timed out.",
                kind="timeout",
                retryable=True,
            ) from exc
        except httpx.RequestError as exc:
            raise GlyphHoldError(
                "Could not connect to Glyph Hold.",
                kind="connection_error",
                retryable=True,
            ) from exc

        if response.status_code >= 400:
            detail = response.reason_phrase or "Request failed"
            try:
                payload = response.json()
                if isinstance(payload, Mapping):
                    api_detail = payload.get("detail")
                    if isinstance(api_detail, str) and api_detail.strip():
                        detail = api_detail.strip()[:500]
            except ValueError:
                pass
            code = response.headers.get("X-GlyphHold-Error", "")
            detail = SAFE_VAULT_ERRORS.get(code, detail)
            status_code = response.status_code
            kind = {
                401: "authentication_error",
                403: "authorization_error",
                404: "not_found",
                409: "conflict",
                422: "validation_error",
                429: "rate_limited",
            }.get(status_code, "upstream_error" if status_code >= 500 else "request_error")
            raise GlyphHoldError(
                f"Glyph Hold request failed: HTTP {status_code}: {detail}",
                kind=kind,
                status_code=status_code,
                retryable=(status_code == 429 or status_code >= 500)
                and code not in {"vault_create_failed", "vault_edit_failed"},
            )

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise GlyphHoldError(
                "Glyph Hold returned an invalid JSON response.",
                kind="invalid_response",
                status_code=response.status_code,
                retryable=response.status_code >= 500,
            ) from exc

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

    @staticmethod
    def _memory_path(memory_id: str) -> str:
        from urllib.parse import quote

        return "/api/v2/memories/" + quote(memory_id, safe="")

    async def capabilities(self):
        return await self._request("GET", "/api/v2/capabilities")

    async def list_memories(self, **params):
        return await self._request("GET", "/api/v2/memories", params=self._params(**params))

    async def get_memory(self, *, memory_id: str):
        return await self._request("GET", self._memory_path(memory_id))

    async def search_memories(
        self,
        *,
        query: str,
        space_id: str | None = None,
        session_id: str | None = None,
        broaden: bool = False,
        limit: int = 10,
        max_chars: int = 12000,
    ):
        return await self._request(
            "POST",
            "/api/v2/search",
            json=self._json(
                query=query,
                space_id=space_id,
                session_id=session_id,
                broaden=broaden,
                limit=limit,
                max_chars=max_chars,
            ),
        )

    async def prefetch_memories(
        self,
        *,
        message: str,
        space_id: str | None = None,
        session_id: str | None = None,
        max_memories: int = 5,
        max_chars: int = 2400,
    ):
        return await self._request(
            "POST",
            "/api/v2/recall",
            json=self._json(
                query=message,
                space_id=space_id,
                session_id=session_id,
                limit=max_memories,
                max_chars=max_chars,
            ),
        )

    async def create_memory(self, *, title: str, body: str, idempotency_key: str, **fields):
        return await self._request(
            "POST",
            "/api/v2/memories",
            json=self._json(title=title, body=body, idempotency_key=idempotency_key, **fields),
        )

    async def update_memory(self, *, memory_id: str, expected_version: int, **fields):
        return await self._request(
            "PATCH",
            self._memory_path(memory_id),
            json=self._json(expected_version=expected_version, **fields),
        )

    async def archive_memory(self, *, memory_id: str, expected_version: int):
        return await self._request(
            "POST",
            self._memory_path(memory_id) + "/archive",
            json={"expected_version": expected_version},
        )

    async def move_memory(self, *, memory_id: str, space_id: str, expected_version: int):
        return await self._request(
            "POST",
            self._memory_path(memory_id) + "/move",
            json={"space_id": space_id, "expected_version": expected_version},
        )

    async def list_memory_revisions(self, *, memory_id: str):
        return await self._request("GET", self._memory_path(memory_id) + "/revisions")

    async def restore_memory_revision(
        self, *, memory_id: str, revision_id: str, expected_version: int
    ):
        return await self._request(
            "POST",
            self._memory_path(memory_id) + "/restore",
            json={"revision_id": revision_id, "expected_version": expected_version},
        )

    async def get_context(self, *, session_id: str):
        return await self._request("GET", "/api/v2/context", params={"session_id": session_id})

    async def set_context(self, *, session_id: str, space_id: str):
        return await self._request(
            "PUT", "/api/v2/context", json={"session_id": session_id, "space_id": space_id}
        )

    async def placement_guidance(self, *, space_id: str | None = None):
        return await self._request(
            "GET", "/api/v2/guidance", params=self._params(space_id=space_id)
        )

    async def search_secrets(
        self, *, query: str = "", space_id: str | None = None, provider_name: str | None = None
    ):
        return await self._request(
            "GET",
            "/api/v2/secrets",
            params=self._params(query=query, space_id=space_id, provider_name=provider_name),
        )

    async def get_secret_metadata(self, *, id_or_name: str, space_id: str | None = None):
        from urllib.parse import quote

        return await self._request(
            "GET",
            "/api/v2/secrets/" + quote(id_or_name, safe=""),
            params=self._params(space_id=space_id),
        )

    async def create_secret(
        self,
        *,
        name: str,
        value: str,
        space_id: str | None = None,
        description: str | None = None,
        value_type: str = "text",
        folder_id: str | None = None,
        username: str | None = None,
        uri: str | None = None,
    ):
        return await self._request(
            "POST",
            "/api/v2/secrets",
            json=self._json(
                name=name,
                value=value,
                space_id=space_id,
                description=description,
                value_type=value_type,
                folder_id=folder_id,
                username=username,
                uri=uri,
            ),
        )

    async def reveal_secret(
        self, *, id_or_name: str, space_id: str | None = None, field: str | None = None
    ):
        from urllib.parse import quote

        return await self._request(
            "POST",
            "/api/v2/secrets/" + quote(id_or_name, safe="") + "/reveal",
            json=self._json(field=field),
            params=self._params(space_id=space_id),
        )

    async def list_secret_folders(self):
        return await self._request("GET", "/api/v2/secrets/folders")

    async def create_secret_folder(self, *, name: str):
        return await self._request("POST", "/api/v2/secrets/folders", json={"name": name})

    async def update_secret(
        self, *, id_or_name: str, expected_version: int | str, value: str, field: str | None = None
    ):
        from urllib.parse import quote

        return await self._request(
            "PATCH",
            "/api/v2/secrets/" + quote(id_or_name, safe=""),
            json=self._json(expected_version=expected_version, value=value, field=field),
        )

    async def migrate_secret(
        self,
        *,
        id_or_name: str,
        expected_version: int,
        target_id: str | None = None,
        field: str | None = None,
        folder_id: str | None = None,
        dry_run: bool = False,
    ):
        from urllib.parse import quote

        return await self._request(
            "POST",
            "/api/v2/secrets/"
            + quote(id_or_name, safe="")
            + ("/migrate/preview" if dry_run else "/migrate"),
            json=self._json(
                expected_version=expected_version,
                target_id=target_id,
                field=field,
                folder_id=folder_id,
                **({"dry_run": True} if dry_run else {}),
            ),
        )
