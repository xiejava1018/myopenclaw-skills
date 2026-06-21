import importlib
import xml.etree.ElementTree as ET
render = importlib.import_module("render_drawio")


def _geom():
    return {
        "type": "architecture", "title": "T", "style": "enterprise",
        "canvas": {"width": 600, "height": 300},
        "nodes": [{"id": "a", "label": "Web", "kind": "client",
                   "x": 60, "y": 60, "width": 140, "height": 80}],
        "edges": [{"source": "a", "target": "a", "label": "loop",
                   "flow": "feedback", "points": [[130, 140], [130, 300]]}],
        "containers": [], "decorations": [],
    }


def test_render_produces_valid_xml():
    xml = render.render(_geom())
    root = ET.fromstring(xml)  # raises if invalid
    assert root.tag == "mxfile"


def test_render_contains_node_cell():
    xml = render.render(_geom())
    root = ET.fromstring(xml)
    cells = list(root.iter("mxCell"))
    values = [c.get("value") for c in cells]
    assert "Web" in values


def test_render_canvas_size_set():
    xml = render.render(_geom())
    root = ET.fromstring(xml)
    model = root.find(".//mxGraphModel")
    assert model.get("pageWidth") == "600"
    assert model.get("pageHeight") == "300"


def test_render_edge_uses_orthogonal_style():
    xml = render.render(_geom())
    assert "edgeStyle=orthogonalEdgeStyle" in xml


def test_render_uses_kind_shape_mapping():
    geom = _geom()
    geom["nodes"][0]["kind"] = "database"
    xml = render.render(geom)
    assert "shape=cylinder3" in xml


def test_render_emits_container_with_dashed_style():
    geom = _geom()
    geom["containers"] = [{"id": "L0", "label": "Frontend", "x": 50, "y": 50,
                            "width": 380, "height": 100}]
    xml = render.render(geom)
    assert "dashed=1" in xml
    assert "Frontend" in xml


def test_render_background_color_set_per_style():
    geom = _geom()
    geom["style"] = "claude"
    xml = render.render(geom)
    model = ET.fromstring(xml).find(".//mxGraphModel")
    assert model.get("background") == "#f8f6f3"
