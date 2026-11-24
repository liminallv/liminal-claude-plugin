---
name: liminal-web
description: Integrate the Liminal Web SDK (@liminal/core, @liminal/cli, @liminal/three, @liminal/collision-2d, @liminal/collision-3d) into a JavaScript or TypeScript game. Use when writing the entity registry, liminal.config.ts, running liminal sync, loading a .lm level with parseScene, building colliders or Three.js meshes from level geometry, dispatching entity signals, or debugging a level that loads wrong.
---

# Liminal Web SDK

Engine-agnostic TypeScript. `@liminal/core` has zero runtime dependencies and runs in a
browser bundle and on a Node server unchanged. The adapters are optional. The authoritative
reference is the SDK README in the Liminal Editor repository (`integrations/web/README.md`)
and the example game beside it (`integrations/web/examples/alien-invasion`); this skill is the
working subset.

## Install

```bash
npm install @liminal/core
npm install -D @liminal/cli
npm install @liminal/three            # if rendering with Three.js
npm install @liminal/collision-2d     # or @liminal/collision-3d
```

Node 22.18 or newer runs `liminal.config.ts` natively. Older Node: `npx tsx liminal sync`.

## The registry: one file both halves import

```ts
// src/entities.ts
import { createRegistry, defineEntity } from '@liminal/core';

export const info_player_start = defineEntity({
  classname: 'info_player_start',
  uid: 'info_player_start',
  description: 'Where the player appears. Local +Y is the facing.',
  metadata: { color: '#4caf50', gizmos: [{ type: 'arrow', length: '1.5' }] },
  props: [],
});

export const func_trigger = defineEntity({
  classname: 'func_trigger',
  uid: 'func_trigger',
  description: 'Brush volume that signals on enter and exit.',
  metadata: { color: '#ffb300', volume: true, gizmos: [{ type: 'volume', alpha: '0.2' }] },
  props: [
    { name: 'on_enter', type: 'destination' },
    { name: 'on_exit', type: 'destination' },
    { name: 'once', type: 'bool', default_value: false },
  ],
});

export const func_door = defineEntity({
  classname: 'func_door',
  uid: 'func_door',
  description: 'Sliding door. Opens while its targetname is held active.',
  metadata: { color: '#90caf9', model: 'func_door' },
  props: [
    { name: 'targetname', type: 'source' },
    { name: 'speed', type: 'float', default_value: 1.5, min: 0.1, max: 10 },
    { name: 'mode', type: '$Door.Mode', default_value: 'Slide' },
  ],
  types: { 'Door.Mode': { Slide: 0, Swing: 1 } },
});

export const REGISTRY = createRegistry({ info_player_start, func_trigger, func_door });
```

Rules the SDK enforces or depends on:

- Every key of the object passed to `createRegistry` must equal its descriptor's `classname`
  (checked at compile time).
- **Key order is the manifest order.** Re-sorting changes `entities.json`, bumps its revision
  and makes every designer reload. Append.
- Extra fields on a descriptor are yours: extend `EntityDescriptor` with a spawn function, a
  sim factory, anything. Only contract fields reach `entities.json`.
- Choice sets go in `types`; two entities declaring the same set with different members is an
  error.

## The config and the sync

```ts
// liminal.config.ts, beside package.json
import { REGISTRY } from './src/entities.ts';
import { box } from '@liminal/core/glb-write';

export default {
  registry: REGISTRY,
  workspace: '_blender',
  definitionsDir: '_entities',
  materials: [
    { id: 'concrete', name: 'Concrete', color: [0.6, 0.6, 0.6, 1], roughness: 0.9 },
  ],
  models: { func_door: box(1, 2, 0.2) },
  entityDirs: [{ path: 'src/entities', requireAll: true }],
};
```

```bash
npx liminal sync        # writes _blender/: .lmworkspace, entities.json, models/, materials/, gizmo_textures/
npx liminal verify      # parses every level in _blender/levels and reports contents and warnings
npx liminal wiring      # prints a level's signal graph
npx liminal check       # entity files vs registry, both directions
```

`sync` rewrites `entities.json` only when its content changed. Wire it into the dev script
so the manifest can never be stale: `"dev": "liminal sync && vite"`.

Commit `_blender/entities.json` and `_blender/levels/`. The rest of `_blender/` is
regenerated; ignoring it is fine. Authored `.blend` files go in a `blender/` folder.

## Loading a level

```ts
import { parseScene } from '@liminal/core';
import { REGISTRY } from './entities.ts';

const bytes = await fetch('/levels/hangar.lm').then((r) => r.arrayBuffer());
const scene = parseScene(bytes, REGISTRY, { name: 'hangar' });

for (const entity of scene.entities) {
  // entity.classname is a union of your classnames
  // entity.properties has defaults filled and choice labels resolved to your values
  // entity.world is the 4x4 placement; entity.transform is it decomposed
  // entity.mesh is the brush a designer shaped, for a volume entity
  spawn(entity);
}
for (const node of scene.geometry) {
  // node.collision: BOX, SPHERE, CYLINDER, CAPSULE, CONVEX, CONCAVE or NONE
  // node.mesh: positions, normals, uvs, indices, material
  // node.world: placement
}
for (const warning of scene.warnings) console.warn(warning);
```

`scene.warnings` is drift, not failure: a prop the level carries that the registry no longer
declares, or a choice label that no longer exists. Surface them; re-export the level.

Serve `_blender/levels/` as static files, or copy them into `public/levels/` in the build.

### Colliders

```ts
import { collider2dFrom } from '@liminal/collision-2d';
for (const node of scene.geometry) {
  const c = collider2dFrom(node.mesh, node.world, node.collision, { plane: 'xz' });
  if (!c) continue;                       // NONE, or degenerate once flattened
  if (c.box) world.addBox(c.box);
  else if (c.trimesh) world.addTrimesh(c.trimesh);
  else world.addConvex(c.points);
}
```

`@liminal/collision-3d` has the same shape with `space: 'local' | 'world'`. If your physics
engine wants a shape these do not produce, the raw mesh and matrix are right there.

### Rendering with Three.js

```ts
import { toMesh } from '@liminal/three';
for (const node of scene.geometry) three.add(toMesh(node, { library: MATERIALS }));
```

Materials in a `.lm` carry PBR factors and a name; the game resolves the name against its own
library and falls back to the factors. No textures travel in the file.

## Signals

```ts
import { createWiring, lintWiring, LIMINAL_SIGNALS } from '@liminal/core';
const wiring = createWiring<Payload>(scene.entities, REGISTRY);

for (const name of wiring.destinationsFor(trigger.id)) {
  for (const msg of wiring.send(trigger.id, name, LIMINAL_SIGNALS.ACTIVATE, payload)) {
    deliver(msg.receiverId, msg);
  }
}
for (const problem of lintWiring(scene.entities, REGISTRY)) console.warn(problem.message);
```

Wiring is discovered by prop **type**, never by prop name. `target` and `targetname` are a
convention; an entity may have several of each under any names.

## Coordinates

A `.lm` is Y-up glTF. Blender's exporter does the (x, y, z) to (x, z, -y) mapping, so a
matrix from the file drops straight into Three or gl-matrix. A 2D game picks `xy` (side-on)
or `xz` (top-down); `math.ts` in core has `zRotationOf` and `yRotationOf` for the angle.

## Authored entities

An entity can carry its own `.lm`, built in Blender like a level and exported the same way,
with meshes, brush volumes and nested entities. Pass them to `parseScene` as `definitions`
keyed by classname (`loadDefinitionsFromDisk` in `@liminal/cli` reads `definitionsDir`).
Their contents come back in the same `entities` and `geometry` lists with `parentId` set, and
their ids are deterministic across hosts. A networked game must load identical definition
bytes on every host.

## Debugging checklist

- Entity spawns at the wrong place: you applied the matrix twice, or transposed it. Use
  `entity.transform.position` directly first.
- Everything is rotated 90 degrees: a 2D game using the wrong plane option.
- A prop is undefined at runtime: the level predates the prop. `npx liminal verify` lists
  warnings per level.
- Blender shows the old entity list: `liminal sync` did not run, or Blender has not reloaded.
  The manifest revision is shown in the LM Config panel; compare with `entities.json`.
