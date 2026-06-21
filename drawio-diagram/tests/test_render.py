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


def test_render_lifeline_decoration_is_dashed_free_edge():
    geom = _geom()
    geom["decorations"] = [
        {"kind": "lifeline", "x": 130, "y": 140, "width": 0,
         "height": 160, "label": "a"}
    ]
    xml = render.render(geom)
    root = ET.fromstring(xml)
    # a lifeline renders as an edge (not a vertex) with no arrowheads
    edge_cells = [c for c in root.iter("mxCell") if c.get("edge") == "1"
                  and "lifeline" in c.get("id", "")]
    assert edge_cells, "lifeline must render as a free edge"
    style = edge_cells[0].get("style", "")
    assert "dashed=1" in style
    assert "endArrow=none" in style
    # free edge: no source/target vertex attrs
    assert "source" not in edge_cells[0].attrib
    assert "target" not in edge_cells[0].attrib


def test_render_frame_decoration_is_labeled_rect():
    geom = _geom()
    geom["decorations"] = [
        {"kind": "frame", "x": 50, "y": 50, "width": 300, "height": 120,
         "label": "retry", "frame_kind": "loop"}
    ]
    xml = render.render(geom)
    root = ET.fromstring(xml)
    frame_cells = [c for c in root.iter("mxCell") if c.get("id", "").startswith("frame_")]
    assert frame_cells, "frame must render as a vertex cell"
    value = frame_cells[0].get("value", "")
    assert "loop" in value and "retry" in value
    assert "verticalAlign=top" in frame_cells[0].get("style", "")


def test_render_free_edge_has_no_source_target():
    geom = _geom()
    # a sequence-style free message edge: no source/target, only points
    geom["edges"] = [{"label": "ping", "flow": "data", "free": True,
                      "points": [[60, 200], [300, 200]]}]
    xml = render.render(geom)
    root = ET.fromstring(xml)
    edge_cells = [c for c in root.iter("mxCell") if c.get("edge") == "1"]
    assert edge_cells
    # the free edge carries no source/target vertex linkage
    assert "source" not in edge_cells[0].attrib
    assert "target" not in edge_cells[0].attrib
    assert edge_cells[0].get("value") == "ping"
