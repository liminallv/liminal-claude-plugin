import argparse
import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import __version__
from .client import BridgeClient, BridgeFailure, BridgeUnreachable, NoSession
from .discovery import describe_sessions

mcp = FastMCP("liminal")
_client: BridgeClient | None = None
_dev = False


def _ok(value) -> str:
    return json.dumps({"ok": True, "value": value, "error": None})


def _err(message: str, traceback: str = "") -> str:
    return json.dumps({"ok": False, "value": None, "error": {"message": message, "traceback": traceback}})


def _call(method: str, timeout: float = 30.0, **params) -> str:
    try:
        return _ok(_client.call(method, timeout=timeout, **params))
    except BridgeFailure as e:
        return _err(str(e), e.traceback)
    except (BridgeUnreachable, NoSession) as e:
        return _err(str(e))


@mcp.tool()
def lm_sessions() -> str:
    """List the running Blenders that have the Liminal Bridge add-on enabled.

    Each entry carries pid, port, the open .blend, the configured workspace folder
    (project_dir) and whether that workspace lies inside the current project. The
    server talks to the one whose workspace is inside this project; when several
    qualify or none does, pin one with lm_use_session.
    """
    try:
        return _ok({"project_root": str(_client.project_root), "pinned_pid": _client.pinned_pid,
                    "sessions": describe_sessions(_client.project_root)})
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def lm_use_session(pid: int = 0) -> str:
    """Pin the Blender session to talk to, by pid from lm_sessions. Pass 0 to go back to automatic selection."""
    _client.pin(pid or None)
    try:
        return _ok(_client.session())
    except NoSession as e:
        return _err(str(e))


@mcp.tool()
def lm_ping() -> str:
    """Check that Blender, the bridge and Liminal Editor are reachable, and report versions and developer mode."""
    try:
        return _ok(_client.health())
    except (BridgeUnreachable, NoSession) as e:
        return _err(str(e))


@mcp.tool()
def lm_workspace_info() -> str:
    """Describe the Liminal workspace the open Blender scene is bound to.

    Returns the workspace folder (project_dir), whether it is valid, the levels
    directory where exports land, the manifest revision, how many entity
    definitions are loaded, the geometry tags, and the editor and bridge versions.
    Call this first; most other tools need a valid workspace with definitions loaded.
    """
    return _call("workspace_info")


@mcp.tool()
def lm_reload_workspace() -> str:
    """Reload entities.json, preview models and materials from the workspace folder.

    Use after your game regenerated entities.json (for example after `liminal sync`),
    so Blender's Add menu and property panels pick up the change.
    """
    return _call("reload_workspace", timeout=120.0)


@mcp.tool()
def lm_list_entity_defs(category: str = "") -> str:
    """List every entity classname the loaded manifest offers, with its wiring props.

    category filters by the classname prefix before the first underscore
    (for example "func" or "env"). sources are the props that receive signals,
    destinations the props that send them. Use before lm_add_entity.
    """
    return _call("list_entity_defs", category=category)


@mcp.tool()
def lm_get_entity_def(classname: str) -> str:
    """Return the full schema of one entity classname: description, metadata and every prop.

    Props carry name, type, default, choices (for enum props), min, max, step and
    whether they are a wiring source or destination. Choice props arrive as type
    "enum" with the valid labels in choices.
    """
    return _call("get_entity_def", classname=classname)


@mcp.tool()
def lm_get_entity_def_by_object(name: str) -> str:
    """Return the entity schema for a placed object, looked up through its classname."""
    return _call("get_entity_def_by_object", name=name)


@mcp.tool()
def lm_list_entities(classname: str = "", collection: str = "", selected_only: bool = False) -> str:
    """List the entities placed in the current scene with name, classname, collection and position."""
    return _call("list_entities", classname=classname, collection=collection, selected_only=selected_only)


@mcp.tool()
def lm_get_entity(name: str) -> str:
    """Dump one placed entity: all prop values, its wiring sources and destinations, transform and parent."""
    return _call("get_entity", name=name)


@mcp.tool()
def lm_add_entity(classname: str, name: str = "", location: list[float] | None = None,
                  props: dict | None = None) -> str:
    """Place a new entity through the editor's own spawn path, exactly like the Add menu does.

    location is [x, y, z] in Blender world space (Z up); omit it to spawn at the
    3D cursor. props are validated and coerced against the definition, and unknown
    prop names are rejected. Returns the object name Blender assigned, which may
    carry a .001 suffix when the requested name was taken.
    """
    return _call("add_entity", timeout=60.0, classname=classname, name=name, location=location, props=props or {})


@mcp.tool()
def lm_set_entity_props(name: str, props: dict) -> str:
    """Set several props on a placed entity at once, validated against its definition.

    Nothing is written unless every prop validates. Coercion: int and float parse
    from strings, bool accepts true/false/yes/no, Color accepts #RRGGBB or
    [r, g, b, a], enum props match exactly, then case-insensitively, then by a
    unique substring. Returns previous and new values per prop.
    """
    return _call("set_entity_props", name=name, props=props)


@mcp.tool()
def lm_set_entity_prop(name: str, prop: str, value: str | int | float | bool | list) -> str:
    """Set one prop on a placed entity. See lm_set_entity_props for the coercion rules."""
    return _call("set_entity_props", name=name, props={prop: value})


@mcp.tool()
def lm_set_transform(name: str, location: list[float] | None = None,
                     rotation_euler: list[float] | None = None, scale: list[float] | None = None) -> str:
    """Move, rotate or scale an object. rotation_euler is XYZ radians; any argument left out is untouched."""
    return _call("set_transform", name=name, location=location, rotation_euler=rotation_euler, scale=scale)


@mcp.tool()
def lm_delete_entities(names: list[str]) -> str:
    """Delete placed entities by object name. Refuses objects that are not entities."""
    return _call("delete_entities", names=names)


@mcp.tool()
def lm_wire(sender: str, receiver: str, destination_prop: str = "", source_prop: str = "",
            connection_name: str = "") -> str:
    """Connect two entities: the sender's destination prop and the receiver's source prop get the same name.

    Wiring props are found by type from each definition, never by name. When an
    entity has exactly one destination or source prop it is picked automatically;
    with several, name it and the error lists the options. connection_name
    defaults to the receiver's existing source value, else a sanitised form of
    its object name. Several senders may share one connection, and one connection
    may be answered by several receivers.
    """
    return _call("wire", sender=sender, receiver=receiver, destination_prop=destination_prop,
                 source_prop=source_prop, connection_name=connection_name)


@mcp.tool()
def lm_resolve_wiring(name: str) -> str:
    """Show who signals this entity (senders) and whom it signals (receivers), one hop each way."""
    return _call("resolve_wiring", name=name)


@mcp.tool()
def lm_lint_wiring() -> str:
    """Check every entity in the scene against its definition and index all wiring.

    Errors: unknown_classnames, missing_props, dangling_destinations (a destination
    no source answers). Informational: orphan_sources and shared_sources.
    """
    return _call("lint_wiring")


@mcp.tool()
def lm_export_level(filepath: str = "") -> str:
    """Export the scene as a .lm level through the editor's own export operator.

    With no filepath the file goes to <workspace>/levels/<blend name>.lm, which is
    where the game expects it. Save the .blend first so the level has a name.
    """
    return _call("export_level", timeout=300.0, filepath=filepath)


@mcp.tool()
def lm_add_block(name: str = "", size: list[float] | None = None, location: list[float] | None = None,
                 collision: str = "BOX", material: str = "") -> str:
    """Add a box mesh as level geometry, for floors, walls and blockouts.

    size is [x, y, z] in metres, location its centre in Blender world space
    (Z up). collision is the shape the game should build for it: BOX for walls
    and floors, CONCAVE for exact static shapes, NONE for purely visual meshes.
    material names a material from the workspace library, if the level uses one.
    """
    return _call("add_block", name=name, size=size or [1.0, 1.0, 1.0], location=location or [0.0, 0.0, 0.0],
                 collision=collision, material=material)


@mcp.tool()
def lm_get_geometry(name: str) -> str:
    """Read a level mesh's collision kind, geometry tags, dimensions and location."""
    return _call("get_geometry", name=name)


@mcp.tool()
def lm_set_geometry(name: str, collision: str = "", tags: list[str] | None = None) -> str:
    """Set a level mesh's collision kind (SPHERE, BOX, CYLINDER, CAPSULE, CONVEX, CONCAVE, NONE) and/or its geometry tags.

    Tags must be ones the manifest declares (see geo_tags in lm_workspace_info).
    An argument left out is untouched.
    """
    return _call("set_geometry", name=name, collision=collision or None, tags=tags)


@mcp.tool()
def lm_save_blend(filepath: str = "") -> str:
    """Save the current .blend, to filepath or to where it was opened from. Export needs a saved file for its name."""
    return _call("save_blend", timeout=120.0, filepath=filepath)


@mcp.tool()
def lm_open_blend(filepath: str, discard_changes: bool = False) -> str:
    """Open a .blend file. Refuses while the current file has unsaved changes unless discard_changes is true."""
    return _call("open_blend", timeout=120.0, filepath=filepath, discard_changes=discard_changes)


@mcp.tool()
def lm_new_blend(discard_changes: bool = False) -> str:
    """Start an empty scene for a new level. Refuses while the current file has unsaved changes unless discard_changes is true."""
    return _call("new_blend", timeout=60.0, discard_changes=discard_changes)


@mcp.tool()
def lm_scene_info() -> str:
    """Summarise the scene: object counts by type and collection, entity count, selection, active object, cursor."""
    return _call("scene_info")


@mcp.tool()
def lm_search_objects(name_pattern: str = "", type: str = "", collection: str = "",
                      selected_only: bool = False, limit: int = 200) -> str:
    """Find scene objects by glob name pattern, Blender type (MESH, EMPTY, LIGHT...), collection or selection."""
    return _call("search_objects", name_pattern=name_pattern, type=type, collection=collection,
                 selected_only=selected_only, limit=limit)


@mcp.tool()
def lm_select(names: list[str], additive: bool = False) -> str:
    """Select objects by name, replacing the selection unless additive is true."""
    return _call("select", names=names, additive=additive)


@mcp.tool()
def lm_focus(name: str) -> str:
    """Select an object and frame it in the 3D viewport."""
    return _call("focus", name=name)


def _register_developer_tools() -> None:
    @mcp.tool()
    def blender_exec(code: str, timeout: float = 30.0) -> str:
        """Run Python inside Blender on its main thread. Developer mode only.

        The namespace persists across calls with bpy and mathutils imported.
        Raise timeout for long operations such as glTF export or import.
        Returns captured stdout.
        """
        try:
            reply = _client.exec(code, timeout=timeout)
            return reply.get("stdout", "") or "(no output)"
        except BridgeFailure as e:
            return f"ERROR: {e}\n{e.traceback}"
        except (BridgeUnreachable, NoSession) as e:
            return f"ERROR: {e}"

    @mcp.tool()
    def blender_eval(expr: str) -> str:
        """Evaluate a Python expression inside Blender and return its repr. Developer mode only."""
        try:
            reply = _client.eval(expr)
            out = reply.get("stdout", "")
            return (out + "\n" if out else "") + str(reply.get("value"))
        except BridgeFailure as e:
            return f"ERROR: {e}\n{e.traceback}"
        except (BridgeUnreachable, NoSession) as e:
            return f"ERROR: {e}"

    @mcp.tool()
    def blender_get_log(lines: int = 100) -> str:
        """Return the most recent lines Blender printed to its console. Developer mode only."""
        try:
            return "\n".join(_client.log()[-lines:]) or "(log empty)"
        except (BridgeFailure, BridgeUnreachable, NoSession) as e:
            return f"ERROR: {e}"

    @mcp.tool()
    def blender_get_object(name: str) -> str:
        """Full dump of any Blender object: transform, hierarchy, collections, data block, custom properties."""
        return _call("get_object", name=name)

    @mcp.tool()
    def blender_set_object_prop(name: str, path: str, value: str | int | float | bool | list) -> str:
        """Set a dotted attribute (location.x, hide_render) or a raw custom property on any object. Developer mode only.

        For entity props prefer lm_set_entity_props, which validates against the definition.
        """
        return _call("set_object_prop", name=name, path=path, value=value)

    @mcp.tool()
    def blender_search_operators(query: str = "", limit: int = 50) -> str:
        """Search Blender's registered operators by idname, label or description."""
        return _call("search_operators", query=query, limit=limit)


def main() -> None:
    global _client, _dev
    parser = argparse.ArgumentParser(prog="liminal-mcp", description="MCP server for Liminal Editor")
    parser.add_argument("--project", default=os.getcwd(),
                        help="Game project root; the Blender whose workspace lies inside it is used")
    parser.add_argument("--dev", action="store_true",
                        help="Expose developer tools (exec, eval, log, raw object access); Blender must have Developer Mode on")
    parser.add_argument("--version", action="version", version=__version__)
    args, _ = parser.parse_known_args()
    _client = BridgeClient(Path(args.project).resolve())
    _dev = args.dev
    if _dev:
        _register_developer_tools()
    mcp.run(transport="stdio")
