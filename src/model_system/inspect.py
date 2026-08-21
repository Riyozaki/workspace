from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from .security import inspect_glb_container
from .util import sha256_file


def _mesh_metrics(name: str, mesh: trimesh.Trimesh) -> dict[str, Any]:
    source_vertices = np.asarray(mesh.vertices)
    finite = bool(np.isfinite(source_vertices).all())
    # glTF splits vertices at hard-normal and UV seams. Merge position-equivalent
    # vertices on a copy before topology checks, otherwise every bevel seam is
    # falsely reported as an open boundary.
    topology = mesh.copy()
    topology.merge_vertices(merge_tex=True, merge_norm=True)
    vertices = np.asarray(topology.vertices)
    faces = np.asarray(topology.faces)
    if len(faces):
        triangles = vertices[faces]
        twice_area = np.linalg.norm(
            np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]),
            axis=1,
        )
        degenerate = int(np.count_nonzero(twice_area <= 1e-14))
        edges = np.sort(
            np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=0),
            axis=1,
        )
        _unique, counts = np.unique(edges, axis=0, return_counts=True)
        boundary_edges = int(np.count_nonzero(counts == 1))
        nonmanifold_edges = int(np.count_nonzero(counts > 2))
    else:
        degenerate = boundary_edges = nonmanifold_edges = 0
    material = getattr(getattr(mesh.visual, "material", None), "name", None)
    bounds = np.asarray(mesh.bounds) if len(vertices) else np.zeros((2, 3))
    return {
        "name": name,
        "vertices": int(len(source_vertices)),
        "topology_vertices": int(len(vertices)),
        "triangles": int(len(faces)),
        "finite_vertices": finite,
        "degenerate_triangles": degenerate,
        "boundary_edges": boundary_edges,
        "nonmanifold_edges": nonmanifold_edges,
        "watertight": bool(topology.is_watertight),
        "winding_consistent": bool(topology.is_winding_consistent),
        "is_volume": bool(topology.is_volume),
        "volume_m3": float(abs(topology.volume)) if topology.is_watertight else None,
        "surface_area_m2": float(topology.area),
        "bounds_m": bounds.tolist(),
        "extents_m": (bounds[1] - bounds[0]).tolist(),
        "material": material,
    }


def inspect_model(path: str | Path) -> dict[str, Any]:
    source = Path(path).resolve()
    if source.suffix.lower() != ".glb":
        raise ValueError("Initial secure inspection supports single-file .glb assets only")
    container = inspect_glb_container(source)
    scene = trimesh.load_scene(source, process=False)
    geometries: list[dict[str, Any]] = []
    overall_min: np.ndarray | None = None
    overall_max: np.ndarray | None = None
    for node_name in sorted(scene.graph.nodes_geometry):
        transform, geometry_name = scene.graph.get(node_name)
        mesh = scene.geometry[geometry_name].copy()
        mesh.apply_transform(transform)
        metrics = _mesh_metrics(str(node_name), mesh)
        metrics["geometry"] = str(geometry_name)
        geometries.append(metrics)
        bounds = np.asarray(metrics["bounds_m"])
        overall_min = bounds[0] if overall_min is None else np.minimum(overall_min, bounds[0])
        overall_max = bounds[1] if overall_max is None else np.maximum(overall_max, bounds[1])
    total_vertices = sum(item["vertices"] for item in geometries)
    total_triangles = sum(item["triangles"] for item in geometries)
    material_names = sorted({item["material"] for item in geometries if item["material"]})
    bounds = None if overall_min is None else [overall_min.tolist(), overall_max.tolist()]
    return {
        "path": str(source),
        "sha256": sha256_file(source),
        "bytes": source.stat().st_size,
        "format": "glb",
        "units": "m",
        "container": container,
        "scene": {
            "nodes": len(scene.graph.nodes),
            "geometry_instances": len(geometries),
            "unique_geometries": len(scene.geometry),
            "vertices": total_vertices,
            "triangles": total_triangles,
            "materials": material_names,
            "material_count": len(material_names),
            "bounds_m": bounds,
            "extents_m": None if bounds is None else (overall_max - overall_min).tolist(),
        },
        "geometries": geometries,
    }
