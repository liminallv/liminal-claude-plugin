import argparse
import json
import re
import sys
from pathlib import Path

SCALAR_TYPES = {"source", "destination", "bool", "int", "float", "String", "Color"}
GIZMO_TYPES = {"sphere", "arrow", "cone", "frustum", "box", "billboard", "volume", "text", "path"}
GIZMO_FIELDS = {"radius", "length", "angle", "fov", "near", "far", "size", "size_x", "size_y", "size_z",
                "texture", "texture_scale", "color", "style", "alpha", "offset", "euler", "text",
                "mode", "closed"}
HEX = re.compile(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")


def default_matches(value, type_str, types):
    if type_str == "bool":
        return isinstance(value, bool)
    if type_str == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_str == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_str in ("String", "source", "destination"):
        return isinstance(value, str)
    if type_str == "Color":
        return isinstance(value, list) and len(value) == 4 and all(isinstance(c, (int, float)) for c in value)
    if type_str.startswith("$"):
        key = type_str[1:].removesuffix("[]")
        labels = types.get(key, {})
        if type_str.endswith("[]"):
            return isinstance(value, str) and all(v.strip() in labels for v in value.split(",") if v.strip())
        return isinstance(value, str) and value in labels
    return True


def validate(manifest: dict, report: Report) -> None:
    if not isinstance(manifest, dict):
        report.error("root", "manifest must be a JSON object")
        return
    if not isinstance(manifest.get("revision"), int):
        report.error("revision", "missing or not an integer")
    types = manifest.get("types", {})
    if not isinstance(types, dict):
        report.error("types", "must be an object")
        types = {}
    for key, members in types.items():
        if not isinstance(members, dict) or not members:
            report.error(f"types.{key}", "must be a non-empty object of label -> value")
            continue
        kinds = {type(v) for v in members.values()}
        if not kinds <= {int, str} or len(kinds) > 1:
            report.error(f"types.{key}", "values must be all integers or all strings")
    entities = manifest.get("entities")
    if not isinstance(entities, list) or not entities:
        report.error("entities", "must be a non-empty array")
        return
    seen = set()
    for i, e in enumerate(entities):
        where = f"entities[{i}]"
        if not isinstance(e, dict):
            report.error(where, "must be an object")
            continue
        cls = e.get("classname")
        if not isinstance(cls, str) or not cls:
            report.error(where, "classname is required")
            continue
        where = cls
        if cls in seen:
            report.error(where, "duplicate classname")
        seen.add(cls)
        if not re.match(r"^[a-z0-9]+(_[a-z0-9]+)*$", cls):
            report.warn(where, "classnames are conventionally lower_snake_case; the part before the first "
                               "underscore becomes the Add menu category")
        if "_" not in cls:
            report.warn(where, "no underscore, so this entity lands in a category named after itself")
        if not isinstance(e.get("uid"), str) or not e["uid"]:
            report.error(where, "uid is required (whatever your game resolves the entity from)")
        if not e.get("description"):
            report.warn(where, "no description; designers see it in the Add menu")
        meta = e.get("metadata", {})
        if meta and not isinstance(meta, dict):
            report.error(where, "metadata must be an object")
            meta = {}
        color = meta.get("color")
        if color is not None and not (isinstance(color, str) and HEX.match(color)):
            report.error(where, f"metadata.color {color!r} must be #RRGGBB or #RRGGBBAA")
        if "volume" in meta and not isinstance(meta["volume"], bool):
            report.error(where, "metadata.volume must be a boolean")
        props = e.get("props", [])
        if not isinstance(props, list):
            report.error(where, "props must be an array")
            props = []
        names = set()
        sources = destinations = 0
        for p in props:
            if not isinstance(p, dict) or not isinstance(p.get("name"), str):
                report.error(where, f"prop without a name: {p!r}")
                continue
            pw = f"{cls}.{p['name']}"
            if p["name"] in names:
                report.error(pw, "duplicate prop name")
            names.add(p["name"])
            t = p.get("type")
            if not isinstance(t, str):
                report.error(pw, "type is required")
                continue
            if t.startswith("$"):
                key = t[1:].removesuffix("[]")
                if key not in types:
                    report.error(pw, f"references type {key!r} which is not in types")
            elif t not in SCALAR_TYPES:
                report.error(pw, f"unknown type {t!r}; valid: {', '.join(sorted(SCALAR_TYPES))}, $TypeKey, $TypeKey[]")
            if t == "source":
                sources += 1
            if t == "destination":
                destinations += 1
            if "default_value" in p and p["default_value"] is not None and not default_matches(p["default_value"], t, types):
                report.error(pw, f"default_value {p['default_value']!r} does not match type {t}")
            for bound in ("min", "max", "step"):
                if bound in p and t not in ("int", "float"):
                    report.warn(pw, f"{bound} only applies to int and float props")
        if destinations and not sources:
            report.warn(where, "sends signals but has no source prop, so nothing can target it back; fine for pure senders")
        gizmos = meta.get("gizmos", [])
        if gizmos and not isinstance(gizmos, list):
            report.error(where, "metadata.gizmos must be an array")
            gizmos = []
        for gi, g in enumerate(gizmos):
            gw = f"{cls}.gizmos[{gi}]"
            if not isinstance(g, dict):
                report.error(gw, "must be an object")
                continue
            gt = g.get("type")
            if gt not in GIZMO_TYPES:
                report.error(gw, f"unknown gizmo type {gt!r}; valid: {', '.join(sorted(GIZMO_TYPES))}")
            if gt == "volume" and not meta.get("volume"):
                report.warn(gw, "a volume gizmo only draws on an entity with metadata.volume true")
            for field, value in g.items():
                if field in ("type", "bindings"):
                    continue
                if field not in GIZMO_FIELDS:
                    report.warn(gw, f"unknown gizmo field {field!r}")
                elif not isinstance(value, str):
                    report.error(gw, f"gizmo field {field} must be a string (the addon parses numbers from strings)")
            if gt in ("box", "sphere", "cone", "arrow", "frustum", "billboard") and g.get("color") and not HEX.match(str(g["color"])):
                report.error(gw, f"color {g['color']!r} must be #RRGGBB")
            for field, prop in (g.get("bindings") or {}).items():
                if prop not in names:
                    report.error(gw, f"binding {field} -> {prop!r} names a prop this entity does not have")


def main():
    parser = argparse.ArgumentParser(description="Validate a Liminal entities.json against the workspace contract")
    parser.add_argument("path", nargs="?", default="_blender/entities.json")
    args = parser.parse_args()
    path = Path(args.path)
    if not path.exists():
        print(f"no such file: {path}")
        sys.exit(2)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        print(f"{path}: not valid JSON: {e}")
        sys.exit(2)
    report = Report()
    validate(manifest, report)
    for w in report.warnings:
        print(f"warning  {w}")
    for e in report.errors:
        print(f"error    {e}")
    count = len(manifest.get("entities", [])) if isinstance(manifest, dict) else 0
    print(f"{path}: {count} entities, {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    sys.exit(1 if report.errors else 0)


if __name__ == "__main__":
    main()
