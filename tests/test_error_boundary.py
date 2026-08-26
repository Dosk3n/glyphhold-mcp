from __future__ import annotations

import json

import pytest
from mcp.types import TextContent

from glyphhold_mcp import server
from glyphhold_mcp.client import GlyphHoldError


def _text_payload(content: list[TextContent]) -> dict:
    assert len(content) == 1
    assert isinstance(content[0], TextContent)
    return json.loads(content[0].text)


@pytest.mark.asyncio
async def test_failed_tool_returns_normal_payload_and_next_tool_works(monkeypatch) -> None:
    class FakeClient:
        async def get_secret_metadata(self, *, id_or_name: str) -> dict:
            raise GlyphHoldError(
                "Glyph Hold request failed: HTTP 404: Secret not found",
                kind="not_found",
                status_code=404,
                retryable=False,
            )

        async def health(self) -> dict:
            return {"status": "ok", "database": "ok"}

    monkeypatch.setattr(server, "_client", FakeClient)

    failed = await server.mcp.call_tool(
        "get_secret_metadata",
        {"id_or_name": "NONEXISTENT_DIAGNOSTIC_SECRET"},
    )
    healthy = await server.mcp.call_tool("glyphhold_health", {})

    assert _text_payload(failed) == {
        "ok": False,
        "error": {
            "type": "not_found",
            "message": "Glyph Hold request failed: HTTP 404: Secret not found",
            "retryable": False,
            "status": 404,
        },
    }
    assert _text_payload(healthy) == {"status": "ok", "database": "ok"}


@pytest.mark.asyncio
async def test_unexpected_error_is_redacted_and_nonfatal(monkeypatch) -> None:
    class BrokenClient:
        async def health(self) -> dict:
            raise ValueError("sensitive implementation detail")

    monkeypatch.setattr(server, "_client", BrokenClient)

    result = await server.mcp.call_tool("glyphhold_health", {})

    assert _text_payload(result) == {
        "ok": False,
        "error": {
            "type": "internal_error",
            "message": "Glyph Hold MCP encountered an unexpected internal error.",
            "retryable": False,
        },
    }
