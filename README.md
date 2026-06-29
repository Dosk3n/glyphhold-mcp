# Glyph Hold MCP

Local stdio MCP server for connecting Codex and other MCP clients to Glyph Hold.

This repo is intentionally separate from Glyph Hold. It does not access the
SQLite database directly. It talks to a running Glyph Hold instance through the
public `/api/v1` HTTP API.

## Requirements

- Python 3.12+
- A running Glyph Hold instance
- A Glyph Hold API key created from the dashboard

Example URL:

```text
GLYPHHOLD_URL=https://glyphhold.example.com
```

## Local Setup

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` and set `GLYPHHOLD_API_KEY` to a key created in Glyph Hold.

Useful scopes:

- `memories:read`
- `memories:write`
- `secrets:write`
- `secrets:reveal`

Only grant `secrets:reveal` if you want the MCP client to be able to reveal
secret values after an explicit user request.

## Codex CLI Config

Add this to `~/.codex/config.toml`:

```toml
[mcp_servers.glyphhold]
command = "/path/to/glyphhold-mcp/.venv/bin/python"
args = ["-m", "glyphhold_mcp.server"]
cwd = "/path/to/glyphhold-mcp"
env_vars = ["GLYPHHOLD_URL", "GLYPHHOLD_API_KEY"]
```

Before starting Codex, export the environment variables:

```bash
export GLYPHHOLD_URL="https://glyphhold.example.com"
export GLYPHHOLD_API_KEY="gh_live_xxxxxxxxxxxxxxxxx"
codex
```

Inside Codex, run:

```text
/mcp
```

You should see the `glyphhold` MCP server connected.

## Tools

- `glyphhold_health`
- `list_categories`
- `search_memories`
- `prefetch_memories`
- `create_memory`
- `create_secret`
- `reveal_secret`

Secret values are only returned by `reveal_secret`.
