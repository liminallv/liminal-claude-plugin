---
name: liminal-levels
description: Author and inspect game levels in Blender through the Liminal MCP tools (lm_*). Use when asked to build, block out, populate, wire, lint, fix or export a level, to place or configure entities, or to explain what a level contains. Covers the tool workflow, Blender conventions that matter for export, and how to recover when Blender is not reachable.
---

# Authoring levels through the bridge

The `lm_*` tools drive the Liminal Editor add-on inside a running Blender through the Liminal
Bridge. Everything they do goes through the editor's own code paths, so an entity you place is
identical to one placed from the Add menu, and an export is the same file the Export Level
button writes. You never need Blender's Python for level work; if a tool is missing, say so
rather than working around it.

## Before anything

1. `lm_ping`. If it fails: Blender is not running, the bridge add-on is not enabled, or
   several Blenders are open and none matches this project. `lm_sessions` shows what the
   server sees; `lm_use_session(pid)` pins one. Walk the user through the fix from
   `/liminal:setup` rather than guessing.
2. `lm_workspace_info`. `workspace_valid` must be true and `entity_def_count` above zero. If
   not, the user has to select a game configuration in the LM Toolkit sidebar (press N in the
   3D viewport). After a `liminal sync` that changed the registry, `lm_reload_workspace`.
3. `lm_list_entity_defs`, then `lm_get_entity_def` for each classname you are about to use.
   Props, defaults, choices and wiring props come from there. Do not assume prop names.

## Coordinates and units

Blender is **Z up**, metres, right-handed. `location` everywhere in these tools is Blender
world space. The export converts to glTF Y up; the game never sees Blender axes. A 2D
top-down game that reads the `xz` plane sees Blender X as X and Blender Y as depth; a side-on
game on `xy` sees Blender Z as up. Ask which plane the game uses before laying things out.

Rotation is `rotation_euler`, XYZ radians. Facing conventions (which local axis is "forward")
belong to the entity definition's description; read it.

## Building a level, in order

1. **File.** A new level starts with `lm_new_blend`, then `lm_save_blend` to
   `blender/<level>.blend` inside the project (never inside `_blender/`, which sync owns).
   The export name comes from the `.blend` name, so name it like the level.
2. **Geometry.** `lm_add_block` for floors, walls, platforms. Floors: large flat box with
   collision BOX. Walls: thin tall boxes. Give meshes names (`floor_main`, `wall_north`).
   Default collision is BOX; use CONCAVE only for shapes that are genuinely not convex, NONE
   for decoration. `lm_set_geometry` changes collision and applies manifest geo tags
   (`lm_workspace_info` lists them). Anything beyond boxes is for the designer in Blender, or
   for the game to generate; say so.
3. **Entities.** `lm_add_entity(classname, name, location, props)`. Name them by role
   (`door_lab_entry`, `trigger_arena_start`). Set props at creation when you know them, or
   with `lm_set_entity_props` later. Volume entities spawn as a unit cube: size them with
   `lm_set_transform(scale=...)`, position with `location`. A floor at Z 0 means entities sit
   at Z 0 too unless the definition says they hover.
4. **Wiring.** `lm_wire(sender, receiver)`; name `destination_prop` or `source_prop` when the
   definition has more than one, and pass `connection_name` when several senders should share
   it. `lm_resolve_wiring(name)` shows one entity's neighbours. Connection names are plain
   strings; use descriptive ones (`arena_start`, `exit_unlock`).
5. **Lint.** `lm_lint_wiring`. Fix every `dangling_destinations` entry (a signal nobody
   receives) and `missing_props` (a stale entity; `lm_reload_workspace` usually repairs).
   `orphan_sources` are fine when the game signals them itself. `unknown_classnames` means
   the registry changed under the level; either restore the entity or delete it.
6. **Save and export.** `lm_save_blend`, then `lm_export_level`. The file lands in
   `<workspace>/levels/<blend name>.lm`. Tell the user the path and suggest
   `npx liminal verify <name>` in the game project, which parses it with the real registry and
   prints warnings.

## Reading an existing level

`lm_scene_info` for the shape of it, `lm_list_entities` for every entity (filter by classname
or collection), `lm_get_entity` for one, `lm_search_objects(type="MESH")` for geometry,
`lm_lint_wiring` for the signal graph's health. To describe a level to the user, group by
classname and summarise the wiring chains, not the coordinates.

`lm_focus(name)` frames an object in the viewport, which is the fastest way to show the user
what you mean. `lm_select` sets the selection for them to act on.

## Conventions that keep designers and the game happy

- One `.blend` per level, saved in the repo, exported into the workspace.
- Entities named by role; Blender appends `.001` on collisions, so check the returned name.
- A `text` gizmo showing the connection name exists on most well-designed entities; when it
  does not, suggest adding one in the registry rather than leaving comments in the scene.
- Keep level geometry in the scene's default collection unless the project has a convention.
  Collections export as hierarchy; the game does not need them.
- Do not touch the `.LM_Models` collection or anything starting with a dot: those are the
  editor's preview assets.
- Do not edit `entity_type`, `entity_uid` or `__lm_*` custom properties. The tools will not
  let you, and raw access needs developer mode that customers do not have.

## When Blender says no

Every tool returns `{"ok": false, "error": {"message": ...}}` with a reason written for a
person. Read it; it names the valid options, the missing configuration or the prop list. Three
that recur:

- *Developer Mode, which is off*: you called a tool outside the customer set. Use the `lm_*`
  equivalent.
- *Classname not in the loaded manifest*: run `lm_reload_workspace`, or the registry was never
  synced; `npx liminal sync` in the game project first.
- *Timeout*: Blender's main thread is busy, often a modal dialog. Ask the user to look at
  Blender. Do not repeat a request that creates things until `lm_ping` is healthy and
  `lm_list_entities` confirms what exists.
