# Glyph Hold MCP connector

Version 2.1.0 is a local stdio MCP server for Codex and other MCP clients. It uses
Glyph Hold 2's public `/api/v2` HTTP API and never opens the server's SQLite file.
Upgrade this connector alongside the server; version 0.1.0 is for GH1.

## Setup

Use Python 3.12+ and install locally with `pip install -e ".[dev]"`. The FastMCP
SDK dependency is pinned below major version 2 because that major changes the
server API. Configure `.env` or your MCP host environment:

```text
GLYPHHOLD_URL=https://your-glyphhold-host.example.com
GLYPHHOLD_API_KEY=gh_live_xxxxxxxxxxxxxxxxx
```

Existing timeout/TLS options in `.env.example` remain supported. In GH2 create
the API key, assign its explicit space grants and default destination, and grant
only required scopes: `memories:read`, `memories:write`, `secrets:write`, and
`secrets:reveal`. API-level admin scope does not grant all spaces. Run
`glyphhold-mcp` as the stdio command in your host's MCP configuration, with the
checkout's environment and Python executable. No live host configuration is
changed by this source upgrade.

## Contract

- `glyphhold_capabilities` reports permitted spaces and the connection default.
- `prefetch_memories` returns bounded active/General context with IDs, versions,
  ownership, provenance and freshness.
- `search_memories` accepts explicit broader discovery. A result in another space
  does not change the write destination.
- `create_memory` requires a stable idempotency key. Reuse it for retries.
- `update_memory`, `archive_memory`, `move_memory` and `restore_memory_revision`
  require the last-read expected version. Reread after HTTP 409 conflicts.
- `get_memory_context`, `set_memory_context` and `get_placement_guidance` support
  deliberate per-conversation routing and owner-confirmed associations. Supply
  the same unique session ID to context, search/recall and create operations.
- Secret metadata and explicit per-secret reveal remain separate and work with
  built-in or Vaultwarden providers. Secrets are global and independent of memory spaces.
- Destructive delete, bulk environment reveal and lexical conflict claims are
  removed from this GH2 surface.

Tool failures remain structured ordinary payloads so a missing record or conflict
never invalidates the entire connector. Source content and credentials are not
included in error logs. Tool availability alone cannot guarantee pre-response
recall: configure the host workflow or use a native memory-provider integration.

Run `python -m pytest tests`. Tests validate tool schemas, error containment,
transport safety, idempotent/versioned writes and explicit reveal paths. The GH2
checkout also has local cross-repository ASGI conformance tests covering this
client, Hermes and Nexus against the actual backend. Live host setup and network
connectivity still need a deployment rehearsal.

## Live secret providers (2.1)

With Vaultwarden enabled, search and metadata read all accessible vault entries
directly, including pre-existing items. Built-in secrets remain accessible.
Secret `space_id` is accepted for compatibility but no longer scopes access;
API keys still require secret permissions. Memory spaces are unchanged.

`create_secret` uses the active provider and rejects duplicate names. Optional
`folder_id` chooses a vault folder; omission uses the configured default and an
empty string means unfiled. `list_secret_folders` and `create_secret_folder`
manage optional folders. No memory-to-folder mapping or item linking is needed.

`reveal_secret(field=...)` selects a field from metadata (password, username,
SSH keys, notes, card/identity or custom fields). `update_secret` requires the
current metadata version and preserves other fields. External changes cannot
be made atomically against concurrent edits in other Bitwarden clients.

`migrate_secret` transfers a built-in secret without exposing its value to the
agent. Search first: provide an existing `target_id` and field to verify equal
values, or omit target ID to create only when the name is unused. Conflicts
retain both values for user review; never blindly overwrite or export plaintext.
Provider outages fail explicitly rather than look like an empty vault. Upgrade
the server and adapters together to use these operations.
