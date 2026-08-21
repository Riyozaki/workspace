# Headless 3D runtime compatibility shims

The official Linux `bpy` and Open Cascade wheels dynamically link a small GUI/OpenGL surface even when the requested workload is CPU-only and headless. The Arena runtime has no APT access and omits those desktop libraries.

This directory builds **null compatibility shims** for the unresolved GUI symbols. They contain no renderer and are safe only under these enforced conditions:

- Blender uses Cycles on CPU; EEVEE, viewport rendering, and interactive GUI paths are forbidden.
- Open Cascade is used for nonvisual BREP construction/export only; VTK/OpenGL visualization is forbidden.
- Workers run as isolated subprocesses and receive declarative JSON, never arbitrary code or untrusted `.blend` files.
- If real system libraries are available, production deployments should use those instead.

The shims are original trivial ABI adapters, not copied implementations. Calling a GUI/OpenGL code path against them is unsupported and may crash; runtime adapters therefore select only tested non-GUI operations. `scripts/bootstrap-modeling.sh` builds them into the ignored `.cache/model-runtime/headless-libs` directory.
