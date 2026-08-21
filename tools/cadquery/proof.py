#!/usr/bin/env python3
"""Research proof for the optional CadQuery/Open Cascade precision lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cadquery as cq


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    part = (
        cq.Workplane("XY")
        .box(80, 50, 6)
        .edges("|Z")
        .fillet(4)
        .faces(">Z")
        .workplane()
        .rect(62, 32, forConstruction=True)
        .vertices()
        .cskHole(5, 9, 82)
        .faces(">Z")
        .workplane()
        .circle(12)
        .extrude(28)
        .faces(">Z")
        .hole(14)
    )
    step = args.output_dir / "bracket.step"
    stl = args.output_dir / "bracket.stl"
    cq.exporters.export(part, str(step))
    cq.exporters.export(part, str(stl), tolerance=0.05, angularTolerance=0.1)
    shape = part.val()
    bounds = shape.BoundingBox()
    print(
        json.dumps(
            {
                "valid": shape.isValid(),
                "volume_mm3": shape.Volume(),
                "surface_area_mm2": shape.Area(),
                "bounds_mm": [bounds.xlen, bounds.ylen, bounds.zlen],
                "step": str(step),
                "stl": str(stl),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
