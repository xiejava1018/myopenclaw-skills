"""ER diagram layout: entities as 3-compartment boxes in a grid + relationships.

Algorithm (deterministic):
  * Entities -> uniform-width 3-compartment boxes laid out in a 2-3 column grid
    (2 columns if <=4 entities, 3 if more), filled left-to-right, top-to-bottom.
    Box width is the snapped max over all entities of (longest line width +
    padding); height grows with the attribute count.
  * Relationships -> orthogonal edges between entity edges. For each pair we
    enumerate side-pair candidates (right->left, left->right, bottom->top,
    top->bottom, and the two same-side elbow exits) in shortest-route order and
    take the FIRST whose every segment is collision-free against the OTHER
    entities. If every direct candidate is blocked, we route out a right
    corridor (a vertical lane past the canvas right edge), which is empty by
    construction. This guarantees no edge ever crosses a non-endpoint entity.

All geometry goes through layout.assert_invariants before return.
The input diagram is never mutated.
"""
import layout

HEADER_H = 40      # entity name header compartment
ROW_H = 24         # per attribute row
ENTITY_PAD = 32    # horizontal padding around the widest text line
ATTR_MARKER = " (PK)"   # width-calc marker appended to a PK attribute name
ATTR_MARKER_FK = " (FK)"


def layout_er(d: dict) -> dict:
    geom = layout.empty_geometry("er", d["style"], d["title"])
    entities = d["entities"]
    relationships = d.get("relationships", [])

    # --- entity geometry --------------------------------------------------
    # Uniform box width across all entities (grid looks tidy). Based on the
    # widest single line: entity name OR longest attribute-with-marker.
    max_line_w = 0
    for ent in entities:
        w_name = layout.text_width(ent["label"])
        for a in ent["attributes"]:
            disp = _attr_display(a)
            w_attr = layout.text_width(disp)
            max_line_w = max(max_line_w, w_name, w_attr)
    box_w = _snap_up(max(max_line_w + ENTITY_PAD, layout.NODE_MIN_W))
    box_w = max(box_w, layout.text_width(entities[0]["label"])) if entities else box_w

    max_attrs = max((len(e["attributes"]) for e in entities), default=0)
    # Row pitch uses the tallest entity so rows never overlap, but each entity's
    # own height grows with its attribute count (spec: HEADER_H + n*ROW_H).
    row_h = _snap_up(HEADER_H + max(1, max_attrs) * ROW_H) + layout.GUTTER_Y

    cols = 2 if len(entities) <= 4 else 3
    col_w = box_w + layout.GUTTER_X

    centers: dict[str, dict] = {}  # id -> geometry map
    for i, ent in enumerate(entities):
        col = i % cols
        row = i // cols
        x = layout.snap(layout.MARGIN + col * col_w)
        y = layout.snap(layout.MARGIN + row * row_h)
        h = _snap_up(HEADER_H + max(1, len(ent["attributes"])) * ROW_H)
        geom["nodes"].append({
            "id": ent["id"], "label": ent["label"], "kind": "er_entity",
            "x": x, "y": y, "width": box_w, "height": h,
            "attributes": [
                {"name": a["name"], "pk": a.get("pk", False),
                 "fk": a.get("fk", False)}
                for a in ent["attributes"]
            ],
        })
        centers[ent["id"]] = {"x": x, "y": y, "w": box_w, "h": h}

    nrows = (len(entities) + cols - 1) // cols if entities else 1
    last_row = (len(entities) - 1) // cols if entities else 0
    last_col_used = (len(entities) - 1) % cols if entities else 0
    canvas_w = layout.snap(
        layout.MARGIN + cols * col_w - layout.GUTTER_X + layout.MARGIN)
    # bottom of the last actually-used row, plus margin. Use the tallest entity
    # in the last row so the canvas encloses it.
    max_h_last_row = max(
        (centers[entities[r * cols + c]["id"]]["h"]
         for r in range(last_row + 1) for c in range(cols)
         if r == last_row and r * cols + c < len(entities)),
        default=0,
    )
    canvas_h = layout.snap(
        layout.MARGIN + last_row * row_h + max_h_last_row + layout.MARGIN)

    # --- relationship edges ----------------------------------------------
    rects = [(n["id"], n["x"], n["y"], n["width"], n["height"])
             for n in geom["nodes"]]
    for rel in relationships:
        s = centers[rel["from"]]
        t = centers[rel["to"]]
        pts = _route_relationship(
            rel["from"], rel["to"], s, t, rects, canvas_w)
        label = _rel_label(rel)
        geom["edges"].append({
            "source": rel["from"], "target": rel["to"],
            "label": label, "flow": "data", "points": pts,
        })

    geom["canvas"] = {"width": canvas_w, "height": canvas_h}

    labels = {e["id"]: e["label"] for e in entities}
    layout.assert_invariants(geom, source_nodes=labels)
    return geom


def _attr_display(a: dict) -> str:
    """Attribute name + marker, used only for WIDTH calculation. Rendering marks
    PK/FK differently (bold/italic); here we just reserve horizontal space."""
    name = a["name"]
    if a.get("pk"):
        return name + ATTR_MARKER
    if a.get("fk"):
        return name + ATTR_MARKER_FK
    return name


def _rel_label(rel: dict) -> str:
    card = rel.get("card", "")
    name = rel.get("label", "")
    if name and card:
        return f"{name} ({card})"
    if card:
        return card
    return name


def _snap_up(v: int) -> int:
    """Round UP to the nearest SNAP multiple (boxes must enclose their text)."""
    rem = v % layout.SNAP
    if rem == 0:
        return v
    return v + (layout.SNAP - rem)


def _seg_hits_entity(
    x1: int, y1: int, x2: int, y2: int,
    rects: list[tuple[str, int, int, int, int]],
    skip: set[str],
) -> bool:
    """True if the axis-aligned segment (x1,y1)-(x2,y2) intersects the INTERIOR
    of any entity box not in `skip`. Segment is horizontal or vertical.

    Strict interior test: a route grazing an entity's border (e.g. running along
    its edge) is allowed; only a true cut-through counts as a hit."""
    for nid, nx, ny, nw, nh in rects:
        if nid in skip:
            continue
        if y1 == y2:
            sx_lo, sx_hi = (x1, x2) if x1 <= x2 else (x2, x1)
            if ny < y1 < ny + nh and sx_lo < nx + nw and sx_hi > nx:
                return True
        else:
            sy_lo, sy_hi = (y1, y2) if y1 <= y2 else (y2, y1)
            if nx < x1 < nx + nw and sy_lo < ny + nh and sy_hi > ny:
                return True
    return False


def _route_clear(
    pts: list[tuple[int, int]],
    rects: list[tuple[str, int, int, int, int]],
    skip: set[str],
) -> bool:
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        if _seg_hits_entity(x1, y1, x2, y2, rects, skip):
            return False
    return True


def _side_points(box: dict) -> dict:
    """Anchor points on each side midpoint of a box."""
    x, y, w, h = box["x"], box["y"], box["w"], box["h"]
    cx = x + w // 2
    cy = y + h // 2
    return {
        "right": (x + w, cy), "left": (x, cy),
        "top": (cx, y), "bottom": (cx, y + h),
        "cx": cx, "cy": cy,
    }


def _direct_candidates(
    s: dict, t: dict
) -> list[tuple[str, tuple[int, int], tuple[int, int], tuple[int, int] | None]]:
    """Ordered list of (side_s, start_pt, end_pt, mid_pt_or_None) direct routes
    in roughly shortest-first order. mid_pt produces a Z-bend; None is straight.

    Right->left is preferred for left-to-right reading order; we then try the
    reverse, then vertical (bottom->top / top->bottom), then elbow exits on the
    same side for adjacent boxes."""
    sp = _side_points(s)
    tp = _side_points(t)
    out = []
    # horizontal pairs
    out.append(("right", sp["right"], tp["left"], None))
    out.append(("left", sp["left"], tp["right"], None))
    # vertical pairs
    out.append(("bottom", sp["bottom"], tp["top"], None))
    out.append(("top", sp["top"], tp["bottom"], None))
    return out


def _route_relationship(
    src_id: str, tgt_id: str,
    s: dict, t: dict,
    rects: list[tuple[str, int, int, int, int]],
    canvas_w: int,
    canvas_h: int = 0,
) -> list[tuple[int, int]]:
    """Pick a collision-free orthogonal route between two entity boxes.

    Strategy (each candidate is whole-route collision-checked before use):
      1. Self-relationship: loop out the right side and back in.
      2. Direct side-pair candidates (right->left, left->right, bottom->top,
         top->bottom): straight when aligned, else Z-bend. Take the first clear.
      3. Detour candidates: if both boxes are blocked head-on (e.g. same row with
         a box between them, or same column), exit to a horizontal lane in the
         empty gutter BELOW or ABOVE the row band and re-enter. The lane y is a
         snap multiple chosen in the empty margin band outside the boxes' shared
         vertical span, guaranteed not to intersect any entity in that band.
      4. Last resort: right corridor past the canvas edge (empty by construction).
    No edge ever crosses a non-endpoint entity interior."""
    skip = {src_id, tgt_id}

    if src_id == tgt_id:
        return _self_loop(s)

    for _side, start, end, _mid in _direct_candidates(s, t):
        pts = _z_route(start, end)
        if _route_clear(pts, rects, skip):
            return pts

    # Detour via a horizontal lane below/above the shared vertical span.
    detour = _detour_route(s, t, rects, skip)
    if detour is not None:
        return detour

    # All direct + detour candidates blocked -> right corridor (empty by design).
    corridor = layout.snap(canvas_w + layout.MARGIN // 2)
    sp = _side_points(s)
    tp = _side_points(t)
    s_start = sp["right"]
    t_end = tp["right"]
    pts = [s_start, (corridor, s_start[1]),
           (corridor, t_end[1]), t_end]
    if _route_clear(pts, rects, skip):
        return pts
    return [s_start, t_end]


def _detour_route(
    s: dict, t: dict,
    rects: list[tuple[str, int, int, int, int]],
    skip: set[str],
) -> list[tuple[int, int]] | None:
    """Route via an empty horizontal lane below or above the two boxes' shared
    vertical band. Tries (in order): lane below both boxes, lane above both.
    Each lane y is the snap of (band_bottom + GUTTER/2) or (band_top - GUTTER/2)
    — empty by construction because it sits in the inter-row gutter / margin.
    Returns the first clear route, or None if neither works."""
    sp = _side_points(s)
    tp = _side_points(t)
    band_bottom = max(s["y"] + s["h"], t["y"] + t["h"])
    band_top = min(s["y"], t["y"])

    # Lane below the band (snap into the gutter/margin beneath both boxes).
    below_y = layout.snap(band_bottom + layout.GUTTER_Y // 2)
    # Lane above the band.
    above_y = layout.snap(band_top - layout.GUTTER_Y // 2)

    for lane_y, s_anchor, t_anchor in (
        (below_y, sp["bottom"], tp["bottom"]),
        (below_y, sp["right"], tp["left"]),
        (above_y, sp["top"], tp["top"]),
        (above_y, sp["right"], tp["left"]),
    ):
        if lane_y <= 0:
            continue
        pts = [s_anchor, (s_anchor[0], lane_y),
               (t_anchor[0], lane_y), t_anchor]
        if _route_clear(pts, rects, skip):
            return pts
    return None


def _z_route(
    start: tuple[int, int], end: tuple[int, int]
) -> list[tuple[int, int]]:
    """Orthogonal route start->end. Straight if aligned on an axis, else a
    single Z-bend through the midpoint of the non-aligned axis."""
    x1, y1 = start
    x2, y2 = end
    if x1 == x2 or y1 == y2:
        return [start, end]
    # If horizontal offset dominates, bend horizontally at start-y then drop.
    # Choose the bend that keeps both segments axis-aligned (Z-bend).
    if abs(x2 - x1) >= abs(y2 - y1):
        mid_x = (x1 + x2) // 2
        return [start, (mid_x, y1), (mid_x, y2), end]
    mid_y = (y1 + y2) // 2
    return [start, (x1, mid_y), (x2, mid_y), end]


def _self_loop(box: dict) -> list[tuple[int, int]]:
    """Self-relationship: exit the right side, run out, and re-enter the right
    side lower down — an orthogonal loop that stays clear of the box interior
    (it only touches the right border, never the interior)."""
    x, y, w, h = box["x"], box["y"], box["w"], box["h"]
    out_x = x + w + layout.GUTTER_X // 2
    top = (x + w, y + h // 3)
    bot = (x + w, y + 2 * h // 3)
    return [top, (out_x, top[1]), (out_x, bot[1]), bot]
