# liminal-mcp

A stdio [MCP](https://modelcontextprotocol.io) server that lets an AI coding agent place
entities, wire signals, lint and export levels in a running Blender through the
**Liminal Bridge** add-on. It is the tool half of the Liminal Claude plugin; the plugin's
README explains the whole setup.

```bash
pip install liminal-mcp
liminal-mcp            # started by your agent, from the game project directory
```

## How it finds Blender

Each Blender with the bridge enabled listens on a random localhost port and writes a
session file to `~/.liminal/sessions/<pid>.json` (override the directory with
`LIMINAL_SESSIONS_DIR`). The server reads those files, drops the ones whose port no longer
answers, and picks the Blender whose configured workspace folder lies inside the project it
was started in (`--project`, default: the current directory). With one Blender running that
is always the right one. With several and no match, `lm_sessions` lists them and
`lm_use_session` pins one.

## Tool sets

The default tool set only reaches the bridge's named operations, which are schema-driven
and validate every prop against the entity definition. `liminal-mcp --dev` adds
`blender_exec`, `blender_eval`, `blender_get_log`, raw object access and an operator
search; the bridge refuses those unless its own **Developer Mode** preference is on.

## Result envelope

Every tool returns a JSON string:

```json
{"ok": true,  "value": ..., "error": null}
{"ok": false, "value": null, "error": {"message": "...", "traceback": "..."}}
```
