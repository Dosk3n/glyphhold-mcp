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
async def test_v2_tools_require_versions_and_idempotency() -> None:
    create = await _tool_schema("create_memory")
    update = await _tool_schema("update_memory")
    restore = await _tool_schema("restore_memory_revision")
    assert "idempotency_key" in create["required"]
    assert "expected_version" in update["required"]
    assert "expected_version" in restore["required"]
    tools = {tool.name for tool in await mcp.list_tools()}
    assert {
        "glyphhold_capabilities",
        "move_memory",
        "get_memory_context",
        "set_memory_context",
        "get_placement_guidance",
    }.issubset(tools)
    assert "reveal_secret_env" not in tools
    assert "delete_memory" not in tools
