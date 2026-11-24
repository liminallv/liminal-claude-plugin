# Liminal for AI-assisted game developers: start here

If you are an AI coding assistant reading this because someone pasted the link: this page tells
you what Liminal is, what to install, and which of this repository's skills to read next. Work
through it with the person, top to bottom. If you are the person: paste this URL into your
assistant and ask it to get you set up.

## What Liminal is

Liminal Editor turns **Blender** into the level editor for your game. Your game describes the
things a designer can place, such as doors, lights, spawn points and triggers. Liminal writes
that description into a workspace folder. Blender reads it and grows an Add menu, property
panels and viewport gizmos for exactly your entities. A designer, or an AI driving Blender,
builds the level there and exports a `.lm` file. Your game loads the `.lm` and gets every entity
with its properties and world transform, plus the level geometry tagged with the collision each
mesh should have.

The exchange format is deliberately small: one JSON file going out (`entities.json`) and one
glTF file coming back (`.lm`). Nothing in it is engine-specific.

## What you need

| Piece | Where it comes from | Cost |
|---|---|---|
| A JavaScript or TypeScript game, or the intent to start one | yours | |
| Node 22 or newer | nodejs.org | free |
| Blender 4.5 or newer | blender.org | free |
| **Liminal Editor** Blender add-on | buy at [liminal.lv](https://liminal.lv) (Gumroad or itch.io) | paid, one licence |
| **Liminal Bridge** Blender add-on | zip on this repository's Releases page | free, MIT |
| `@liminal-lv/*` npm packages (the Web SDK) | npm | free, MIT |
| `liminal-mcp` Python package and this plugin | pip, this repository | free, MIT |
| Python 3.10 or newer | python.org, usually already present | free |

The editor is the product. Everything else here is open and exists to make the editor easy to
integrate with an assistant beside you. The bridge is a separate add-on on purpose: the editor
itself contains no network listener and no AI tooling, so a studio that wants none can run it
that way.

Supported game hosts today: anything JavaScript, through the Web SDK (Three.js, PlayCanvas,
Babylon, plain WebGL, a Node game server). The SDK gives you the entities and the geometry; the
renderer and physics adapters are optional. Two other integrations exist outside this plugin's
scope: a Godot plugin, and a single-file C SDK (`liminal.h` plus `liminal.c`, C99, MIT) for
games and engines written in C or C++ or anything that can call C. The C SDK ships as
`liminal_sdk-<version>-c.zip` with each release and is documented under C SDK at
[liminal.lv/docs](https://liminal.lv/docs). Any other engine can read a `.lm` because it is
standard glTF 2.0 with two node extensions, documented in the same place.

## Install the plugin (Claude Code)

```bash
claude plugin marketplace add liminal-lv/liminal-claude
claude plugin install liminal@liminal
```

Then, inside your game project, run:

```
/liminal:setup
```

That command checks Node, Python, Blender, the two add-ons, the `liminal-mcp` server and your
project's workspace, and tells you what to do about whatever is missing. It is safe to run as
often as you like.

Other assistants: the `skills/` folder is plain Markdown in the agent-skills format, and the
MCP server is any-client. Point your tool at `skills/*/SKILL.md` and register `liminal-mcp`
(stdio, started from the game project directory) however your client takes MCP servers.

## What is in this plugin

| Path | What it does |
|---|---|
| `commands/setup.md` | `/liminal:setup`, the environment doctor |
| `skills/liminal-start` | The onboarding path and the mental model, read this first |
| `skills/liminal-web` | Integrating the Web SDK: registry, workspace sync, reading levels, colliders, rendering |
| `skills/liminal-entities` | Designing entities well: prop types, wiring, choices, gizmos, preview models, and a validator |
| `skills/liminal-levels` | Authoring levels in Blender through the MCP tools, and the conventions a good level follows |
| `mcp/` | The `liminal-mcp` server (Python). `pip install ./mcp` or `pip install liminal-mcp` |
| `scripts/` | `doctor.py` behind the setup command, `validate_entities.py` for `entities.json` |

## The path, in order

1. **Setup.** `/liminal:setup` until it is green. The assistant installs `liminal-mcp`, you
   install the two Blender add-ons from Edit > Preferences > Get Extensions > Install from Disk.
2. **Describe your entities** in TypeScript with `@liminal-lv/core` and run `liminal sync` to
   write the Blender workspace. The `liminal-entities` skill covers what makes an entity
   pleasant to place and wire.
3. **Point Blender at the workspace.** In the editor's preferences, add a game configuration
   whose Workspace Folder is the synced `_blender` folder, then select it in the LM Toolkit
   sidebar. Your entities appear under Add > Entity.
4. **Build a level.** By hand in Blender, or by asking the assistant, which now has the
   `lm_*` tools: place entities, set props, wire signals, lint, export. The `liminal-levels`
   skill is the workflow.
5. **Load it in the game** with `parseScene` from `@liminal-lv/core`, and turn the geometry into
   meshes and colliders with the adapters. The `liminal-web` skill has the code.

Loop on 4 and 5. Export from Blender, reload the game, repeat.

## Where to get help

- Documentation: [liminal.lv/docs](https://liminal.lv/docs)
- Web SDK source and example game: `integrations/web/` in the Liminal Editor repository
- This plugin's issues: the Issues tab of this repository
