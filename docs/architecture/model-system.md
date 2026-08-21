# 3D model system architecture

## Purpose

`modelctl` turns an agent-authored, schema-validated scene description into a real GLB asset, then validates and renders it before delivery. The model file is not considered successful until independent structural, topological and visual gates pass.

The first release targets authored hard-surface/product/furniture assets. It does not pretend that a primitive assembly is sufficient for every organic or character request.

## Components

| Component | Role |
|---|---|
| `src/model_system/spec.py` | JSON Schema and semantic validation |
| `src/model_system/build.py` | Blender quality backend and Trimesh fallback |
| `src/model_system/security.py` | bounded single-file GLB intake |
| `src/model_system/inspect.py` | world-space scene, topology, bounds and material metrics |
| `src/model_system/gltf_validator.py` | official Khronos validator adapter |
| `src/model_system/validate.py` | profile-aware QA policy |
| `src/model_system/render.py` | Cycles multi-view render and contact sheet |
| `src/model_system/optimize.py` | source-preserving glTF Transform adapter |
| `src/model_system/viewer.py` | local interactive `<model-viewer>` bundle |
| `src/model_system/doctor.py` | capabilities and deterministic self-test |
| `tools/blender/model_worker.py` | restricted isolated Blender worker |
| `tools/headless-3d-shims/` | CPU/headless runtime compatibility layer |
| `scripts/modelctl` | stable CLI entry point |
| `scripts/bootstrap-modeling.sh` | exact Python/npm/Blender runtime bootstrap |

## Runtime separation and licensing

The main Python package uses permissively licensed geometry/validation libraries. Blender is GPL and is installed into an ignored isolated environment at `.cache/model-runtime/blender`. The source-controlled Blender worker is explicitly GPL-3.0-or-later and communicates with the main package through JSON/files in a subprocess.

The worker never imports the main orchestration package and the main package never imports `bpy`.

## Headless Blender in Arena

The official Blender wheel links desktop ABI libraries even for CPU-only workflows. Arena cannot install them with APT. `tools/headless-3d-shims` supplies null symbols for code paths that must never be called.

Allowed:

- Blender mesh primitives;
- object transforms;
- bevel modifiers;
- Principled PBR materials;
- glTF import/export;
- Cycles CPU rendering.

Forbidden with shims:

- EEVEE;
- viewport screenshots;
- interactive GUI;
- VTK/OpenGL rendering;
- loading arbitrary `.blend` files;
- executing user/model-provided Python.

A deployment with native desktop/OpenGL libraries should omit the shims.

## Build flow

```bash
scripts/bootstrap-modeling.sh
scripts/modelctl create \
  examples/modeling/lounge-chair.json \
  .model-work/lounge-chair.glb \
  --render --render-dir .model-work/lounge-chair-render \
  -o .model-work/lounge-chair-report.json
```

`--backend auto` selects Blender when provisioned and the portable Trimesh builder otherwise. The fallback deliberately warns when a requested bevel cannot be preserved.

### Declarative scope

Version 1.0 supports:

- box/rounded box;
- sphere;
- cylinder;
- cone/frustum;
- torus;
- thin box/plane;
- translation, Euler rotation and scale;
- named PBR materials;
- bevel and smooth shading;
- render/quality settings.

The schema caps object counts, coordinate ranges and mesh segment counts. Semantic checks enforce unique IDs, material references, plausible bevels and finite transforms.

## Secure intake

Initial external intake is intentionally GLB-only:

- exact `glTF` magic/version/declared length;
- aligned, in-bounds chunks;
- one bounded JSON chunk;
- bounded node/mesh/accessor counts;
- no external buffer or image URI;
- no network resolver.

GLB is then parsed by Trimesh only after this gate. glTF validators and optimizers run without a network-enabling option.

## Topology inspection

GLB exporters split vertices at UV and hard-normal seams. Raw index-edge counting would call those seams holes. The inspector therefore:

1. preserves the original mesh for vertex/file statistics;
2. copies it;
3. merges position-equivalent vertices while intentionally ignoring normal/UV splits;
4. performs boundary, nonmanifold, watertight, winding and volume checks on the welded topology copy.

This prevents false warnings without altering the delivered asset.

## QA profiles

### `render`

- Khronos-valid GLB;
- finite geometry;
- no degenerate triangles;
- no nonmanifold edges;
- consistent winding;
- named material required by default;
- open surfaces are warnings.

### `web`

Same structural gates plus a caller-defined triangle budget. Optimization/compression is separate and never overwrites the source.

### `print`

Adds, per geometry:

- watertight closed shell;
- no boundary edge;
- positive solid volume.

Wall thickness, trapped volumes and print orientation are not yet implemented and must not be claimed.

## Rendering and visual QA

`modelctl render` imports the GLB into a fresh factory-reset scene with auto-execution disabled. It computes world-space bounds, fits a camera using the bounding sphere, creates a neutral floor and three-point lighting, and renders requested views with Cycles CPU.

Default views:

- perspective;
- front;
- right;
- back.

The contact sheet is an overview, not a substitute for inspecting individual full-resolution views. The agent must correct clipping, silhouette, floating/intersecting parts, scale and material problems before delivery.

## Optimization

```bash
scripts/modelctl optimize source.glb optimized.glb \
  --compression none --texture-size 2048
```

The fixed glTF Transform route can deduplicate, prune, weld, resize textures and optionally use Meshopt or Draco. It writes a separate file, validates it, and deletes it if QA fails.

Compression is target-dependent:

- uncompressed/quantized GLB maximizes DCC compatibility;
- Draco is useful for static web meshes;
- Meshopt is preferable when target viewers support it, particularly for richer data.

## Interactive review

```bash
scripts/modelctl viewer model.glb -o .model-work/viewer
python3 -m http.server 8000 --directory .model-work/viewer --bind 0.0.0.0
```

The viewer bundle copies its JavaScript locally and contains no CDN dependency for an uncompressed GLB.

## Failure policy

- Never modify an input model in place.
- Never load a supplied `.blend` file automatically.
- Never mark a model complete from one camera angle.
- Never infer manufacturing fitness from a successful render.
- Never claim exact CAD fidelity from a generated triangle mesh.
- Never send a model/reference to a cloud provider without explicit provider configuration and policy approval.
