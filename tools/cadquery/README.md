# Optional CadQuery research proof

This is not yet part of the default `modelctl` runtime. It records the exact precision-CAD smoke test described in the 2026-08-21 research report.

Tested environment:

- `cadquery==2.8.0`;
- official Open Cascade wheel pulled by CadQuery;
- CPython 3.11;
- the same headless null GUI/OpenGL shims used by the Blender worker;
- nonvisual STEP/STL export only.

The proof creates an 80×50 mm filleted bracket with four countersunk holes and a bored boss, then reports BREP validity, volume, area and bounds.

Before making this a product route, pin and hash the large isolated dependency graph, compare its authoring API with build123d, add STEP inspection, and implement tolerance/manufacturing QA. Do not expose arbitrary CadQuery Python execution from prompts.
