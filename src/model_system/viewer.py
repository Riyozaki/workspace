from __future__ import annotations

import html
import shutil
from pathlib import Path
from typing import Any

from .blender_runtime import repository_root
from .inspect import inspect_model
from .util import write_json


def create_viewer(model_path: str | Path, output_dir: str | Path, *, title: str | None = None) -> dict[str, Any]:
    source = Path(model_path).resolve()
    inspection = inspect_model(source)
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    module = repository_root() / "node_modules/@google/model-viewer/dist/model-viewer-module.min.js"
    if not module.is_file():
        raise RuntimeError("@google/model-viewer is unavailable; run npm ci")
    model_name = "model.glb"
    shutil.copy2(source, destination / model_name)
    shutil.copy2(module, destination / "model-viewer.min.js")
    heading = title or source.stem.replace("-", " ").title()
    scene = inspection["scene"]
    markup = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{html.escape(heading)}</title>
  <script type="module" src="model-viewer.min.js"></script>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    body {{ margin: 0; background: #0c1422; color: #eef3f8; display: grid; grid-template-rows: auto 1fr; min-height: 100vh; }}
    header {{ padding: 18px 24px; display: flex; gap: 24px; align-items: baseline; border-bottom: 1px solid #233248; }}
    h1 {{ margin: 0; font-size: 20px; }}
    .meta {{ color: #9eb0c5; font-size: 13px; }}
    model-viewer {{ width: 100%; height: calc(100vh - 68px); background: radial-gradient(circle at 50% 40%, #25364f, #0c1422 65%); }}
    .hint {{ position: fixed; right: 18px; bottom: 16px; background: #101b2dcc; border: 1px solid #334762; border-radius: 10px; padding: 9px 12px; font-size: 12px; color: #b7c6d8; }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(heading)}</h1>
    <span class="meta">{scene['triangles']:,} triangles · {scene['geometry_instances']} mesh instances · {source.stat().st_size / 1024:.1f} KiB</span>
  </header>
  <model-viewer src="{model_name}" camera-controls auto-rotate shadow-intensity="1" shadow-softness="0.8" exposure="1.1" interaction-prompt="auto" alt="Interactive 3D model"></model-viewer>
  <div class="hint">Drag to orbit · wheel/pinch to zoom · right-drag to pan</div>
</body>
</html>
"""
    index = destination / "index.html"
    index.write_text(markup, encoding="utf-8")
    write_json(destination / "inspection.json", inspection)
    return {
        "input": str(source),
        "output_dir": str(destination),
        "index": str(index),
        "model": str(destination / model_name),
        "inspection": str(destination / "inspection.json"),
    }
