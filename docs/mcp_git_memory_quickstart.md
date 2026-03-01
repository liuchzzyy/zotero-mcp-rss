# Memory MCP Quickstart

Date: 2026-03-01

## Installed In Codex

Updated user config file:

`C:\Users\chengliu\.codex\config.toml`

Current:

```toml
[mcp_servers.memory]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-memory"]
env = { MEMORY_FILE_PATH = "C:/Users/chengliu/.codex/memory.jsonl" }
```

## How To Use Memory MCP

After restarting Codex/session, ask directly:

- "Remember: my default language is Chinese."
- "What do you remember about my preferences?"
- "Forget that I prefer morning meetings."

Typical tools behind the scenes:

- `create_entities`
- `add_observations`
- `search_nodes`
- `read_graph`
- `delete_observations`

Memory file location:

`C:\Users\chengliu\.codex\memory.jsonl`

## Notes

- Git MCP has been removed from local Codex config.
