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
        assert json.loads(request.content) == {"purpose": "test purpose"}
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

