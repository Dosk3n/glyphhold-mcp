from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from glyphhold_mcp.client import GlyphHoldClient, GlyphHoldError
from glyphhold_mcp.config import load_settings

MemoryConfidence = Annotated[int, Field(ge=1, le=5, description="Confidence score from 1 to 5.")]
MemoryLimit = Annotated[int, Field(ge=1, le=100, description="Maximum number of memories.")]
MemoryListLimit = Annotated[int, Field(ge=1, le=500, description="Maximum number of memories.")]
MemoryOffset = Annotated[int, Field(ge=0, description="Pagination offset.")]
SimilarMemoryLimit = Annotated[int, Field(ge=1, le=20, description="Maximum similar memories.")]
PrefetchMemoryLimit = Annotated[int, Field(ge=1, le=10, description="Maximum memories to prefetch.")]
PrefetchChars = Annotated[int, Field(ge=100, le=8000, description="Maximum character budget.")]
PrefetchTokens = Annotated[int, Field(ge=25, le=2000, description="Maximum token estimate.")]
PrefetchLevel = Literal["never", "low", "normal", "high", "pinned"]
SecretLimit = Annotated[int, Field(ge=1, le=500, description="Maximum number of secret metadata records.")]
SecretOffset = Annotated[int, Field(ge=0, description="Pagination offset.")]
SecretValueType = Literal["text", "api_key", "password", "token", "webhook_url", "username", "json"]

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
        verify_ssl=settings.verify_ssl,
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
async def list_memories(
    category: str | None = None,
    tag: str | None = None,
    include_archived: bool = False,
    limit: MemoryListLimit = 100,
    offset: MemoryOffset = 0,
) -> list[dict[str, Any]]:
    """List Glyph Hold memories, optionally filtered by category, tag, and archive state."""
    return await _client().list_memories(
        category=category,
        tag=tag,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )


@mcp.tool()
async def get_memory(memory_id: str) -> dict[str, Any]:
    """Get one Glyph Hold memory by id."""
    return await _client().get_memory(memory_id=memory_id)


@mcp.tool()
async def search_memories(
    query: str,
    category: str | None = None,
    limit: MemoryLimit = 10,
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
    max_memories: PrefetchMemoryLimit = 3,
    max_chars: PrefetchChars = 1200,
    max_tokens: PrefetchTokens = 300,
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
async def find_similar_memories(
    title: str,
    body: str,
    category: str | None = None,
    tags: list[str] | None = None,
    limit: SimilarMemoryLimit = 5,
) -> dict[str, Any]:
    """Find existing memories that may duplicate or overlap proposed memory content."""
    return await _client().find_similar_memories(
        title=title,
        body=body,
        category=category,
        tags=tags,
        limit=limit,
    )


@mcp.tool()
async def prepare_memory_write(
    title: str,
    body: str,
    category: str | None = None,
    tags: list[str] | None = None,
    limit: SimilarMemoryLimit = 5,
) -> dict[str, Any]:
    """Check likely duplicates and conflicts before creating a durable memory."""
    return await _client().prepare_memory_write(
        title=title,
        body=body,
        category=category,
        tags=tags,
        limit=limit,
    )


@mcp.tool()
async def create_memory(
    category_id: str,
    title: str,
    body: str,
    summary: str | None = None,
    tags: list[str] | None = None,
    confidence: MemoryConfidence = 3,
    auto_prefetch_level: PrefetchLevel = "normal",
) -> dict[str, Any]:
    """Create a Glyph Hold memory after confirming it should be stored durably.

    confidence must be 1-5. auto_prefetch_level must be one of never, low,
    normal, high, or pinned.
    """
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
async def update_memory(
    memory_id: str,
    category_id: str | None = None,
    title: str | None = None,
    summary: str | None = None,
    body: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    source: str | None = None,
    confidence: MemoryConfidence | None = None,
    auto_prefetch_level: PrefetchLevel | None = None,
    archived: bool | None = None,
    superseded_by: str | None = None,
    change_reason: str | None = None,
) -> dict[str, Any]:
    """Update an existing memory only when the user intends to change stored long-term context."""
    return await _client().update_memory(
        memory_id=memory_id,
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
    )


@mcp.tool()
async def update_memory_confidence(
    memory_id: str,
    confidence: MemoryConfidence,
    change_reason: str | None = None,
) -> dict[str, Any]:
    """Update a memory confidence score from 1 to 5."""
    return await _client().update_memory_confidence(
        memory_id=memory_id,
        confidence=confidence,
        change_reason=change_reason,
    )


@mcp.tool()
async def archive_memory(memory_id: str) -> dict[str, Any]:
    """Archive a memory so normal searches and prefetches exclude it."""
    return await _client().archive_memory(memory_id=memory_id)


@mcp.tool()
async def supersede_memory(memory_id: str, superseded_by: str) -> dict[str, Any]:
    """Mark one memory as superseded by another memory id."""
    return await _client().supersede_memory(memory_id=memory_id, superseded_by=superseded_by)


@mcp.tool()
async def list_memory_revisions(memory_id: str) -> list[dict[str, Any]]:
    """List revision history for one memory."""
    return await _client().list_memory_revisions(memory_id=memory_id)


@mcp.tool()
async def restore_memory_revision(
    memory_id: str,
    revision_id: str,
    change_reason: str | None = None,
) -> dict[str, Any]:
    """Restore a memory from a previous revision."""
    return await _client().restore_memory_revision(
        memory_id=memory_id,
        revision_id=revision_id,
        change_reason=change_reason,
    )


@mcp.tool()
async def delete_memory(memory_id: str, confirm_title: str) -> dict[str, str]:
    """Permanently delete a memory after confirm_title exactly matches the current title."""
    client = _client()
    memory = await client.get_memory(memory_id=memory_id)
    if memory["title"] != confirm_title:
        raise GlyphHoldError("Memory title confirmation did not match; delete was not performed.")
    await client.delete_memory(memory_id=memory_id)
    return {"deleted": memory_id}


@mcp.tool()
async def search_secrets(
    query: str | None = None,
    service: str | None = None,
    host: str | None = None,
    scope: str | None = None,
    limit: SecretLimit = 100,
    offset: SecretOffset = 0,
) -> list[dict[str, Any]]:
    """Search/list secret metadata only. Secret values are not returned by this tool."""
    return await _client().list_secrets(
        query=query,
        service=service,
        host=host,
        scope=scope,
        limit=limit,
        offset=offset,
    )


@mcp.tool()
async def get_secret_metadata(id_or_name: str) -> dict[str, Any]:
    """Get secret metadata only by id or name. The secret value is not returned."""
    return await _client().get_secret_metadata(id_or_name=id_or_name)


@mcp.tool()
async def create_secret(
    name: str,
    value: str,
    description: str | None = None,
    value_type: SecretValueType = "text",
    service: str | None = None,
    host: str | None = None,
    scope: str | None = None,
    tags: list[str] | None = None,
    allowed_agents: list[str] | None = None,
    allowed_tools: list[str] | None = None,
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
        allowed_agents=allowed_agents,
        allowed_tools=allowed_tools,
    )


@mcp.tool()
async def update_secret(
    id_or_name: str,
    name: str | None = None,
    value: str | None = None,
    description: str | None = None,
    value_type: SecretValueType | None = None,
    service: str | None = None,
    host: str | None = None,
    scope: str | None = None,
    tags: list[str] | None = None,
    allowed_agents: list[str] | None = None,
    allowed_tools: list[str] | None = None,
) -> dict[str, Any]:
    """Update secret metadata, access restrictions, or value only when the user intends it."""
    return await _client().update_secret(
        id_or_name=id_or_name,
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
    )


@mcp.tool()
async def delete_secret(id_or_name: str, confirm_name: str) -> dict[str, str]:
    """Permanently delete a secret after confirm_name exactly matches the current secret name."""
    client = _client()
    secret = await client.get_secret_metadata(id_or_name=id_or_name)
    if secret["name"] != confirm_name:
        raise GlyphHoldError("Secret name confirmation did not match; delete was not performed.")
    await client.delete_secret(id_or_name=id_or_name)
    return {"deleted": secret["name"]}


@mcp.tool()
async def reveal_secret(
    id_or_name: str,
    requesting_agent: str | None = "codex",
    tool: str | None = None,
    purpose: str = "MCP reveal requested by Codex",
) -> dict[str, Any]:
    """Reveal a secret value only when the user explicitly asks for the value."""
    return await _client().reveal_secret(
        id_or_name=id_or_name,
        requesting_agent=requesting_agent,
        tool=tool,
        purpose=purpose,
    )


@mcp.tool()
async def reveal_secret_env(
    scope: str | None = None,
    requesting_agent: str | None = "codex",
    purpose: str = "MCP env reveal requested by Codex",
) -> dict[str, Any]:
    """Reveal multiple secret values as env-style values only when the user explicitly asks."""
    return await _client().reveal_secret_env(
        scope=scope,
        requesting_agent=requesting_agent,
        purpose=purpose,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
