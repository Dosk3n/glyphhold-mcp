from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Annotated, Any, Literal, cast, get_type_hints

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from glyphhold_mcp.client import GlyphHoldClient, GlyphHoldError
from glyphhold_mcp.config import load_settings

MemoryConfidence = Annotated[int, Field(ge=1, le=5, description="Confidence score from 1 to 5.")]
MemoryLimit = Annotated[int, Field(ge=1, le=100, description="Maximum number of memories.")]
MemoryListLimit = Annotated[int, Field(ge=1, le=500, description="Maximum number of memories.")]
MemoryOffset = Annotated[int, Field(ge=0, description="Pagination offset.")]
SimilarMemoryLimit = Annotated[int, Field(ge=1, le=20, description="Maximum similar memories.")]
PrefetchMemoryLimit = Annotated[
    int, Field(ge=1, le=10, description="Maximum memories to prefetch.")
]
PrefetchChars = Annotated[int, Field(ge=256, le=8000, description="Maximum character budget.")]
PrefetchTokens = Annotated[int, Field(ge=25, le=2000, description="Maximum token estimate.")]
PrefetchLevel = Literal["never", "low", "normal", "high", "pinned"]
SecretLimit = Annotated[
    int, Field(ge=1, le=500, description="Maximum number of secret metadata records.")
]
SecretOffset = Annotated[int, Field(ge=0, description="Pagination offset.")]
SecretValueType = Literal["text", "api_key", "password", "token", "webhook_url", "username", "json"]
logger = logging.getLogger(__name__)

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


def stable_tool[**P, R](
    function: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[Any]]:
    """Keep recoverable tool failures inside normal MCP result payloads.

    Some MCP clients invalidate a connector after receiving a protocol-level
    tool error. Returning a structured result keeps the connector usable while
    still giving the agent an explicit, actionable failure.
    """

    @wraps(function)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> Any:
        try:
            return await function(*args, **kwargs)
        except GlyphHoldError as exc:
            logger.warning(
                "Glyph Hold tool %s failed: type=%s status=%s retryable=%s",
                function.__name__,
                exc.kind,
                exc.status_code,
                exc.retryable,
            )
            return {"ok": False, "error": exc.as_tool_error()}
        except RuntimeError:
            logger.exception("Glyph Hold tool %s has an invalid configuration", function.__name__)
            return {
                "ok": False,
                "error": {
                    "type": "configuration_error",
                    "message": "Glyph Hold MCP configuration is invalid.",
                    "retryable": False,
                },
            }
        except Exception:
            logger.exception("Unexpected failure in Glyph Hold tool %s", function.__name__)
            return {
                "ok": False,
                "error": {
                    "type": "internal_error",
                    "message": "Glyph Hold MCP encountered an unexpected internal error.",
                    "retryable": False,
                },
            }

    # FastMCP inspects this signature for both input and output schemas. Resolve
    # postponed annotations, keep the input contract, and allow the structured
    # error envelope as an alternative output.
    signature = inspect.signature(function)
    type_hints = get_type_hints(function, include_extras=True)
    parameters = [
        parameter.replace(annotation=type_hints.get(name, parameter.annotation))
        for name, parameter in signature.parameters.items()
    ]
    wrapped.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=parameters,
        return_annotation=Any,
    )
    return cast(Callable[P, Awaitable[Any]], wrapped)


@mcp.tool()
@stable_tool
async def glyphhold_health() -> dict[str, Any]:
    """Check service health."""
    return await _client().health()


@mcp.tool()
@stable_tool
async def glyphhold_capabilities() -> dict[str, Any]:
    """Discover permitted spaces, defaults and GH2 features."""
    return await _client().capabilities()


@mcp.tool()
@stable_tool
async def list_categories() -> list[dict[str, Any]]:
    """List categories; these classify records and do not grant access."""
    return await _client().list_categories()


@mcp.tool()
@stable_tool
async def list_memories(
    space_id: str | None = None,
    include_archived: bool = False,
    limit: MemoryListLimit = 100,
    offset: MemoryOffset = 0,
) -> dict[str, Any]:
    """List permitted records with versions and ownership."""
    return await _client().list_memories(
        space_id=space_id, include_archived=include_archived, limit=limit, offset=offset
    )


@mcp.tool()
@stable_tool
async def get_memory(memory_id: str) -> dict[str, Any]:
    """Read a record and its current version."""
    return await _client().get_memory(memory_id=memory_id)


@mcp.tool()
@stable_tool
async def search_memories(
    query: str,
    space_id: str | None = None,
    session_id: str | None = None,
    broaden: bool = False,
    limit: MemoryLimit = 10,
    max_chars: int = 12000,
) -> dict[str, Any]:
    """Search active space; explicitly broaden across permitted spaces as needed."""
    return await _client().search_memories(
        query=query,
        space_id=space_id,
        session_id=session_id,
        broaden=broaden,
        limit=limit,
        max_chars=max_chars,
    )


@mcp.tool()
@stable_tool
async def prefetch_memories(
    message: str,
    space_id: str | None = None,
    session_id: str | None = None,
    max_memories: PrefetchMemoryLimit = 5,
    max_chars: PrefetchChars = 2400,
) -> dict[str, Any]:
    """Recall bounded, traceable active and permitted General context."""
    return await _client().prefetch_memories(
        message=message,
        space_id=space_id,
        session_id=session_id,
        max_memories=max_memories,
        max_chars=max_chars,
    )


@mcp.tool()
@stable_tool
async def create_memory(
    title: str,
    body: str,
    idempotency_key: str,
    space_id: str | None = None,
    session_id: str | None = None,
    category_id: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    source: str | None = None,
    confidence: MemoryConfidence = 3,
    auto_prefetch_level: PrefetchLevel = "normal",
) -> dict[str, Any]:
    """Save a durable memory after search. Reuse the idempotency key for retries."""
    return await _client().create_memory(
        title=title,
        body=body,
        idempotency_key=idempotency_key,
        space_id=space_id,
        session_id=session_id,
        category_id=category_id,
        summary=summary,
        tags=tags or [],
        metadata=metadata or {},
        source=source,
        confidence=confidence,
        auto_prefetch_level=auto_prefetch_level,
    )


@mcp.tool()
@stable_tool
async def update_memory(
    memory_id: str,
    expected_version: int,
    title: str | None = None,
    body: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    last_verified_at: str | None = None,
    change_reason: str | None = None,
) -> dict[str, Any]:
    """Update using the last-read version; reread and reconcile after conflicts."""
    return await _client().update_memory(
        memory_id=memory_id,
        expected_version=expected_version,
        title=title,
        body=body,
        summary=summary,
        tags=tags,
        metadata=metadata,
        last_verified_at=last_verified_at,
        change_reason=change_reason,
    )


@mcp.tool()
@stable_tool
async def archive_memory(memory_id: str, expected_version: int) -> dict[str, Any]:
    """Archive a memory reversibly with concurrency protection."""
    return await _client().archive_memory(memory_id=memory_id, expected_version=expected_version)


@mcp.tool()
@stable_tool
async def move_memory(memory_id: str, space_id: str, expected_version: int) -> dict[str, Any]:
    """Explicitly move ownership; requires write grants in both spaces."""
    return await _client().move_memory(
        memory_id=memory_id, space_id=space_id, expected_version=expected_version
    )


@mcp.tool()
@stable_tool
async def list_memory_revisions(memory_id: str) -> dict[str, Any]:
    """Inspect permitted historical snapshots."""
    return await _client().list_memory_revisions(memory_id=memory_id)


@mcp.tool()
@stable_tool
async def restore_memory_revision(
    memory_id: str, revision_id: str, expected_version: int
) -> dict[str, Any]:
    """Restore a permitted revision while checking concurrent edits."""
    return await _client().restore_memory_revision(
        memory_id=memory_id, revision_id=revision_id, expected_version=expected_version
    )


@mcp.tool()
@stable_tool
async def get_memory_context(session_id: str) -> dict[str, Any]:
    """Read active context and confirmed placement guidance for one conversation."""
    return await _client().get_context(session_id=session_id)


@mcp.tool()
@stable_tool
async def set_memory_context(session_id: str, space_id: str) -> dict[str, Any]:
    """Change one conversation's active space without changing connection default."""
    return await _client().set_context(session_id=session_id, space_id=space_id)


@mcp.tool()
@stable_tool
async def get_placement_guidance(space_id: str | None = None) -> dict[str, Any]:
    """Read owner-confirmed guidance for placing new memories."""
    return await _client().placement_guidance(space_id=space_id)


@mcp.tool()
@stable_tool
async def search_secrets(
    query: str = "", space_id: str | None = None, provider_name: str | None = None
) -> dict[str, Any]:
    """Search global secret metadata in the active vault plus built-in storage. provider_name=builtin allows local-only access during a vault outage. No values are returned."""
    return await _client().search_secrets(
        query=query, space_id=space_id, provider_name=provider_name
    )


@mcp.tool()
@stable_tool
async def get_secret_metadata(id_or_name: str, space_id: str | None = None) -> dict[str, Any]:
    """Inspect one secret without revealing its value."""
    fields = {"id_or_name": id_or_name}
    if space_id:
        fields["space_id"] = space_id
    return await _client().get_secret_metadata(**fields)


@mcp.tool()
@stable_tool
async def create_secret(
    name: str,
    value: str,
    space_id: str | None = None,
    description: str | None = None,
    value_type: SecretValueType = "text",
    folder_id: str | None = None,
    username: str | None = None,
    uri: str | None = None,
) -> dict[str, Any]:
    """Create in the active provider after searching for duplicates. Secrets are global. Optional folder_id selects a vault folder; empty string means unfiled, omission uses the default. space_id is deprecated."""
    return await _client().create_secret(
        name=name,
        value=value,
        space_id=space_id,
        description=description,
        value_type=value_type,
        folder_id=folder_id,
        username=username,
        uri=uri,
    )


@mcp.tool()
@stable_tool
async def reveal_secret(
    id_or_name: str, space_id: str | None = None, field: str | None = None
) -> dict[str, Any]:
    """Explicitly reveal one field for an authorised task. Use metadata fields to select username, password, SSH key, notes or custom fields."""
    return await _client().reveal_secret(id_or_name=id_or_name, space_id=space_id, field=field)


@mcp.tool()
@stable_tool
async def list_secret_folders() -> dict[str, Any]:
    """List optional vault folders. Built-in storage returns supported=false."""
    return await _client().list_secret_folders()


@mcp.tool()
@stable_tool
async def create_secret_folder(name: str) -> dict[str, Any]:
    """Create a vault folder after checking existing folders. Requires external writes."""
    return await _client().create_secret_folder(name=name)


@mcp.tool()
@stable_tool
async def update_secret(
    id_or_name: str, expected_version: int | str, value: str, field: str | None = None
) -> dict[str, Any]:
    """Update one explicitly selected secret field using its current metadata version. Never overwrite a conflicting value without authorisation."""
    return await _client().update_secret(
        id_or_name=id_or_name, expected_version=expected_version, value=value, field=field
    )


@mcp.tool()
@stable_tool
async def migrate_secret(
    id_or_name: str,
    expected_version: int,
    target_id: str | None = None,
    field: str | None = None,
    folder_id: str | None = None,
) -> dict[str, Any]:
    """Transfer a built-in secret directly to the vault without exposing its value. Search first: pass an existing target_id and field to verify identical values, or omit target_id to create only if the name is unused. Different values require user review; neither is overwritten."""
    return await _client().migrate_secret(
        id_or_name=id_or_name,
        expected_version=expected_version,
        target_id=target_id,
        field=field,
        folder_id=folder_id,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
