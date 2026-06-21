"""Architecture diagram layout: layered horizontal bands (v1: top-to-bottom)."""
import layout

NODE_H = layout.NODE_H


def layout_architecture(d: dict) -> dict:
    direction = d.get("direction", "tb")
    if direction != "tb":
        # v1 supports tb only; fail loud rather than guess.
        raise layout.LayoutError("architecture v1 supports direction='tb' only")

    geom = layout.empty_geometry("architecture", d["style"], d["title"])
    node_map = {n["id"]: n for n in d["nodes"]}

    y_cursor = layout.MARGIN
    max_right = 0
    centers: dict[str, tuple] = {}  # id -> (cx, x, y, w, h) — 5-tuple, no cy

    for layer in d["layers"]:
        lids = layer["nodes"]
        sized = []
        for nid in lids:
            nd = node_map[nid]
            # Snap UP to the next grid line so the rendered box is always wide
            # enough to hold the label (text_width rounds down can produce a
            # box 1 snap smaller than the label — caught by assert_width_from_text).
            tw = layout.text_width(nd["label"])
            w = tw if tw % layout.SNAP == 0 else tw + (layout.SNAP - tw % layout.SNAP)
            h = layout.snap(NODE_H)
            sized.append((nid, nd, w, h))
        # An empty layer is a no-op: no nodes placed, no container emitted,
        # and y_cursor does not advance — keeps the rest of the diagram aligned.
        if not sized:
            continue
        # Outer snap is a no-op in v1 (all nodes share NODE_H, hence band_h is
        # already snapped) but kept for robustness against future heterogeneous
        # node heights.
        band_h = layout.snap(max((h for _, _, _, h in sized), default=NODE_H))

        x_cursor = layout.MARGIN
        layer_left = x_cursor
        for nid, nd, w, h in sized:
            nx, ny = layout.snap(x_cursor), layout.snap(y_cursor)
            geom["nodes"].append({
                "id": nid, "label": nd["label"],
                "kind": nd.get("kind", "service"),
                "x": nx, "y": ny, "width": w, "height": band_h,
            })
            centers[nid] = (nx + w // 2, nx, ny, w, band_h)
            x_cursor += w + layout.GUTTER_X
        layer_right = x_cursor - layout.GUTTER_X
        max_right = max(max_right, layer_right)

        geom["containers"].append({
            "id": layer["id"], "label": layer.get("label", ""),
            "x": layout.snap(layer_left - 10), "y": layout.snap(y_cursor - 10),
            "width": layout.snap(layer_right - layer_left + 20),
            "height": layout.snap(band_h + 20),
        })
        y_cursor += band_h + layout.GUTTER_Y

    geom["canvas"] = {
        "width": layout.snap(max_right + layout.MARGIN),
        "height": layout.snap(y_cursor - layout.GUTTER_Y + layout.MARGIN),
    }

    for e in d["edges"]:
        src = centers[e["source"]]
        tgt = centers[e["target"]]
        pts = _orthogonal(src, tgt)
        geom["edges"].append({
            "source": e["source"], "target": e["target"],
            "label": e.get("label", ""), "flow": e.get("flow", "data"),
            "points": pts,
        })

    labels = {n["id"]: n["label"] for n in d["nodes"]}
    layout.assert_invariants(geom, source_nodes=labels)
    return geom


def _orthogonal(src, tgt) -> list[list[int]]:
    """src/tgt = (cx, x, y, w, h). Route bottom-of-src -> top-of-tgt with a
    Z-bend (3-segment orthogonal route) when cx != tx, or a straight 2-point
    line when aligned. cy was dropped from the tuple — never read."""
    sx, sxx, syy, sw, sh = src
    tx, txx, tyy, tw, th = tgt
    start = (sx, syy + sh)            # bottom-center of source
    mid_y = (syy + sh + tyy) // 2     # halfway into the gutter
    end = (tx, tyy)                   # top-center of target
    if sx == tx:
        return [start, end]
    return [start, (sx, mid_y), (tx, mid_y), end]
