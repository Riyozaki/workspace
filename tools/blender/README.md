# Restricted Blender worker

`model_worker.py` is the only production entry into the isolated Blender Python runtime. It accepts validated declarative JSON or a safety-checked GLB path and exposes fixed `build` and `render` commands.

It never executes prompt text, uploaded scripts, `.blend` drivers, handlers, add-ons, or arbitrary Python. Blender auto-execution is disabled before every operation.

Because this worker imports Blender's GPL `bpy` module, it is licensed separately under `GPL-3.0-or-later`. The main orchestration communicates with it only through subprocess files/JSON and does not import `bpy`.
