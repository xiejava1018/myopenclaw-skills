"""Unified CLI entry point: check / build."""
import argparse
import json
import sys

import export
import layout
import render_drawio
import schema


def cmd_check(_args) -> int:
    status = export.check_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    if not status["available"]:
        print(status["install_hint"], file=sys.stderr)
        return 1
    return 0


def cmd_build(args) -> int:
    # 1. Load + validate
    try:
        with open(args.input, encoding="utf-8") as f:
            diagram = json.load(f)
        schema.validate(diagram)
    except FileNotFoundError:
        print(f"file not found: {args.input}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"invalid JSON: {e}", file=sys.stderr)
        return 2
    except schema.SchemaError as e:
        print(f"schema error: {e}", file=sys.stderr)
        return 2

    # 2. Layout
    try:
        geom = layout.layout(diagram)
    except layout.LayoutError as e:
        print(f"layout error: {e}", file=sys.stderr)
        return 3

    # 3. Render .drawio (always, even if image export later fails)
    xml = render_drawio.render(geom)
    drawio_path = f"{args.output}.drawio"
    with open(drawio_path, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"wrote {drawio_path}")

    # 4. Export image (best-effort; .drawio is the source of truth)
    img_path = f"{args.output}.{args.format}"
    try:
        export.export_image(drawio_path, img_path, fmt=args.format,
                            scale=args.scale, border=args.border)
        print(f"wrote {img_path}")
        return 0
    except export.ExportError as e:
        print(f"export error: {e}", file=sys.stderr)
        print(f".drawio source still written: {drawio_path}", file=sys.stderr)
        return 4


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="drawio-diagram")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="verify draw.io CLI is available")
    p_build = sub.add_parser("build", help="build .drawio + rendered image from diagram.json")
    p_build.add_argument("input", help="path to diagram.json")
    p_build.add_argument("-o", "--output", required=True,
                         help="output basename without extension (e.g. -o out -> out.drawio + out.png)")
    p_build.add_argument("-f", "--format", default="png",
                         choices=["png", "svg", "pdf", "jpg"],
                         help="rendered image format (default: png)")
    p_build.add_argument("--scale", type=int, default=2,
                         help="image scale (higher = sharper; default: 2)")
    p_build.add_argument("--border", type=int, default=20,
                         help="border around diagram in pixels (default: 20)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        # argparse calls sys.exit on parse errors; convert to return code
        # so callers (and tests) can inspect the outcome without try/except.
        return e.code if isinstance(e.code, int) else 2
    if args.command == "check":
        return cmd_check(args)
    if args.command == "build":
        return cmd_build(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
