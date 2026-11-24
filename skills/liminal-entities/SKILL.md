---
name: liminal-entities
description: Design and author Liminal entity definitions for a game, in TypeScript with @liminal/core or as raw entities.json. Use when adding or changing an entity, choosing prop types, naming wiring props, defining choice types, adding viewport gizmos or preview models, or when entities.json fails to load in Blender. Includes a validator for entities.json.
---

# Authoring entities

An entity definition is the whole interface a designer gets for one kind of thing: what it is
called, what can be tuned, what it connects to, how it looks in the viewport. A good one makes
a level readable at a glance in Blender and leaves nothing to explain in chat.

Write them in TypeScript with `defineEntity` (see `liminal-web` for the registry mechanics).
This skill is about what to put in them. The underlying `entities.json` contract is at the end
for projects that generate it another way.

## Naming

- `category_name` in lower snake case. The part before the first underscore is the Add menu
  category, so pick a handful and stick to them: `info_` (markers), `func_` (things that do
  something), `env_` (lights, sounds, ambience), `item_` (pickups), `prop_` (physical props),
  `ai_` (spawners, behaviours). Quake-lineage names, because designers know them.
- Give every entity a `description`. It is the tooltip in the Add menu and the only place a
  designer learns what the thing does without reading code.

## Prop types

| Type | Blender shows | You get | Use for |
|---|---|---|---|
| `bool` | checkbox | boolean | flags |
| `int` | integer field | number | counts; add `min`, `max`, `step` |
| `float` | float field | number | distances, speeds, times |
| `String` | text field | string | names, free text |
| `Color` | colour picker | `[r, g, b, a]` linear 0..1 | tints |
| `source` | text field | string | this entity's own connection name |
| `destination` | text field + pick button, draws an arrow | string | the name this entity signals |
| `$TypeKey` | dropdown | the type's value for the chosen label | enums |
| `$TypeKey[]` | multi-select | comma-joined labels | flags, layers |

Give every tunable prop a `default_value` that makes a freshly placed entity work with no
edits. A designer should be able to drop a door and have it open.

## Wiring

- A `source` prop is "I answer to this name". A `destination` prop is "I signal this name".
  A connection exists when they hold the same string. One destination may reach many
  receivers; many senders may share one connection.
- Name wiring props after what the signal means, not after the mechanism: `on_enter`,
  `on_cleared`, `unlock_name`. Keep `targetname` as the conventional single source prop when
  an entity has only one.
- An entity that only sends (a trigger) needs no source. An entity that only receives (a door)
  needs no destination. Give an entity several sources when it reacts differently per channel
  (`targetname` to open, `lock_name` to lock), because the designer then wires each with its
  own arrow.
- The payload is yours. The SDK ships two conventions, `ACTIVATE` and `DEACTIVATE`; most games
  need nothing more.

## Choice types

```ts
props: [{ name: 'mode', type: '$Door.Mode', default_value: 'Slide' }],
types: { 'Door.Mode': { Slide: 0, Swing: 1 } },
```

Values may be integers or strings (asset paths, ids). Labels are what the designer sees and
what the exported level carries; `parseScene` resolves them back to values. Share a type
across entities by declaring it identically in each.

## Volumes

`metadata.volume: true` makes the entity a brush: the designer shapes a mesh and the export
carries it. Triggers, ambient zones, kill volumes, nav hints. Add a `volume` gizmo so the body
is tinted in the viewport. In the game, `entity.mesh` is the shape; the collision adapters
turn it into a collider.

## Preview models and colour

- `metadata.color` tints the entity in Blender. Pick one colour per category.
- `metadata.model` names a `.glb` under `_blender/models/`. Supply it from `liminal.config.ts`
  with `models: { func_door: box(1, 2, 0.2) }` using `@liminal/core/glb-write`, or any real
  mesh. A stand-in box of the right size is worth more than a detailed model: the designer
  needs the footprint.
- Without a model an entity is a small empty; fine for markers, poor for anything with size.

## Gizmos

Procedural shapes drawn in the viewport, driven live by props through `bindings`.

| Type | Fields | Typical use |
|---|---|---|
| `sphere` | `radius` | ranges, radii |
| `arrow` | `length` | facing |
| `cone` | `length`, `angle` | spotlights, view cones |
| `frustum` | `fov`, `near`, `far` | cameras |
| `box` | `size` or `size_x/y/z` (half extents) | footprints |
| `billboard` | `size`, `texture` | icons |
| `volume` | `color`, `alpha`, `texture`, `texture_scale` | brush fill |
| `text` | `text` with `{{prop}}` tokens, `size` | labels |
| `path` | `mode`, `closed` | routes through child entities |

All numeric fields are **strings** in the manifest. Bind a dimension to a prop so the
viewport reflects the tuning: `{ type: 'sphere', radius: '5', bindings: { radius: 'range' } }`.
A `text` gizmo showing `{{targetname}}` is the single most useful gizmo for debugging wiring.
Common fields: `color` (`#RRGGBB`), `style` (`wire` or `solid`), `alpha`, `offset` (`"x,y,z"`),
`euler` (degrees, Blender space).

## A checklist before `liminal sync`

- Every entity has a description and a sensible default for every prop.
- Wiring props are typed `source` or `destination`, never `String`.
- Choice props reference a type that exists.
- Anything with physical size has a model or a box gizmo.
- New entities were appended, not inserted.

Then:

```bash
npx liminal sync
python <plugin>/scripts/validate_entities.py _blender/entities.json
```

The validator checks the contract (types, defaults, type references, gizmo fields, bindings)
and warns about the conventions above. Blender's own loader is stricter about nothing the
validator passes; if Blender still refuses the manifest, the LM Config panel shows the error.

## The entities.json contract, for generators

```json
{
  "revision": 3,
  "types": { "Door.Mode": { "Slide": 0, "Swing": 1 } },
  "geo_tags": ["walkable", "skip_nav"],
  "entities": [
    {
      "classname": "func_door",
      "uid": "func_door",
      "description": "Sliding door.",
      "metadata": {
        "color": "#90caf9",
        "model": "func_door",
        "volume": false,
        "gizmos": [{ "type": "text", "text": "{{targetname}}", "size": "0.4" }]
      },
      "props": [
        { "name": "targetname", "type": "source" },
        { "name": "speed", "type": "float", "default_value": 1.5, "min": 0.1, "max": 10 },
        { "name": "mode", "type": "$Door.Mode", "default_value": "Slide" }
      ]
    }
  ]
}
```

`revision` must change only when the content changes. `geo_tags` are the per-mesh tags a
designer can toggle on level geometry; they come back in `LM_geo.tags`. Models live at
`_blender/models/<model>.glb`. Gizmo textures are PNGs under `_blender/gizmo_textures/` named
by the key the gizmo's `texture` field holds.
