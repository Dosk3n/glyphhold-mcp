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

Choose a place on your machine where you keep local tool repos. Clone this repo
there:

```bash
cd ~/coding_projects
git clone git@github.com:Dosk3n/glyphhold-mcp.git
cd glyphhold-mcp
```

Create the local Python environment:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Create the local environment file:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
nano .env
```

Set:

```text
GLYPHHOLD_URL=https://your-glyphhold-host.example.com
GLYPHHOLD_API_KEY=gh_live_xxxxxxxxxxxxxxxxx
```

Create `GLYPHHOLD_API_KEY` from the Glyph Hold dashboard.

Useful scopes:

- `memories:read`
- `memories:write`
- `secrets:write`
- `secrets:reveal`

Only grant `secrets:reveal` if you want the MCP client to be able to reveal
secret values after an explicit user request.

## Codex CLI Config

Find the full path to the cloned repo:

```bash
pwd
```

If `pwd` prints:

```text
/home/you/coding_projects/glyphhold-mcp
```

then add this to `~/.codex/config.toml`:

```toml
[mcp_servers.glyphhold]
command = "/home/you/coding_projects/glyphhold-mcp/.venv/bin/python"
args = ["-m", "glyphhold_mcp.server"]
cwd = "/home/you/coding_projects/glyphhold-mcp"
```

Use your real path from `pwd`. The important parts are:

```text
command = <repo path>/.venv/bin/python
cwd     = <repo path>
```

You do not need to put the API key in Codex config. The MCP server loads
`GLYPHHOLD_URL` and `GLYPHHOLD_API_KEY` from the `.env` file in the cloned repo.

Start Codex from any project as normal.

Inside Codex, run:

```text
/mcp
```

You should see the `glyphhold` MCP server connected.

## Updating

To update the local MCP server later:

```bash
cd ~/coding_projects/glyphhold-mcp
git pull
. .venv/bin/activate
pip install -e ".[dev]"
```

## Tools

- `glyphhold_health`
- `list_categories`
- `search_memories`
- `prefetch_memories`
- `create_memory`
- `create_secret`
- `reveal_secret`

Secret values are only returned by `reveal_secret`.
