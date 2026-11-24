---
description: Check and fix everything Liminal needs on this machine and in this project
allowed-tools: Bash, Read, Glob
---

Run the Liminal environment doctor and act on its report.

1. Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py" --json` from the project root. If
   `python` is not found, try `python3`, then `py -3`. If none exist, Python is the first thing
   to install (python.org, 3.10 or newer); stop and tell the user.
2. Read the JSON. Each check has `status` (`ok`, `warn`, `fail`), a `detail` and a `fix`.
3. For every `fail` and `warn`, do the fix yourself when it is a local, reversible command
   (installing `liminal-mcp` with pip, creating a `liminal.config.ts`, running
   `npx liminal sync`). Ask before anything that costs money or changes the user's Blender
   preferences. Blender add-on installation is done by the user in Blender's UI; give them the
   exact clicks the fix text contains.
4. Re-run the doctor after fixing. Stop when everything is `ok` or only `warn`s remain that
   the user has chosen to leave.
5. Finish with a short status table and the single next step. If the project has no entity
   registry yet, the next step is the `liminal-entities` skill. If it has one and Blender is
   connected, the next step is the `liminal-levels` skill.

Things the doctor cannot see: whether the user has bought the editor. If Blender is running
but the `editor_loaded` check fails, say plainly that the Liminal Editor add-on comes from
https://liminal.lv and must be installed and enabled before any of this works.
