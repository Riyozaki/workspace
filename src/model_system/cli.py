from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .build import build_model_from_file
from .doctor import doctor
from .inspect import inspect_model
from .optimize import optimize_model
from .render import render_model
from .spec import validate_model_spec
from .util import read_json, write_json
from .validate import validate_model
from .viewer import create_viewer


def _emit(value: Any, output: str | Path | None = None) -> None:
    if output:
        write_json(output, value)
        print(output)
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="modelctl", description="Deterministic agent-oriented 3D asset pipeline")
    parser.add_argument("--version", action="version", version="modelctl 0.7.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Report 3D runtime capabilities")
    doctor_parser.add_argument("--self-test", action="store_true")
    doctor_parser.add_argument("-o", "--output")

    spec_parser = subparsers.add_parser("spec-validate", help="Validate a declarative model specification")
    spec_parser.add_argument("spec")

    create = subparsers.add_parser("create", help="Build and validate a model from JSON")
    create.add_argument("spec")
    create.add_argument("output")
    create.add_argument("--backend", choices=("auto", "blender", "trimesh"), default="auto")
    create.add_argument("--profile", choices=("web", "render", "print"), default=None)
    create.add_argument("--max-triangles", type=int, default=None)
    create.add_argument("--render", action="store_true")
    create.add_argument("--render-dir")
    create.add_argument("--timeout", type=int, default=900)
    create.add_argument("-o", "--report")

    inspect = subparsers.add_parser("inspect", help="Inspect GLB scene and mesh topology")
    inspect.add_argument("model")
    inspect.add_argument("-o", "--output")

    validate = subparsers.add_parser("validate", help="Run container, Khronos, topology, and profile QA")
    validate.add_argument("model")
    validate.add_argument("--profile", choices=("web", "render", "print"), default="render")
    validate.add_argument("--max-triangles", type=int, default=1_000_000)
    validate.add_argument("--allow-no-materials", action="store_true")
    validate.add_argument("--allow-missing-gltf-validator", action="store_true")
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("-o", "--output")

    render = subparsers.add_parser("render", help="Render multi-view Cycles QA images")
    render.add_argument("model")
    render.add_argument("-o", "--output-dir", required=True)
    render.add_argument("--resolution", type=int, default=512)
    render.add_argument("--samples", type=int, default=24)
    render.add_argument("--views", nargs="+", choices=("perspective", "front", "right", "back", "left", "top"))
    render.add_argument("--background", default="#162333")
    render.add_argument("--transparent", action="store_true")
    render.add_argument("--timeout", type=int, default=900)

    optimize = subparsers.add_parser("optimize", help="Create a separate optimized GLB")
    optimize.add_argument("model")
    optimize.add_argument("output")
    optimize.add_argument("--compression", choices=("none", "meshopt", "draco"), default="none")
    optimize.add_argument("--texture-size", type=int, default=2048)
    optimize.add_argument("--simplify-ratio", type=float)
    optimize.add_argument("--timeout", type=int, default=600)
    optimize.add_argument("-o", "--report")

    viewer = subparsers.add_parser("viewer", help="Create a self-contained interactive web viewer")
    viewer.add_argument("model")
    viewer.add_argument("-o", "--output-dir", required=True)
    viewer.add_argument("--title")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "doctor":
            _emit(doctor(self_test=args.self_test), args.output)
            return 0
        if args.command == "spec-validate":
            spec = read_json(args.spec)
            validate_model_spec(spec)
            _emit({"path": str(Path(args.spec).resolve()), "valid": True})
            return 0
        if args.command == "create":
            spec = read_json(args.spec)
            quality = spec.get("quality", {})
            profile = args.profile or quality.get("profile", "render")
            max_triangles = args.max_triangles or quality.get("max_triangles", 1_000_000)
            build = build_model_from_file(args.spec, args.output, backend=args.backend, timeout=args.timeout)
            validation = validate_model(
                args.output,
                profile=profile,
                max_triangles=max_triangles,
                require_materials=quality.get("require_materials", True),
            )
            render_report = None
            if args.render:
                settings = spec.get("render", {})
                render_report = render_model(
                    args.output,
                    args.render_dir or str(Path(args.output).with_suffix("")) + "-render",
                    resolution=settings.get("resolution", 512),
                    samples=settings.get("samples", 24),
                    views=settings.get("views"),
                    background=settings.get("background", "#162333"),
                    transparent=settings.get("transparent", False),
                    timeout=args.timeout,
                )
            report = {"passed": validation["passed"], "build": build, "validation": validation, "render": render_report}
            _emit(report, args.report)
            return 0 if report["passed"] else 1
        if args.command == "inspect":
            _emit(inspect_model(args.model), args.output)
            return 0
        if args.command == "validate":
            report = validate_model(
                args.model,
                output_report=args.output,
                profile=args.profile,
                max_triangles=args.max_triangles,
                require_materials=not args.allow_no_materials,
                require_gltf_validator=not args.allow_missing_gltf_validator,
                strict=args.strict,
            )
            if args.output:
                print(args.output)
            else:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["passed"] else 1
        if args.command == "render":
            _emit(
                render_model(
                    args.model,
                    args.output_dir,
                    resolution=args.resolution,
                    samples=args.samples,
                    views=args.views,
                    background=args.background,
                    transparent=args.transparent,
                    timeout=args.timeout,
                )
            )
            return 0
        if args.command == "optimize":
            _emit(
                optimize_model(
                    args.model,
                    args.output,
                    compression=args.compression,
                    texture_size=args.texture_size,
                    simplify_ratio=args.simplify_ratio,
                    timeout=args.timeout,
                ),
                args.report,
            )
            return 0
        if args.command == "viewer":
            _emit(create_viewer(args.model, args.output_dir, title=args.title))
            return 0
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
