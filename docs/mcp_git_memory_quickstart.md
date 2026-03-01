# Git MCP + Memory MCP Quickstart

Date: 2026-03-01

## Installed In Codex

Updated user config file:

`C:\Users\chengliu\.codex\config.toml`

Added:

```toml
[mcp_servers.git]
command = "uvx"
args = ["mcp-server-git", "--repository", "F:/ICMAB-Data/UAB-Thesis/zotero-mcp"]

[mcp_servers.memory]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-memory"]
env = { MEMORY_FILE_PATH = "C:/Users/chengliu/.codex/memory.jsonl" }
```

## How To Use Git MCP

After restarting Codex/session, ask directly in natural language:

- "Show git status of current repo."
- "Show unstaged diff."
- "Show last 5 commits."
- "Create branch `feat/x` from current branch."
- "Commit staged changes with message `fix(cli): ...`."

Typical tools behind the scenes:

- `git_status`
- `git_diff_unstaged`
- `git_diff_staged`
- `git_log`
- `git_add`
- `git_commit`
- `git_create_branch`
- `git_checkout`

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

- Git MCP is scoped to this repository path:
  `F:/ICMAB-Data/UAB-Thesis/zotero-mcp`
- If you want Git MCP to access multiple repositories, add more server entries or remove `--repository` and provide paths per call.
