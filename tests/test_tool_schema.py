from __future__ import annotations

from typing import Any

import pytest

from glyphhold_mcp.server import mcp


async def _tool_schema(name: str) -> dict[str, Any]:
    tools = await mcp.list_tools()
    for tool in tools:
        if tool.name == name:
            return tool.inputSchema
    raise AssertionError(f"Tool not found: {name}")


@pytest.mark.asyncio
async def test_create_memory_schema_has_service_constraints() -> None:
    schema = await _tool_schema("create_memory")
    properties = schema["properties"]

    assert properties["confidence"]["minimum"] == 1
    assert properties["confidence"]["maximum"] == 5
    assert properties["auto_prefetch_level"]["enum"] == [
        "never",
        "low",
        "normal",
        "high",
        "pinned",
    ]


@pytest.mark.asyncio
async def test_create_secret_schema_has_value_type_enum() -> None:
    schema = await _tool_schema("create_secret")

    assert schema["properties"]["value_type"]["enum"] == [
        "text",
        "api_key",
        "password",
        "token",
        "webhook_url",
        "username",
        "json",
    ]


@pytest.mark.asyncio
async def test_memory_management_tools_are_registered() -> None:
    tools = {tool.name for tool in await mcp.list_tools()}

    assert {
        "list_memories",
        "get_memory",
        "find_similar_memories",
        "prepare_memory_write",
        "update_memory",
        "update_memory_confidence",
        "archive_memory",
        "supersede_memory",
        "list_memory_revisions",
        "restore_memory_revision",
        "delete_memory",
    }.issubset(tools)


@pytest.mark.asyncio
async def test_secret_management_tools_are_registered() -> None:
    tools = {tool.name for tool in await mcp.list_tools()}

    assert {
        "search_secrets",
        "get_secret_metadata",
        "update_secret",
        "delete_secret",
        "reveal_secret_env",
    }.issubset(tools)


@pytest.mark.asyncio
async def test_delete_tools_require_confirmations() -> None:
    memory_schema = await _tool_schema("delete_memory")
    secret_schema = await _tool_schema("delete_secret")

    assert "confirm_title" in memory_schema["required"]
    assert "confirm_name" in secret_schema["required"]
