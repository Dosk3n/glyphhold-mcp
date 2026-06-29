from __future__ import annotations

import json

import httpx
import pytest

from glyphhold_mcp.client import GlyphHoldClient, GlyphHoldError


def _transport(handler):
    async def wrapped(request: httpx.Request) -> httpx.Response:
        return handler(request)

    return httpx.MockTransport(wrapped)


@pytest.mark.asyncio
async def test_search_memories_sends_bearer_token_and_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/memories/search"
        assert request.headers["authorization"] == "Bearer gh_live_test"
        assert json.loads(request.content) == {
            "query": "glyph hold",
            "limit": 5,
            "include_archived": False,
        }
        return httpx.Response(200, json={"results": [{"title": "Glyph Hold"}]})

    client = GlyphHoldClient(
        base_url="https://glyphhold.example",
        api_key="gh_live_test",
        transport=_transport(handler),
    )

    assert await client.search_memories(query="glyph hold", limit=5) == {
        "results": [{"title": "Glyph Hold"}]
    }


@pytest.mark.asyncio
async def test_reveal_secret_uses_explicit_reveal_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/secrets/CUSTOM_API_KEY/reveal"
        assert json.loads(request.content) == {
            "requesting_agent": "codex",
            "purpose": "test purpose",
        }
        return httpx.Response(200, json={"name": "CUSTOM_API_KEY", "value": "hidden"})

    client = GlyphHoldClient(
        base_url="https://glyphhold.example",
        api_key="gh_live_test",
        transport=_transport(handler),
    )

    assert await client.reveal_secret(id_or_name="CUSTOM_API_KEY", purpose="test purpose") == {
        "name": "CUSTOM_API_KEY",
        "value": "hidden",
    }


@pytest.mark.asyncio
async def test_memory_management_paths() -> None:
    seen: list[tuple[str, str, dict | list | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, payload))
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"ok": True})

    client = GlyphHoldClient(
        base_url="https://glyphhold.example",
        api_key="gh_live_test",
        transport=_transport(handler),
    )

    await client.get_memory(memory_id="mem_1")
    await client.update_memory(memory_id="mem_1", title="Updated", confidence=4)
    await client.archive_memory(memory_id="mem_1")
    await client.list_memory_revisions(memory_id="mem_1")
    await client.restore_memory_revision(memory_id="mem_1", revision_id="rev_1")
    await client.delete_memory(memory_id="mem_1")

    assert seen == [
        ("GET", "/api/v1/memories/mem_1", None),
        ("PATCH", "/api/v1/memories/mem_1", {"title": "Updated", "confidence": 4}),
        ("POST", "/api/v1/memories/mem_1/archive", {}),
        ("GET", "/api/v1/memories/mem_1/revisions", None),
        ("POST", "/api/v1/memories/mem_1/revisions/rev_1/restore", {}),
        ("DELETE", "/api/v1/memories/mem_1", None),
    ]


@pytest.mark.asyncio
async def test_secret_metadata_management_paths() -> None:
    seen: list[tuple[str, str, dict | list | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, payload))
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"ok": True})

    client = GlyphHoldClient(
        base_url="https://glyphhold.example",
        api_key="gh_live_test",
        transport=_transport(handler),
    )

    await client.get_secret_metadata(id_or_name="CUSTOM_API_KEY")
    await client.update_secret(id_or_name="CUSTOM_API_KEY", description="Updated")
    await client.reveal_secret_env(scope="local", purpose="test env")
    await client.delete_secret(id_or_name="CUSTOM_API_KEY")

    assert seen == [
        ("GET", "/api/v1/secrets/CUSTOM_API_KEY", None),
        ("PATCH", "/api/v1/secrets/CUSTOM_API_KEY", {"description": "Updated"}),
        (
            "POST",
            "/api/v1/secrets/env",
            {"scope": "local", "requesting_agent": "codex", "purpose": "test env"},
        ),
        ("DELETE", "/api/v1/secrets/CUSTOM_API_KEY", None),
    ]


@pytest.mark.asyncio
async def test_error_does_not_include_authorization_value() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer gh_live_do_not_leak"
        return httpx.Response(401, json={"detail": "Invalid API key"})

    client = GlyphHoldClient(
        base_url="https://glyphhold.example",
        api_key="gh_live_do_not_leak",
        transport=_transport(handler),
    )

    with pytest.raises(GlyphHoldError) as exc_info:
        await client.health()

    assert "Invalid API key" in str(exc_info.value)
    assert "gh_live_do_not_leak" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_client_accepts_ssl_verification_override() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok"})

    client = GlyphHoldClient(
        base_url="https://glyphhold.example",
        api_key="gh_live_test",
        verify_ssl=False,
        transport=_transport(handler),
    )

    assert await client.health() == {"status": "ok"}
