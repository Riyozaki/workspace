from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
import trimesh

from model_system.blender_runtime import find_blender_python, find_gltf_transform
from model_system.build import build_model, build_model_from_file
from model_system.cli import main as modelctl_main
from model_system.errors import UnsafeModelError
from model_system.gltf_validator import find_gltf_validator
from model_system.inspect import inspect_model
from model_system.optimize import optimize_model
from model_system.render import render_model
from model_system.security import inspect_glb_container
from model_system.spec import validate_model_spec
from model_system.validate import validate_model
from model_system.viewer import create_viewer


@pytest.fixture
def simple_model_spec():
    return {
        "version": "1.0",
        "materials": [
            {"id": "blue", "name": "Anodized blue", "base_color": "#2866A5", "metallic": 0.6, "roughness": 0.25}
        ],
        "objects": [
            {
                "id": "body",
                "type": "box",
                "size": [1.0, 0.7, 0.4],
                "material": "blue",
                "location": [0, 0, 0.2],
            },
            {
                "id": "dial",
                "type": "cylinder",
                "radius": 0.14,
                "depth": 0.12,
                "segments": 32,
                "material": "blue",
                "location": [0, -0.36, 0.2],
                "rotation_deg": [90, 0, 0],
            },
        ],
    }


def test_spec_semantic_guards(simple_model_spec):
    validate_model_spec(simple_model_spec)
    duplicate = json.loads(json.dumps(simple_model_spec))
    duplicate["objects"].append(dict(duplicate["objects"][0]))
    with pytest.raises(ValueError, match="unique"):
        validate_model_spec(duplicate)
    unknown = json.loads(json.dumps(simple_model_spec))
    unknown["objects"][0]["material"] = "missing"
    with pytest.raises(ValueError, match="unknown material"):
        validate_model_spec(unknown)


def test_portable_build_inspect_and_validate(tmp_path, simple_model_spec):
    output = tmp_path / "model.glb"
    result = build_model(simple_model_spec, output, backend="trimesh")
    assert result["backend"] == "trimesh"
    assert output.is_file()
    inspection = inspect_model(output)
    assert inspection["scene"]["geometry_instances"] == 2
    assert inspection["scene"]["triangles"] > 0
    assert inspection["scene"]["material_count"] == 1
    report = validate_model(output, require_gltf_validator=find_gltf_validator() is not None)
    assert report["passed"] is True, report["issues"]


def test_modelctl_create_inspect_validate_routes(tmp_path, simple_model_spec, capsys):
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(simple_model_spec), encoding="utf-8")
    model = tmp_path / "asset.glb"
    report = tmp_path / "create.json"
    assert modelctl_main(["create", str(spec_path), str(model), "--backend", "trimesh", "-o", str(report)]) == 0
    assert json.loads(report.read_text())["passed"] is True
    assert modelctl_main(["inspect", str(model)]) == 0
    assert '"geometry_instances": 2' in capsys.readouterr().out
    assert modelctl_main(["validate", str(model), "--strict"]) == 0


def test_glb_external_resource_is_rejected(tmp_path):
    document = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": 4, "uri": "../../escape.bin"}],
        "scenes": [{"nodes": []}],
        "scene": 0,
    }
    payload = json.dumps(document, separators=(",", ":")).encode()
    payload += b" " * ((4 - len(payload) % 4) % 4)
    length = 12 + 8 + len(payload)
    path = tmp_path / "external.glb"
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, length) + struct.pack("<I4s", len(payload), b"JSON") + payload)
    with pytest.raises(UnsafeModelError, match="external resources"):
        inspect_glb_container(path)


def test_print_profile_rejects_an_open_surface(tmp_path):
    mesh = trimesh.Trimesh(vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces=[[0, 1, 2]], process=False)
    mesh.visual = trimesh.visual.TextureVisuals(
        material=trimesh.visual.material.PBRMaterial(name="Sheet", baseColorFactor=[120, 140, 160, 255])
    )
    scene = trimesh.Scene(mesh)
    path = tmp_path / "sheet.glb"
    path.write_bytes(scene.export(file_type="glb"))
    report = validate_model(path, profile="print", require_gltf_validator=find_gltf_validator() is not None)
    assert report["passed"] is False
    assert any(item["code"] == "not-watertight" for item in report["issues"])


def test_viewer_bundle_is_local_and_self_contained(tmp_path, simple_model_spec):
    if find_gltf_validator() is None:
        pytest.skip("npm runtime is unavailable")
    model = tmp_path / "model.glb"
    build_model(simple_model_spec, model, backend="trimesh")
    result = create_viewer(model, tmp_path / "viewer", title="QA asset")
    markup = Path(result["index"]).read_text(encoding="utf-8")
    assert "model-viewer.min.js" in markup
    assert "https://" not in markup
    assert (tmp_path / "viewer/model.glb").is_file()
    assert (tmp_path / "viewer/model-viewer.min.js").is_file()


@pytest.mark.integration
def test_gltf_transform_produces_valid_separate_output(tmp_path, simple_model_spec):
    if find_gltf_transform() is None or find_gltf_validator() is None:
        pytest.skip("glTF JavaScript runtime is unavailable")
    source = tmp_path / "source.glb"
    output = tmp_path / "optimized.glb"
    build_model(simple_model_spec, source, backend="trimesh")
    report = optimize_model(source, output, compression="none")
    assert output.is_file()
    assert report["validation"]["errors"] == 0
    assert source.read_bytes() != b""


@pytest.mark.integration
def test_blender_build_render_and_khronos_validation(tmp_path):
    if find_blender_python() is None or find_gltf_validator() is None:
        pytest.skip("Blender modeling runtime is unavailable")
    spec_path = Path(__file__).resolve().parents[1] / "examples/modeling/lounge-chair.json"
    model = tmp_path / "chair.glb"
    build = build_model_from_file(spec_path, model, backend="blender", timeout=300)
    assert build["backend"] == "blender-python"
    qa = validate_model(model, max_triangles=100_000)
    assert qa["passed"] is True, qa["issues"]
    render = render_model(
        model,
        tmp_path / "render",
        resolution=256,
        samples=4,
        views=["perspective", "right"],
        timeout=300,
    )
    assert not render["summary"]["blank_views"]
    assert Path(render["contact_sheet"]).is_file()
