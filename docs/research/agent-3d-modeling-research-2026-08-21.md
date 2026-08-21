# Research: production 3D modeling for an AI agent in the Arena runtime

**Date:** 2026-08-21
**Runtime:** Debian 12, Python 3.11, Node 22, 2 vCPU, 3.8 GiB RAM, no GPU, no APT/native Blender
**Status:** research complete; the first deterministic Blender/glTF vertical slice is implemented and tested

## Executive conclusion

“Generate a quality 3D model from a prompt” is not one capability. It is three different production lanes:

1. **Deterministic authored assets** — furniture, products, hard-surface props, simple environments and low-poly assemblies. The agent translates intent into dimensions, parts, materials and procedural operations. Blender/Python is the strongest general backend.
2. **Precision CAD** — brackets, enclosures, mechanical parts and fabrication geometry. These require a BREP kernel, constraints, exact dimensions and STEP output. CadQuery/build123d over Open Cascade are the strongest Python choices.
3. **Generative organic assets** — characters, creatures, sculptures and image-conditioned reconstruction. Current high-quality systems are GPU models or hosted APIs. They still require retopology, scale correction, UV/material QA and visual iteration.

The right architecture is therefore **multi-backend and QA-first**, not a single “text-to-3D” endpoint. In this repository the immediately usable baseline is now:

- restricted declarative model specs;
- Blender 4.5 LTS from the official `bpy` wheel;
- Cycles CPU multi-view rendering;
- glTF/GLB export;
- Trimesh topology inspection;
- official Khronos glTF validation;
- glTF Transform optimization;
- a local interactive `<model-viewer>` bundle;
- a mandatory visual feedback loop.

A local neural text/image-to-3D model is not credible in the present 3.8 GiB CPU-only sandbox. Provider adapters are the correct later route, with keys supplied only through secrets/environment.

## 1. Runtime constraints established experimentally

| Capability | Result |
|---|---|
| Native Blender / OpenSCAD / FreeCAD / MeshLab | absent |
| NVIDIA/CUDA | absent |
| APT/native binary download | blocked by the same egress policy encountered by the document system |
| PyPI | available |
| npm | available |
| GitHub source/API | available |
| Disk | sufficient for isolated runtimes, but dependencies must remain ignored |
| Practical CPU renderer | Blender Cycles |
| Practical exchange format | GLB (single-file glTF 2.0) |

### 1.1 Blender proof

The official Blender Foundation [`bpy`](https://pypi.org/project/bpy/) wheel is available for CPython 3.11. `bpy==4.5.12` downloads as a 373 MB wheel and occupies approximately 942 MB in an isolated virtual environment.

The Linux wheel expects desktop libraries that the sandbox omits (`libXrender`, `libXfixes`, `libXi`, `libxkbcommon`, `libSM`, `libICE`, `libGL`). A small original set of null ABI shims was built for **unused GUI/OpenGL symbols only**. This is safe only because workers enforce:

- Cycles CPU rendering;
- no EEVEE or viewport path;
- no interactive Blender GUI;
- fixed declarative operations;
- no untrusted `.blend` files or scripts.

Operational proof in the sandbox:

- `bpy 4.5.12 LTS` imported successfully;
- a multi-part upholstered chair was generated;
- bevel modifiers and PBR materials were applied;
- GLB export succeeded;
- four Cycles views rendered at 512×512;
- Khronos validation returned zero errors and zero warnings;
- topology QA returned zero errors after correctly welding glTF normal/UV seam vertices for analysis.

Blender officially supports background/UI-less operation, and its glTF exporter supports evaluated modifiers, PBR materials, normals, UVs, animation and +Y-up conversion. See the [Blender command-line manual](https://docs.blender.org/manual/en/dev/advanced/command_line/arguments.html), [scripting security guidance](https://docs.blender.org/manual/en/latest/advanced/scripting/security.html), and [glTF 2.0 manual](https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html).

### 1.2 Precision CAD proof

[`CadQuery 2.8.0`](https://pypi.org/project/cadquery/) and Open Cascade wheels also install from PyPI. A bracket with fillets, four countersunk mounting holes and a bored boss was built and exported successfully:

- `Shape.isValid() == True`;
- volume: `30,696.25 mm³`;
- bounding box: approximately `80 × 50 × 34 mm`;
- STEP and STL outputs were produced.

The complete CadQuery runtime occupied approximately 1.7 GB because current wheels pull VTK, CasADi, Numba/LLVM and visualization dependencies. This proves feasibility but is intentionally not in the default bootstrap yet. A later CAD milestone should provision an isolated, integrity-locked runtime and expose a fixed worker, analogous to Blender.

[`build123d`](https://pypi.org/project/build123d/) is an attractive modern alternative: Pythonic context managers over Open Cascade, Apache-2.0, and direct STEP/STL workflows. It should be benchmarked against CadQuery on the same precision cases before choosing the public CAD DSL.

## 2. Existing agent/skill ecosystem

### 2.1 Blender MCP projects

Representative projects inspected:

- [`ahujasid/blender-mcp`](https://github.com/ahujasid/blender-mcp) — popular live Blender bridge with scene inspection, screenshots, code execution and optional asset/generative services;
- [`sandraschi/blender-mcp`](https://github.com/sandraschi/blender-mcp) — broad headless/MCP tool surface and downstream game/VR workflows;
- [`djeada/blender-mcp-server`](https://github.com/djeada/blender-mcp-server) — structured object/material/render/export tools under MIT;
- [`minihellboy/claude-blender`](https://github.com/minihellboy/claude-blender) — visual feedback loop, local model hooks and project skills;
- [`jithinolickal/blender`](https://github.com/jithinolickal/blender) — Apache-2.0 agent skill emphasizing analyze → build → verify → iterate;
- [`OpenAEC skill package`](https://github.com/OpenAEC-Foundation/Blender-Bonsai-ifcOpenshell-Sverchok-Claude-Skill-Package) — Blender/BIM/IFC/Sverchok skill catalog.

Useful design lessons:

1. Scene introspection plus screenshots materially improves agent results.
2. Reusable primitive/material/lighting helpers reduce hallucinated Blender API calls.
3. Checkpoints and deterministic operations are more reliable than one large generated script.
4. Multi-view review is essential: a front view can hide intersections, missing backs and scale errors.
5. Broad “execute arbitrary Python” MCP tools are a serious production security boundary.

What is **not** adopted:

- no source is copied into this clean-room implementation;
- no unauthenticated TCP listener is opened;
- no arbitrary code from a prompt or model is executed;
- no implicit network access to Poly Haven, Sketchfab or model-generation services occurs;
- no untrusted Blender file is loaded with auto-execution.

Our initial headless pipeline does not need MCP: Arena can invoke deterministic `modelctl` operations directly. An MCP adapter can later wrap the same bounded functions without becoming the source of truth.

## 3. Tooling matrix

| Tool | Best use | Strengths | Limits here | Decision |
|---|---|---|---|---|
| Blender 4.5 LTS / `bpy` | general authored assets, materials, animation, rendering | mature geometry/modifiers, Cycles, glTF, huge ecosystem | large GPL runtime; no native desktop libs | **default quality backend; operational** |
| Trimesh 5 | mesh I/O, topology QA, portable primitives | MIT, small, excellent inspection/repair API | not a full DCC; no production renderer | **core inspection and fallback builder; operational** |
| Manifold3D | robust mesh booleans | fast, modern, Trimesh integration | mesh rather than exact CAD | **pinned for later CSG** |
| CadQuery | precise parametric CAD | STEP, STL, 3MF, Open Cascade BREP | 1.7 GB tested runtime | **feasible optional backend; proof passed** |
| build123d | modern parametric CAD | readable Python, Apache-2.0 | must benchmark and isolate | **candidate for CAD public API** |
| FreeCAD | full CAD/BIM GUI and Python | broad format/workbench support | no viable current binary path | defer |
| OpenSCAD | simple deterministic CSG | easy DSL, reproducible | no binary; weaker BREP/interchange | not primary |
| MeshLab / PyMeshLab | remesh/repair/filtering | mature mesh processing | large native wheel; narrower authoring role | evaluate for repair milestone |
| Khronos glTF Validator | standards conformance | official JSON/binary/accessor checks | glTF only | **mandatory GLB gate; operational** |
| glTF Transform | optimize/compress/inspect | deterministic dedup, prune, weld, simplify, Draco/Meshopt/KTX | compression support varies by consumer | **post-process route; operational** |
| Google `<model-viewer>` | interactive review | strong defaults, camera controls, web/AR | GLB/glTF-focused | **local viewer bundle; operational** |
| Three.js | custom web scenes/tools | flexible ecosystem | more code than needed for basic review | later annotation/editor UI |
| USD/OpenUSD | film/VFX/large scenes | composition, variants, references | more complex validation/runtime | later scene pipeline |
| IFC/IfcOpenShell | BIM | semantic building model | separate domain | later AEC skill |

The official Khronos validator reports structural and accessor issues in JSON. glTF Transform provides reproducible inspect/optimize commands. See [Khronos glTF resources](https://www.khronos.org/gltf/), [glTF Validator](https://github.com/KhronosGroup/glTF-Validator), and [glTF Transform](https://github.com/donmccurdy/glTF-Transform).

## 4. Generative 3D models and services

### 4.1 Self-hosted models

| Model | Input | Published hardware need | License note | Arena verdict |
|---|---|---:|---|---|
| TripoSR | single image | normally CUDA; commonly 6–8 GB VRAM | MIT | no GPU; not baseline |
| Stable Fast 3D | single image | consumer CUDA GPU | Stability community terms | no GPU; license review needed |
| Hunyuan3D 2.1 | image/multiview + texture | official repo: 10 GB shape, 21 GB texture, 29 GB combined | Tencent community license | impossible locally; terms need counsel |
| TRELLIS.2-4B | image to detailed PBR asset | official repo: NVIDIA GPU with at least 24 GB | MIT code/model, dependency review still required | impossible locally |

Primary references:

- [TripoSR official repository](https://github.com/VAST-AI-Research/TripoSR)
- [Hunyuan3D 2.1 official repository](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)
- [TRELLIS.2 official repository](https://github.com/microsoft/TRELLIS.2)

Even with suitable GPU infrastructure, these outputs are candidates, not final assets. Required post-processing includes orientation/scale, hole and self-intersection checks, decimation/retopology, UV/material inspection, silhouette comparison and licensing/provenance capture.

### 4.2 Hosted providers

Current serious API candidates:

- [Meshy API](https://docs.meshy.ai/en/api/text-to-3d): text/image/multiview, preview/refine, PBR, remesh, target polycount, GLB/OBJ/FBX/STL/USDZ/3MF;
- [Tripo API](https://developers.tripo3d.ai/en/docs/quick-start): asynchronous text/image generation, newer game-ready/low-poly variants, rig and retarget routes;
- Hyper3D/Rodin: text/image/multiview, quad/triangle tiers and PBR output; official provider documentation and current commercial terms must be captured before implementation.

Recommended provider design:

- provider-neutral request/response schema;
- environment-only credentials (`MESHY_API_KEY`, `TRIPO_API_KEY`, etc.); never chat, manifests or Git;
- explicit cost ceiling and timeout;
- immutable request manifest without secrets;
- downloaded GLB treated as untrusted;
- mandatory local validation and Blender re-render;
- model/provider/version/seed/license recorded in provenance;
- no provider declared “production quality” until benchmarked on our corpus.

Image-to-3D or multiview-to-3D should generally be preferred over pure text-to-3D for shape fidelity. The agent can first create/collect orthographic references, then reconstruct, validate and refine.

## 5. Target architecture

```text
natural-language request / reference images
                    │
                    ▼
       intent + target profile classifier
       (web / render / game / print / CAD / BIM)
                    │
                    ▼
       dimensional brief + model specification
                    │
       ┌────────────┼─────────────┐
       ▼            ▼             ▼
 Blender worker  CAD worker   provider adapter
 authored mesh   STEP/BREP    generated candidate
       └────────────┼─────────────┘
                    ▼
        normalize to GLB + optional native format
                    ▼
 security → Khronos → topology → budgets → materials
                    ▼
       Cycles multi-view render + interactive viewer
                    ▼
         agent visual critique and bounded iteration
                    ▼
       final asset + previews + QA + provenance
```

### Format policy

- **GLB:** canonical portable delivery and review format; single file prevents resource-path surprises.
- **STEP:** canonical precision CAD interchange.
- **STL:** geometry-only manufacturing derivative; units must be explicit in the manifest.
- **3MF:** preferred future print package when colors/materials/units matter.
- **BLEND:** optional editable authoring output only; never trusted as an automatic input.
- **FBX:** compatibility derivative, not canonical due weaker open validation.
- **USD/USDZ:** later scene/AR pipeline.

## 6. What “quality” means

A successful export is not a quality model. Independent gates are required:

1. **Prompt fidelity:** recognizable requested object, correct parts and omissions.
2. **Scale/proportions:** explicit units, plausible dimensions, correct origin/up-axis.
3. **Silhouette:** front/side/back/perspective all read correctly.
4. **Topology:** finite vertices, no zero-area triangles, no nonmanifold edges, intentional boundaries only.
5. **Manufacturing:** watertight positive volume and minimum-wall checks for print profiles.
6. **Materials:** named PBR materials, correct metallic/roughness behavior, texture color-space rules.
7. **UVs/textures:** no obvious stretching, seams or baked lighting where dynamic lighting is expected.
8. **Budgets:** target triangle count, texture size, draw calls and file size.
9. **Interoperability:** official glTF validation and import/render in a second tool.
10. **Editability:** meaningful object/material names and separable parts when requested.
11. **Visual presentation:** deliberate camera, light, background and no clipping.
12. **Provenance:** source prompt/references, generator/backend/version, hashes and license.

## 7. Security model

Every uploaded model is untrusted.

- Initial secure intake accepts single-file GLB only.
- Declared file length, chunk bounds, JSON size and collection counts are bounded.
- External buffer/image URIs are rejected.
- Network reads are disabled in validators and optimizers.
- `.blend` auto-execution, drivers, handlers and embedded Python are not accepted.
- Blender workers use fixed source-controlled code and validated JSON.
- Source models are never overwritten.
- Provider outputs pass the same local safety and QA gates.
- Texture decoders remain an attack surface; file and pixel limits plus updated dependencies are mandatory.
- Arbitrary Blender-Python MCP execution is excluded from the production route.

## 8. Implemented first milestone

The repository now includes:

- `modelctl 0.7.0`;
- declarative JSON Schema and semantic guards;
- Blender and Trimesh builders;
- isolated official Blender Python bootstrap;
- headless Cycles compatibility shims;
- GLB container safety checks;
- scene/topology/material/bounds inspection;
- Khronos validation;
- profile-aware QA (`web`, `render`, `print`);
- four-view Cycles render and contact sheet;
- glTF Transform optimization without source overwrite;
- self-contained local interactive viewer;
- tests, example model, benchmark definition and agent Skill.

## 9. Recommended implementation order

### Milestone A — deterministic asset platform (current)

- hard-surface/product/furniture primitives and assemblies;
- modifiers/material presets;
- GLB validation, rendering, viewer and regression tests.

### Milestone B — richer authored geometry

- curves, lathe/revolve, sweep, loft, text, arrays and mirror;
- bounded booleans through Manifold3D;
- Geometry Nodes templates;
- UV unwrap, baked normals/AO, texture ingestion;
- LOD generation and collision meshes;
- animation/rig validation.

### Milestone C — precision CAD

- compare CadQuery and build123d ergonomics and output quality;
- isolated locked Open Cascade worker;
- STEP + 3MF + dimension drawing outputs;
- hole/fillet/chamfer/shell/pattern operations;
- tolerance, wall-thickness and interference QA.

### Milestone D — provider-backed generative assets

- Meshy and Tripo adapters behind an allowlisted interface;
- image/multiview reference pipeline;
- provider benchmark by category;
- retopology/material cleanup and provenance.

### Milestone E — specialized domains

- AEC/BIM via IFC;
- characters, rigging and animation;
- game-engine import oracles;
- USD scenes and variants;
- Gaussian splats for capture/environment workflows.

## 10. Decision

Proceed with Blender + glTF as the general default, Trimesh/Khronos as independent QA, and an isolated Open Cascade backend for precision work. Treat neural text-to-3D as an optional candidate generator rather than the foundation. This is the only route that remains useful, testable and honest both in the current Arena sandbox and in a future GPU/cloud deployment.
