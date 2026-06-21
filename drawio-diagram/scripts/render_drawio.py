"""Render layout geometry -> draw.io mxfile XML string."""
import xml.etree.ElementTree as ET
import shapes
import styles

_ROOT_PARENT_ID = "1"


def render(geom: dict) -> str:
    canvas = geom["canvas"]
    style_name = geom["style"]
    cs = styles.canvas_style(style_name)

    mxfile = ET.Element("mxfile", {"host": "app.diagrams.net"})
    diagram = ET.SubElement(mxfile, "diagram", {"name": geom.get("title", "Diagram"), "id": "d0"})
    model = ET.SubElement(diagram, "mxGraphModel", {
        "dx": "800", "dy": "600", "grid": "1", "gridSize": "10",
        "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1",
        "fold": "1", "page": "1", "pageScale": "1",
        "pageWidth": str(canvas["width"]), "pageHeight": str(canvas["height"]),
        "math": "0", "shadow": "0", "background": cs["background"],
    })
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": _ROOT_PARENT_ID, "parent": "0"})

    # containers first so nodes render on top
    for c in geom.get("containers", []):
        _add_container(root, c, style_name)
    for n in geom["nodes"]:
        _add_node(root, n, style_name)
    for d in geom.get("decorations", []):
        _add_decoration(root, d, style_name)
    for index, e in enumerate(geom["edges"]):
        _add_edge(root, e, style_name, index)

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode")


def _add_node(root, n, style_name):
    shape = shapes.shape_for(n.get("kind"))
    cell = ET.SubElement(root, "mxCell", {
        "id": n["id"], "value": n.get("label", ""),
        "style": styles.cell_style(n.get("kind", "default"), style_name, shape),
        "vertex": "1", "parent": _ROOT_PARENT_ID,
    })
    ET.SubElement(cell, "mxGeometry", {
        "x": str(n["x"]), "y": str(n["y"]),
        "width": str(n["width"]), "height": str(n["height"]), "as": "geometry",
    })


def _add_container(root, c, style_name):
    st = styles.STYLES[style_name]
    style_str = (
        f"rounded=0;whiteSpace=wrap;html=1;fillColor=none;"
        f"strokeColor={st['stroke']};dashed=1;dashPattern=8 4;"
        f"verticalAlign=top;fontColor={st['font_color']};fontSize=12;"
    )
    cell = ET.SubElement(root, "mxCell", {
        "id": c["id"], "value": c.get("label", ""), "style": style_str,
        "vertex": "1", "parent": _ROOT_PARENT_ID,
    })
    ET.SubElement(cell, "mxGeometry", {
        "x": str(c["x"]), "y": str(c["y"]),
        "width": str(c["width"]), "height": str(c["height"]), "as": "geometry",
    })


def _add_decoration(root, d, style_name):
    """Render a decoration by kind.

    lifeline: a vertical dashed line (free edge, no arrowhead) under a
      participant header — drawn as an edge because a line is not a box.
    frame:   a rect vertex with a label tab (verticalAlign=top), enclosing a
      range of messages. Falls back to _add_node for any unknown kind.
    """
    kind = d.get("kind")
    if kind == "lifeline":
        _add_lifeline(root, d, style_name)
        return
    if kind == "frame":
        _add_frame(root, d, style_name)
        return
    _add_node(root, d, style_name)


def _add_lifeline(root, d, style_name):
    st = styles.STYLES[style_name]
    style_str = (
        "endArrow=none;startArrow=none;html=1;dashed=1;dashPattern=6 4;"
        f"strokeColor={st['stroke']};strokeWidth=1.5;"
        "endFill=0;startFill=0;"
    )
    # Unique id keyed on participant label + position so two lifelines never
    # collide on cell id.
    cell_id = f"lifeline_{d.get('label', '')}_{d['x']}_{d['y']}"
    cell = ET.SubElement(root, "mxCell", {
        "id": cell_id, "value": "", "style": style_str,
        "edge": "1", "parent": _ROOT_PARENT_ID,
    })
    geo = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
    x = d["x"]
    y0 = d["y"]
    y1 = d["y"] + d["height"]
    ET.SubElement(geo, "mxPoint", {"x": str(x), "y": str(y0), "as": "sourcePoint"})
    ET.SubElement(geo, "mxPoint", {"x": str(x), "y": str(y1), "as": "targetPoint"})


def _add_frame(root, d, style_name):
    st = styles.STYLES[style_name]
    # A frame: a dashed rect with a label tab in the top-left. verticalAlign=top
    # + align=left places the label like a UML frame label. fillColor=none so
    # it never obscures the messages it encloses.
    style_str = (
        "rounded=0;whiteSpace=wrap;html=1;fillColor=none;"
        f"strokeColor={st['stroke']};dashed=1;dashPattern=8 4;"
        "verticalAlign=top;align=left;spacingTop=2;spacingLeft=6;"
        f"fontColor={st['font_color']};fontSize=12;"
    )
    label = d.get("frame_kind", "frame")
    if d.get("label"):
        label = f"{label}: {d['label']}"
    cell_id = f"frame_{d['x']}_{d['y']}_{d['width']}_{d['height']}"
    cell = ET.SubElement(root, "mxCell", {
        "id": cell_id, "value": label, "style": style_str,
        "vertex": "1", "parent": _ROOT_PARENT_ID,
    })
    ET.SubElement(cell, "mxGeometry", {
        "x": str(d["x"]), "y": str(d["y"]),
        "width": str(d["width"]), "height": str(d["height"]), "as": "geometry",
    })


def _add_edge(root, e, style_name, index):
    has_source = "source" in e and e["source"]
    has_target = "target" in e and e["target"]
    cell_attrs = {
        "id": f"edge_{e.get('source', 'free')}_{e.get('target', index)}_{index}",
        "value": e.get("label", ""),
        "style": styles.edge_style(e.get("flow", "data"), style_name),
        "edge": "1", "parent": _ROOT_PARENT_ID,
    }
    if has_source:
        cell_attrs["source"] = e["source"]
    if has_target:
        cell_attrs["target"] = e["target"]
    cell = ET.SubElement(root, "mxCell", cell_attrs)
    geo = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
    pts = e.get("points", [])
    if len(pts) >= 2:
        arr = ET.SubElement(geo, "Array", {"as": "points"})
        for px, py in pts[1:-1]:  # endpoints come from source/target vertices
            ET.SubElement(arr, "mxPoint", {"x": str(px), "y": str(py)})
    sx, sy = pts[0]
    ET.SubElement(geo, "mxPoint", {"x": str(sx), "y": str(sy), "as": "sourcePoint"})
    ex, ey = pts[-1]
    ET.SubElement(geo, "mxPoint", {"x": str(ex), "y": str(ey), "as": "targetPoint"})
