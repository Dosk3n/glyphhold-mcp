from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from glyphhold_mcp.client import GlyphHoldClient
from glyphhold_mcp.config import load_settings

mcp = FastMCP(
    "Glyph Hold",
    instructions=(
        "Use Glyph Hold for durable user-approved memory and explicit secret retrieval. "
        "Search or prefetch memories before creating new ones to avoid duplicates. "
        "Never reveal secrets unless the user explicitly asks for the secret value."
    ),
)


def _client() -> GlyphHoldClient:
    settings = load_settings()
    return GlyphHoldClient(
        base_url=settings.glyphhold_url,
        api_key=settings.api_key,
        timeout_seconds=settings.timeout_seconds,
    )


@mcp.tool()
async def glyphhold_health() -> dict[str, Any]:
    """Check the configured Glyph Hold service health and version."""
    return await _client().health()


@mcp.tool()
async def list_categories() -> list[dict[str, Any]]:
    """List available Glyph Hold memory categories."""
    return await _client().list_categories()


@mcp.tool()
async def search_memories(
    query: str,
    category: str | None = None,
    limit: int = 10,
    include_archived: bool = False,
) -> dict[str, Any]:
    """Search Glyph Hold memories with deterministic SQLite FTS."""
    return await _client().search_memories(
        query=query,
        category=category,
        limit=limit,
        include_archived=include_archived,
    )


@mcp.tool()
async def prefetch_memories(
    message: str,
    agent: str | None = "codex",
    max_memories: int = 3,
    max_chars: int = 1200,
    max_tokens: int = 300,
    summaries_only: bool = True,
) -> dict[str, Any]:
    """Ask Glyph Hold for conservative memory context relevant to a message."""
    return await _client().prefetch_memories(
        message=message,
        agent=agent,
        max_memories=max_memories,
        max_chars=max_chars,
        max_tokens=max_tokens,
        summaries_only=summaries_only,
    )


@mcp.tool()
async def create_memory(
    category_id: str,
    title: str,
    body: str,
    summary: str | None = None,
    tags: list[str] | None = None,
    confidence: int = 3,
    auto_prefetch_level: str = "normal",
) -> dict[str, Any]:
    """Create a Glyph Hold memory after confirming it should be stored durably."""
    return await _client().create_memory(
        category_id=category_id,
        title=title,
        body=body,
        summary=summary,
        tags=tags,
        confidence=confidence,
        auto_prefetch_level=auto_prefetch_level,
    )


@mcp.tool()
async def create_secret(
    name: str,
    value: str,
    description: str | None = None,
    value_type: str = "text",
    service: str | None = None,
    host: str | None = None,
    scope: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Create encrypted Glyph Hold secret metadata and value."""
    return await _client().create_secret(
        name=name,
        value=value,
        description=description,
        value_type=value_type,
        service=service,
        host=host,
        scope=scope,
        tags=tags,
    )


@mcp.tool()
async def reveal_secret(id_or_name: str, purpose: str = "MCP reveal requested by Codex") -> dict[str, Any]:
    """Reveal a secret value only when the user explicitly asks for the value."""
    return await _client().reveal_secret(id_or_name=id_or_name, purpose=purpose)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

