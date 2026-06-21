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


def test_render_er_entity_is_3compartment_html_label():
    geom = _geom()
    geom["type"] = "er"
    geom["nodes"] = [{
        "id": "user", "label": "User", "kind": "er_entity",
        "x": 60, "y": 60, "width": 160, "height": 120,
        "attributes": [
            {"name": "id", "pk": True},
            {"name": "email"},
            {"name": "org_id", "fk": True},
        ],
    }]
    xml = render.render(geom)
    root = ET.fromstring(xml)
    cell = next(c for c in root.iter("mxCell") if c.get("id") == "user")
    value = cell.get("value", "")
    # parsed value un-escapes the XML entities, so HTML tags are literal here
    assert "<b>User</b>" in value
    assert "<hr" in value
    # PK underlined, FK italic, plain attribute plain
    assert "<u>id</u>" in value
    assert "email" in value
    assert "<i>org_id</i>" in value
    # entity renders as a rect (not a cylinder), html label enabled
    style = cell.get("style", "")
    assert "rounded=0" in style
    assert "html=1" in style


def test_render_er_entity_label_escapes_special_chars():
    geom = _geom()
    geom["type"] = "er"
    geom["nodes"] = [{
        "id": "e", "label": "A<B>", "kind": "er_entity",
        "x": 60, "y": 60, "width": 140, "height": 80,
        "attributes": [{"name": "x"}],
    }]
    xml = render.render(geom)
    root = ET.fromstring(xml)
    cell = next(c for c in root.iter("mxCell") if c.get("id") == "e")
    # parsed value keeps the escaped entity text distinct from HTML markup
    assert "<b>A&lt;B&gt;</b>" in cell.get("value", "")


def test_render_initial_pseudostate_is_filled_black_disc():
    geom = _geom()
    geom["decorations"] = [
        {"kind": "initial_pseudostate", "x": 20, "y": 90,
         "width": 20, "height": 20, "label": ""}
    ]
    xml = render.render(geom)
    root = ET.fromstring(xml)
    cells = [c for c in root.iter("mxCell")
             if c.get("id", "").startswith("init_")]
    assert cells, "initial pseudo-state must render as a vertex cell"
    style = cells[0].get("style", "")
    assert "ellipse" in style
    assert "fillColor=#000000" in style


def test_render_final_pseudostate_is_bullseye_two_cells():
    geom = _geom()
    geom["decorations"] = [
        {"kind": "final_pseudostate", "x": 500, "y": 88,
         "width": 24, "height": 24, "label": ""}
    ]
    xml = render.render(geom)
    root = ET.fromstring(xml)
    outer = [c for c in root.iter("mxCell")
             if c.get("id", "").startswith("final_outer_")]
    inner = [c for c in root.iter("mxCell")
             if c.get("id", "").startswith("final_inner_")]
    assert outer and inner, "final pseudo-state must render as ring + disc"
    outer_style = outer[0].get("style", "")
    inner_style = inner[0].get("style", "")
    # outer is a hollow ring (white fill, thick black stroke)
    assert "ellipse" in outer_style
    assert "fillColor=#ffffff" in outer_style
    assert "strokeWidth=3" in outer_style
    # inner is a filled black disc
    assert "fillColor=#000000" in inner_style
    # inner disc is smaller than the outer ring
    def _w(c):
        return int(c.find("mxGeometry").get("width"))
    assert _w(inner[0]) < _w(outer[0])


# --- cloud icon rendering ---

def test_render_cloud_node_uses_provider_stencil():
    geom = _geom()
    geom["nodes"] = [{
        "id": "s3", "label": "Amazon S3", "kind": "external",
        "provider": "aws", "service": "s3",
        "x": 60, "y": 60, "width": 80, "height": 80,
    }]
    xml = render.render(geom)
    assert "mxgraph.aws4.s3" in xml


def test_render_cloud_node_azure_namespace():
    geom = _geom()
    geom["nodes"] = [{
        "id": "f", "label": "Func", "kind": "service",
        "provider": "azure", "service": "function_apps",
        "x": 60, "y": 60, "width": 80, "height": 80,
    }]
    xml = render.render(geom)
    assert "mxgraph.azure.function_apps" in xml


def test_render_node_without_provider_uses_kind_shape():
    # a plain database node must still use the cylinder shape, not a cloud glyph
    geom = _geom()
    geom["nodes"] = [{"id": "d", "label": "DB", "kind": "database",
                      "x": 60, "y": 60, "width": 140, "height": 80}]
    xml = render.render(geom)
    assert "shape=cylinder3" in xml
    assert "mxgraph." not in xml


# --- legend for multi-flow diagrams ---

def test_legend_omitted_when_single_flow():
    geom = _geom()
    geom["edges"] = [{"source": "a", "target": "a", "label": "x",
                      "flow": "data", "points": [[130, 140], [130, 300]]}]
    xml = render.render(geom)
    assert "legend_" not in xml  # no legend cell


def test_legend_omitted_when_all_edges_share_flow():
    geom = _geom()
    geom["edges"] = [
        {"source": "a", "target": "a", "flow": "control",
         "points": [[130, 140], [130, 200]]},
        {"source": "a", "target": "a", "flow": "control",
         "points": [[130, 200], [130, 300]]},
    ]
    xml = render.render(geom)
    assert "legend_" not in xml


def test_legend_present_when_two_distinct_flows():
    geom = _geom()
    geom["edges"] = [
        {"source": "a", "target": "a", "flow": "data",
         "points": [[130, 140], [130, 200]]},
        {"source": "a", "target": "a", "flow": "control",
         "points": [[130, 200], [130, 300]]},
    ]
    xml = render.render(geom)
    assert "legend_" in xml


def test_legend_lists_each_flow_name():
    geom = _geom()
    geom["edges"] = [
        {"source": "a", "target": "a", "flow": "data",
         "points": [[130, 140], [130, 200]]},
        {"source": "a", "target": "a", "flow": "async",
         "points": [[130, 200], [130, 300]]},
    ]
    xml = render.render(geom)
    assert "data" in xml
    assert "async" in xml


def test_legend_includes_flow_colors():
    geom = _geom()
    geom["edges"] = [
        {"source": "a", "target": "a", "flow": "data",
         "points": [[130, 140], [130, 200]]},
        {"source": "a", "target": "a", "flow": "control",
         "points": [[130, 200], [130, 300]]},
    ]
    xml = render.render(geom)
    # data=blue, control=orange hexes appear in the legend swatches
    assert "2563eb" in xml  # data blue
    assert "ea580c" in xml  # control orange
