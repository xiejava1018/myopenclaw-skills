import importlib
import json
cli = importlib.import_module("cli")


ARCH_JSON = {
    "type": "architecture", "style": "enterprise", "title": "Demo", "direction": "tb",
    "layers": [
        {"id": "L0", "label": "客户端", "nodes": ["web", "gw"]},
        {"id": "L1", "label": "存储", "nodes": ["db"]},
    ],
    "nodes": [
        {"id": "web", "label": "Web", "kind": "client"},
        {"id": "gw", "label": "Gateway", "kind": "api"},
        {"id": "db", "label": "Postgres", "kind": "database"},
    ],
    "edges": [
        {"source": "web", "target": "gw", "flow": "data"},
        {"source": "gw", "target": "db", "flow": "data"},
    ],
}


def test_build_writes_drawio_and_png(tmp_path, monkeypatch):
    import export
    written = {}
    def fake_export(drawio_path, out_path, **kw):
        written["png"] = out_path
        with open(out_path, "w") as f:
            f.write("PNG")
    monkeypatch.setattr(export, "export_image", fake_export)

    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(ARCH_JSON), encoding="utf-8")
    out = tmp_path / "out"

    rc = cli.main(["build", str(inp), "-o", str(out)])
    assert rc == 0
    assert (tmp_path / "out.drawio").exists()
    assert (tmp_path / "out.png").exists()


def test_build_invalid_schema_exits_nonzero(tmp_path):
    inp = tmp_path / "bad.json"
    inp.write_text(json.dumps({"type": "bogus"}), encoding="utf-8")
    rc = cli.main(["build", str(inp), "-o", str(tmp_path / "out")])
    assert rc != 0


def test_build_layout_error_exits_nonzero(tmp_path, monkeypatch):
    import layout
    def broken_layout(d): raise layout.LayoutError("boom")
    monkeypatch.setattr(layout, "layout", broken_layout)
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(ARCH_JSON), encoding="utf-8")
    rc = cli.main(["build", str(inp), "-o", str(tmp_path / "out")])
    assert rc != 0


def test_build_export_error_doesnt_kill_drawio(tmp_path, monkeypatch):
    """If the drawio CLI is missing/misbehaving, the .drawio source is still
    useful to the user — they can open it in the draw.io app and export
    themselves. So we write the .drawio regardless and exit non-zero only
    if the user wanted the rendered image."""
    import export
    def broken_export(*a, **kw): raise export.ExportError("no drawio")
    monkeypatch.setattr(export, "export_image", broken_export)
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(ARCH_JSON), encoding="utf-8")
    rc = cli.main(["build", str(inp), "-o", str(tmp_path / "out")])
    # The .drawio should exist (we got the source out the door)
    assert (tmp_path / "out.drawio").exists()
    # The png should NOT exist
    assert not (tmp_path / "out.png").exists()
    # Non-zero exit because the image export failed
    assert rc != 0


def test_build_supports_svg_format(tmp_path, monkeypatch):
    import export
    captured = {}
    def fake_export(drawio_path, out_path, fmt="png", **kw):
        captured["fmt"] = fmt
        with open(out_path, "w") as f: f.write("SVG")
    monkeypatch.setattr(export, "export_image", fake_export)
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(ARCH_JSON), encoding="utf-8")
    cli.main(["build", str(inp), "-o", str(tmp_path / "out"), "-f", "svg"])
    assert captured["fmt"] == "svg"
    assert (tmp_path / "out.svg").exists()
