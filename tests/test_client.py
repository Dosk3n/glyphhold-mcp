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
        assert request.url.path == "/api/v2/search"
        assert request.headers["authorization"] == "Bearer gh_live_test"
        assert json.loads(request.content) == {
            "query": "glyph hold",
            "limit": 5,
            "broaden": False,
            "max_chars": 12000,
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
        assert request.url.path == "/api/v2/secrets/CUSTOM_API_KEY/reveal"
        assert json.loads(request.content) == {}
        return httpx.Response(200, json={"name": "CUSTOM_API_KEY", "value": "hidden"})

    client = GlyphHoldClient(
        base_url="https://glyphhold.example",
        api_key="gh_live_test",
        transport=_transport(handler),
    )

    assert await client.reveal_secret(id_or_name="CUSTOM_API_KEY") == {
        "name": "CUSTOM_API_KEY",
        "value": "hidden",
    }


@pytest.mark.asyncio
async def test_memory_management_paths() -> None:
    seen = []

    def handler(request):
        seen.append(
            (
                request.method,
                request.url.path,
                json.loads(request.content) if request.content else None,
            )
        )
        return httpx.Response(200, json={"ok": True})

    client = GlyphHoldClient(
        base_url="https://glyphhold.example", api_key="key", transport=_transport(handler)
    )
    await client.create_memory(
        title="Server", body="SSH", idempotency_key="one", space_id="space_work"
    )
    await client.update_memory(memory_id="mem_1", expected_version=1, body="updated")
    await client.move_memory(memory_id="mem_1", space_id="space_personal", expected_version=2)
    await client.restore_memory_revision(memory_id="mem_1", revision_id="rev_1", expected_version=3)
    assert seen[0][1] == "/api/v2/memories" and seen[0][2]["idempotency_key"] == "one"
    assert seen[1] == (
        "PATCH",
        "/api/v2/memories/mem_1",
        {"expected_version": 1, "body": "updated"},
    )
    assert seen[2][1] == "/api/v2/memories/mem_1/move"
    assert seen[3][2] == {"revision_id": "rev_1", "expected_version": 3}


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
    assert exc_info.value.kind == "authentication_error"
    assert exc_info.value.status_code == 401
    assert exc_info.value.retryable is False
    assert exc_info.value.as_tool_error() == {
        "type": "authentication_error",
        "message": "Glyph Hold request failed: HTTP 401: Invalid API key",
        "retryable": False,
        "status": 401,
    }


@pytest.mark.asyncio
async def test_timeout_is_safe_and_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = GlyphHoldClient(
        base_url="https://glyphhold.example",
        api_key="gh_live_do_not_leak",
        transport=_transport(handler),
    )

    with pytest.raises(GlyphHoldError) as exc_info:
        await client.health()

    assert exc_info.value.kind == "timeout"
    assert exc_info.value.retryable is True
    assert "gh_live_do_not_leak" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_connection_failure_is_safe_and_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    client = GlyphHoldClient(
        base_url="https://glyphhold.example",
        api_key="gh_live_do_not_leak",
        transport=_transport(handler),
    )

    with pytest.raises(GlyphHoldError) as exc_info:
        await client.health()

    assert exc_info.value.kind == "connection_error"
    assert exc_info.value.retryable is True
    assert "gh_live_do_not_leak" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_invalid_success_response_is_structured() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    client = GlyphHoldClient(
        base_url="https://glyphhold.example",
        api_key="gh_live_test",
        transport=_transport(handler),
    )

    with pytest.raises(GlyphHoldError) as exc_info:
        await client.health()

    assert exc_info.value.kind == "invalid_response"
    assert exc_info.value.status_code == 200


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


@pytest.mark.asyncio
async def test_global_secret_provider_fields_folders_and_transfer():
    calls = []

    def handle(request):
        calls.append(
            (
                request.method,
                request.url.path,
                json.loads(request.content) if request.content else None,
            )
        )
        return httpx.Response(200, json={"ok": True})

    client = GlyphHoldClient(
        base_url="http://gh", api_key="test", transport=httpx.MockTransport(handle)
    )
    await client.create_secret(name="Token", value="test", folder_id="home")
    await client.list_secret_folders()
    await client.reveal_secret(id_or_name="vw:account:item", field="login.username")
    await client.update_secret(
        id_or_name="vw:account:item",
        expected_version="revision",
        value="new-test",
        field="login.password",
    )
    await client.migrate_secret(
        id_or_name="sec_old",
        expected_version=1,
        target_id="vw:account:item",
        field="login.password",
    )
    assert calls[0][2]["folder_id"] == "home" and "space_id" not in calls[0][2]
    assert calls[1][1] == "/api/v2/secrets/folders"
    assert calls[2][2] == {"field": "login.username"}
    assert calls[3][2]["expected_version"] == "revision"
    assert calls[4][1] == "/api/v2/secrets/sec_old/migrate"


@pytest.mark.asyncio
async def test_preview_payload_and_uncertain_write_not_marked_retryable():
    calls = []

    def handle(request):
        calls.append(json.loads(request.content))
        return httpx.Response(
            503,
            headers={"X-GlyphHold-Error": "vault_create_failed"},
            json={"detail": "private-secret-value"},
        )

    client = GlyphHoldClient(
        base_url="http://gh", api_key="test", transport=httpx.MockTransport(handle)
    )
    with pytest.raises(GlyphHoldError) as exc:
        await client.migrate_secret(id_or_name="sec_test", expected_version=1, dry_run=True)
    assert calls[0]["dry_run"] is True
    assert not exc.value.retryable and "private-secret-value" not in str(exc.value)
    assert "Check the destination" in str(exc.value)
