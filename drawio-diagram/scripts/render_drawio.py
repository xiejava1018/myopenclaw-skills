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
        _add_node(root, d, style_name)
    for e in geom["edges"]:
        _add_edge(root, e, style_name)

    _indent(mxfile)
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


def _add_edge(root, e, style_name):
    cell = ET.SubElement(root, "mxCell", {
        "id": f"edge_{e['source']}_{e['target']}",
        "value": e.get("label", ""),
        "style": styles.edge_style(e.get("flow", "data"), style_name),
        "edge": "1", "parent": _ROOT_PARENT_ID,
        "source": e["source"], "target": e["target"],
    })
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


def _indent(elem, level=0):
    """Pretty-print without lxml (stdlib only)."""
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i
