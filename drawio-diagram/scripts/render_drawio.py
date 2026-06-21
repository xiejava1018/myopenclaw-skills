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
        if n.get("kind") == "er_entity" or "attributes" in n:
            _add_entity(root, n, style_name)
        else:
            _add_node(root, n, style_name)
    for d in geom.get("decorations", []):
        _add_decoration(root, d, style_name)
    for index, e in enumerate(geom["edges"]):
        _add_edge(root, e, style_name, index)

    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode")


def _add_node(root, n, style_name):
    provider = n.get("provider")
    service = n.get("service")
    if provider and service:
        # Cloud service glyph takes precedence over kind-based shape.
        style_str = shapes.cloud_icon(provider, service)
    else:
        shape = shapes.shape_for(n.get("kind"))
        style_str = styles.cell_style(n.get("kind", "default"), style_name, shape)
    cell = ET.SubElement(root, "mxCell", {
        "id": n["id"], "value": n.get("label", ""),
        "style": style_str,
        "vertex": "1", "parent": _ROOT_PARENT_ID,
    })
    ET.SubElement(cell, "mxGeometry", {
        "x": str(n["x"]), "y": str(n["y"]),
        "width": str(n["width"]), "height": str(n["height"]), "as": "geometry",
    })


def _add_entity(root, n, style_name):
    """Render an ER entity as a single rect cell with an HTML 3-compartment
    label: bold centered name header, a horizontal rule, then one row per
    attribute. PK is underlined (<u>), FK is italic (<i>); all rows left-aligned
    so the column reads like an attribute list."""
    st = styles.STYLES[style_name]
    style_str = (
        "rounded=0;whiteSpace=wrap;html=1;"
        f"fillColor={st['palette'].get('default', '#ffffff')};"
        f"strokeColor={st['stroke']};fontColor={st['font_color']};"
        f"fontSize={st['font_size']};align=left;verticalAlign=top;"
    )
    label = _entity_html_label(n)
    cell = ET.SubElement(root, "mxCell", {
        "id": n["id"], "value": label, "style": style_str,
        "vertex": "1", "parent": _ROOT_PARENT_ID,
    })
    ET.SubElement(cell, "mxGeometry", {
        "x": str(n["x"]), "y": str(n["y"]),
        "width": str(n["width"]), "height": str(n["height"]), "as": "geometry",
    })


def _entity_html_label(n: dict) -> str:
    """Build the HTML label for an ER entity: <b>Name</b><hr>attr rows.

    PK attributes are underlined, FK attributes italic. draw.io renders html=1
    label content as HTML, so a single value string suffices."""
    name = n.get("label", "")
    parts = [f"<div style=\"text-align:center\"><b>{_esc(name)}</b></div>",
             "<hr size=\"1\">"]
    for a in n.get("attributes", []):
        an = _esc(a.get("name", ""))
        if a.get("pk"):
            row = f"<u>{an}</u>"
        elif a.get("fk"):
            row = f"<i>{an}</i>"
        else:
            row = an
        parts.append(f"<div>{row}</div>")
    return "".join(parts)


def _esc(s: str) -> str:
    """XML-escape text going into an HTML label value."""
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


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
    initial_pseudostate: a filled black disc (UML initial pseudo-state).
    final_pseudostate:   a UML final pseudo-state (bullseye) — rendered as an
      outer hollow ring with a smaller filled black disc on top. Two cells
      because draw.io cannot express concentric circles in a single cell.
    """
    kind = d.get("kind")
    if kind == "lifeline":
        _add_lifeline(root, d, style_name)
        return
    if kind == "frame":
        _add_frame(root, d, style_name)
        return
    if kind in ("initial_pseudostate", "final_pseudostate"):
        _add_pseudostate(root, d)
        return
    _add_node(root, d, style_name)


def _add_pseudostate(root, d):
    """Render a UML pseudo-state as small circle cell(s).

    initial: a single filled black disc.
    final:   a bullseye — an outer hollow ring (white fill, thick black stroke)
             with an inner filled black disc drawn on top. The inner disc sits
             centered with ~30% the bounding diameter, matching the standard
             UML final-state glyph.
    Both are non-interactive (no label, no wrapping) so they read as glyphs.
    """
    kind = d.get("kind")
    x, y, w, h = d["x"], d["y"], d["width"], d["height"]
    cx = x + w // 2
    cy = y + h // 2
    if kind == "initial_pseudostate":
        style_str = "ellipse;fillColor=#000000;strokeColor=#000000;whiteSpace=wrap;html=1;"
        cell = ET.SubElement(root, "mxCell", {
            "id": f"init_{x}_{y}_{w}_{h}", "value": "", "style": style_str,
            "vertex": "1", "parent": _ROOT_PARENT_ID,
        })
        ET.SubElement(cell, "mxGeometry", {
            "x": str(x), "y": str(y),
            "width": str(w), "height": str(h), "as": "geometry",
        })
        return
    # final pseudo-state: outer hollow ring + inner filled disc (bullseye).
    outer_style = ("ellipse;fillColor=#ffffff;strokeColor=#000000;"
                   "strokeWidth=3;whiteSpace=wrap;html=1;")
    outer = ET.SubElement(root, "mxCell", {
        "id": f"final_outer_{x}_{y}_{w}_{h}", "value": "", "style": outer_style,
        "vertex": "1", "parent": _ROOT_PARENT_ID,
    })
    ET.SubElement(outer, "mxGeometry", {
        "x": str(x), "y": str(y),
        "width": str(w), "height": str(h), "as": "geometry",
    })
    inner_d = max(8, (min(w, h) * 3) // 10)  # ~30% of bbox, floored at 8px
    inner_style = "ellipse;fillColor=#000000;strokeColor=#000000;whiteSpace=wrap;html=1;"
    inner = ET.SubElement(root, "mxCell", {
        "id": f"final_inner_{x}_{y}_{w}_{h}", "value": "", "style": inner_style,
        "vertex": "1", "parent": _ROOT_PARENT_ID,
    })
    ET.SubElement(inner, "mxGeometry", {
        "x": str(cx - inner_d // 2), "y": str(cy - inner_d // 2),
        "width": str(inner_d), "height": str(inner_d), "as": "geometry",
    })


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
