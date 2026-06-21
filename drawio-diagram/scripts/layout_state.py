"""State machine layout: BFS rank columns + initial/final pseudo-states.

Algorithm (deterministic):
  1. BFS from `initial` assigns ranks (= distance from initial). States are
     placed left-to-right by rank in COLUMNS (x = MARGIN + rank*col_pitch),
     and within a column stacked vertically, the column group centered on the
     canvas midline. States unreachable from `initial` get rank = max_rank + 1
     (appended at the far right, in BFS order among themselves).
  2. Each state is a rounded rect (kind "state"). Width grows with label.
  3. Pseudo-states are decorations:
       - initial_pseudostate: filled black circle just LEFT of the initial
         state, plus an edge from the circle to the initial state.
       - final_pseudostate: a bullseye (filled black disc inside a hollow ring)
         just RIGHT of each final state, plus an edge from the state to it.
  4. Transitions are orthogonal edges between states. Forward edges (rank+1)
     route right-side -> left-side with a Z-bend. Same-column / back / blocked
     edges route out to an empty vertical lane (canvas right corridor) and
     re-enter, every segment collision-checked so no edge crosses a non-
     endpoint state interior. Self-transitions loop out the top of the state.

All geometry goes through layout.assert_invariants before return.
The input diagram is never mutated.
"""
import layout

STATE_H = layout.NODE_H
INITIAL_R = 20            # initial pseudo-state circle bounding box
FINAL_R = 24              # final pseudo-state bullseye bounding box
PSEUDO_GAP = 40           # gap between a state edge and its pseudo-state
CORRIDOR_PAD = layout.MARGIN // 2  # how far past content the right corridor sits


def layout_state(d: dict) -> dict:
    geom = layout.empty_geometry("state", d["style"], d["title"])
    states = d["states"]
    transitions = d.get("transitions", [])
    initial = d["initial"]
    finals = set(d.get("final", []))
    ids = [s["id"] for s in states]

    ranks = _bfs_ranks(ids, transitions, initial)

    # --- state geometry: columns by rank, vertically stacked & centered -------
    by_rank: dict[int, list[str]] = {}
    for sid in ids:
        by_rank.setdefault(ranks[sid], []).append(sid)

    # Width per state (snapped up to SNAP). Column pitch from the widest state
    # in the diagram so columns align cleanly.
    state_w: dict[str, int] = {}
    for s in states:
        tw = layout.text_width(s["label"])
        state_w[s["id"]] = _snap_up(tw)
    col_pitch = layout.GUTTER_X + max(
        (state_w[sid] for sid in ids), default=layout.NODE_MIN_W)

    centers: dict[str, dict] = {}  # id -> {x, y, w, h, cx, cy}
    column_right = 0
    max_column_height = 0
    for r in sorted(by_rank):
        members = by_rank[r]
        x = layout.snap(layout.MARGIN + r * col_pitch)
        col_w = max(state_w[sid] for sid in members)
        # total stack height for this column
        total_h = sum(STATE_H for _ in members) + layout.GUTTER_Y * (len(members) - 1)
        max_column_height = max(max_column_height, total_h)
        # center the column's stack on 0 for now; final y assigned after we know
        # the canvas height. We place y top-down from a running cursor.
        # Defer: we need canvas height first to vertically center. Two-pass.
        column_right = max(column_right, x + col_w)

    # Canvas height from the tallest column so every column fits. The padding
    # is GUTTER_Y (not MARGIN) on each side so the edge-routing lane at
    # global_top - GUTTER_Y/2 sits at a positive y inside the canvas (edges route
    # above and below the state band through these empty lanes).
    stack_canvas_h = layout.snap(max_column_height + 2 * layout.GUTTER_Y)

    for r in sorted(by_rank):
        members = by_rank[r]
        x = layout.snap(layout.MARGIN + r * col_pitch)
        total_h = sum(STATE_H for _ in members) + layout.GUTTER_Y * (len(members) - 1)
        # center this column's stack within the canvas vertically
        y_cursor = layout.snap((stack_canvas_h - total_h) // 2)
        for sid in members:
            w = state_w[sid]
            h = layout.snap(STATE_H)
            y = y_cursor
            geom["nodes"].append({
                "id": sid,
                "label": next(s["label"] for s in states if s["id"] == sid),
                "kind": "state",
                "x": x, "y": y, "width": w, "height": h,
            })
            centers[sid] = {"x": x, "y": y, "w": w, "h": h,
                            "cx": x + w // 2, "cy": y + h // 2}
            y_cursor = layout.snap(y_cursor + STATE_H + layout.GUTTER_Y)

    # --- canvas width: include room for final pseudo-states to the right ------
    has_finals = bool(finals)
    canvas_w = layout.snap(
        column_right + layout.MARGIN + (PSEUDO_GAP + FINAL_R if has_finals else 0))
    geom["canvas"] = {"width": canvas_w, "height": stack_canvas_h}

    # --- initial pseudo-state + edge -----------------------------------------
    init_box = centers[initial]
    init_cy = init_box["cy"]
    init_dec_x = layout.snap(init_box["x"] - PSEUDO_GAP - INITIAL_R)
    init_dec_y = layout.snap(init_cy - INITIAL_R // 2)
    geom["decorations"].append({
        "kind": "initial_pseudostate",
        "x": init_dec_x, "y": init_dec_y,
        "width": INITIAL_R, "height": INITIAL_R,
        "label": "",
    })
    # edge from right-center of the initial circle to left-center of the state
    geom["edges"].append({
        "source": "", "target": initial, "label": "", "flow": "control",
        "points": [(init_dec_x + INITIAL_R, init_cy),
                   (init_box["x"], init_cy)],
    })

    # --- final pseudo-states + edges -----------------------------------------
    for sid in ids:
        if sid not in finals:
            continue
        box = centers[sid]
        cy = box["cy"]
        dec_x = layout.snap(box["x"] + box["w"] + PSEUDO_GAP)
        dec_y = layout.snap(cy - FINAL_R // 2)
        geom["decorations"].append({
            "kind": "final_pseudostate",
            "x": dec_x, "y": dec_y,
            "width": FINAL_R, "height": FINAL_R,
            "label": "",
        })
        geom["edges"].append({
            "source": sid, "target": "", "label": "", "flow": "control",
            "points": [(box["x"] + box["w"], cy), (dec_x, cy)],
        })

    # --- transition edges ----------------------------------------------------
    rects: list[tuple[str, int, int, int, int]] = [
        (n["id"], n["x"], n["y"], n["width"], n["height"]) for n in geom["nodes"]
    ]
    for tr in transitions:
        s_id, t_id = tr["from"], tr["to"]
        label = _transition_label(tr)
        if s_id == t_id:
            pts = _self_loop(centers[s_id])
        else:
            pts = _route_transition(
                s_id, t_id, centers[s_id], centers[t_id], rects, canvas_w)
        geom["edges"].append({
            "source": s_id, "target": t_id, "label": label,
            "flow": "control", "points": pts,
        })

    labels = {s["id"]: s["label"] for s in states}
    layout.assert_invariants(geom, source_nodes=labels)
    return geom


def _bfs_ranks(
    ids: list[str], transitions: list[dict], initial: str
) -> dict[str, int]:
    """BFS from `initial`; rank = distance. Unreachable states get
    max_reachable_rank + 1, then +2, ... in stable input order (so multiple
    orphans spread across appended columns rather than piling in one)."""
    adj: dict[str, list[str]] = {sid: [] for sid in ids}
    for tr in transitions:
        if tr["from"] in adj:
            adj[tr["from"]].append(tr["to"])
    # dedupe + stable order
    for sid in adj:
        seen = set()
        uniq = []
        for t in adj[sid]:
            if t not in seen:
                seen.add(t)
                uniq.append(t)
        adj[sid] = uniq

    rank: dict[str, int] = {initial: 0}
    queue = [initial]
    head = 0
    while head < len(queue):
        cur = queue[head]
        head += 1
        for nxt in adj[cur]:
            if nxt not in rank:
                rank[nxt] = rank[cur] + 1
                queue.append(nxt)
    max_rank = max(rank.values()) if rank else -1
    # Unreachable states appended after the reachable ones, one per column,
    # preserving input order for determinism.
    next_extra = max_rank + 1
    for sid in ids:
        if sid not in rank:
            rank[sid] = next_extra
            next_extra += 1
    return rank


def _transition_label(tr: dict) -> str:
    label = tr.get("label", "")
    guard = tr.get("guard")
    if label and guard:
        return f"{label} [{guard}]"
    if guard:
        return f"[{guard}]"
    return label


def _snap_up(v: int) -> int:
    rem = v % layout.SNAP
    if rem == 0:
        return v
    return v + (layout.SNAP - rem)


# ---------------------------------------------------------------------------
# Edge routing
# ---------------------------------------------------------------------------

def _side_points(box: dict) -> dict:
    x, y, w, h = box["x"], box["y"], box["w"], box["h"]
    cx = x + w // 2
    cy = y + h // 2
    return {
        "right": (x + w, cy), "left": (x, cy),
        "top": (cx, y), "bottom": (cx, y + h),
        "cx": cx, "cy": cy,
    }


def _seg_hits_state(
    x1: int, y1: int, x2: int, y2: int,
    rects: list[tuple[str, int, int, int, int]],
    skip: set[str],
) -> bool:
    """True if the axis-aligned segment intersects the INTERIOR of any state box
    not in `skip`. Strict interior: a route grazing a border is allowed."""
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
        if _seg_hits_state(x1, y1, x2, y2, rects, skip):
            return False
    return True


def _route_transition(
    s_id: str, t_id: str,
    s: dict, t: dict,
    rects: list[tuple[str, int, int, int, int]],
    canvas_w: int,
) -> list[tuple[int, int]]:
    """Collision-free orthogonal route between two states.

    Each candidate is a full polyline; we return the FIRST whose every segment
    is collision-free against non-endpoint states. Candidate order prefers the
    natural reading direction, but the collision check is the gate, so no edge
    ever crosses a non-endpoint state interior.

      1. Direct side-pair Z-routes (source side -> target side), ordered by
         naturalness for an LR state machine: right->left, then the three other
         orthogonal pairs, then elbow exits (top->top, bottom->bottom, etc.).
      2. Detour via an empty GLOBAL lane above or below the band, reached by
         exiting the source from its LEFT or RIGHT side (so the vertical exit
         doesn't cross a column-mate) and entering the target from its LEFT or
         RIGHT side (likewise avoiding its column-mates).
      3. Corridor: an empty vertical lane just past the left or right canvas
         edge, reached and exited via a clear global lane. Empty by construction.
    """
    skip = {s_id, t_id}
    sp = _side_points(s)
    tp = _side_points(t)

    # 1. direct side-pair candidates (each Z-routed).
    pairs = _direct_side_pairs(s, t)
    for start, end in pairs:
        pts = _z_route(start, end)
        if _route_clear(pts, rects, skip):
            return pts

    # 2. global-lane detour, side-exiting both endpoints.
    detour = _lane_detour(s, t, rects, skip)
    if detour is not None:
        return detour

    # 3. corridor past the nearer canvas edge, via a clear global lane.
    corridor_pts = _corridor_route(s, t, rects, skip, canvas_w)
    return corridor_pts


def _direct_side_pairs(
    s: dict, t: dict
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Ordered (source-side-point, target-side-point) pairs for Z-routing.

    Ordering prefers the natural direction first: if the target is to the right
    we prefer right->left; if to the left, left->right; vertical fallbacks and
    same-side elbows follow. The collision check decides, so this only sets
    aesthetic priority."""
    sp = _side_points(s)
    tp = _side_points(t)
    target_right = t["x"] >= s["x"]
    pairs: list[tuple[tuple[int, int], tuple[int, int]]] = []
    if target_right:
        pairs.append((sp["right"], tp["left"]))
        pairs.append((sp["bottom"], tp["top"]))
        pairs.append((sp["top"], tp["bottom"]))
        pairs.append((sp["right"], tp["right"]))   # elbow around target right
        pairs.append((sp["left"], tp["left"]))     # elbow around source left
    else:
        pairs.append((sp["left"], tp["right"]))
        pairs.append((sp["bottom"], tp["top"]))
        pairs.append((sp["top"], tp["bottom"]))
        pairs.append((sp["left"], tp["left"]))
        pairs.append((sp["right"], tp["right"]))
    return pairs


def _z_route(
    start: tuple[int, int], end: tuple[int, int]
) -> list[tuple[int, int]]:
    """Orthogonal route start->end: straight if axis-aligned, else a single
    Z-bend. The bend is placed on the side of the endpoint whose axis differs,
    so the route reads naturally (horizontal-then-vertical or vice versa)."""
    x1, y1 = start
    x2, y2 = end
    if x1 == x2 or y1 == y2:
        return [start, end]
    # Prefer bending at the source's coordinate on the dominant axis, giving a
    # clean L; for opposite-side exits (e.g. right->right) use a midpoint Z so
    # the route swings out rather than folding back through the source.
    if (x1 < x2 and start[0] < end[0]) or (x1 > x2 and start[0] > end[0]):
        # exits face the same x-direction -> Z-bend at mid x
        mid_x = (x1 + x2) // 2
        return [start, (mid_x, y1), (mid_x, y2), end]
    mid_y = (y1 + y2) // 2
    return [start, (x1, mid_y), (x2, mid_y), end]


def _lane_detour(
    s: dict, t: dict,
    rects: list[tuple[str, int, int, int, int]],
    skip: set[str],
) -> list[tuple[int, int]] | None:
    """Detour via an empty GLOBAL horizontal lane above or below the band.

    The source exits from its LEFT or RIGHT side (into the adjacent column
    gutter, so the exit never crosses a column-mate), rises/falls to the lane,
    runs across, and enters the target from its LEFT or RIGHT side (likewise
    avoiding the target's column-mates). Lane y is in the margin outside every
    state (global min-top / max-bottom), so horizontal travel is empty by
    construction. Returns the first collision-free candidate, or None."""
    sp = _side_points(s)
    tp = _side_points(t)
    global_top = min(ny for _, _, ny, _, _ in rects)
    global_bottom = max(ny + nh for _, _, ny, nh, _ in rects)
    lanes_above = [layout.snap(global_top - layout.GUTTER_Y // 2),
                   layout.snap(global_top - layout.GUTTER_Y)]
    lanes_below = [layout.snap(global_bottom + layout.GUTTER_Y // 2),
                   layout.snap(global_bottom + layout.GUTTER_Y)]

    candidates: list[list[tuple[int, int]]] = []
    for ly in lanes_above:
        if ly <= 0:
            continue
        for s_side in (sp["left"], sp["right"]):
            for t_side in (tp["left"], tp["right"]):
                candidates.append([s_side, (s_side[0], ly),
                                   (t_side[0], ly), t_side])
    for ly in lanes_below:
        for s_side in (sp["left"], sp["right"]):
            for t_side in (tp["left"], tp["right"]):
                candidates.append([s_side, (s_side[0], ly),
                                   (t_side[0], ly), t_side])
    for pts in candidates:
        if _route_clear(pts, rects, skip):
            return pts
    return None


def _corridor_route(
    s: dict, t: dict,
    rects: list[tuple[str, int, int, int, int]],
    skip: set[str],
    canvas_w: int,
) -> list[tuple[int, int]]:
    """Last-resort corridor route past the nearer canvas edge.

    Exit the source's outer side into a clear global lane, run out to the
    corridor (left or right of all content), and enter the target from its outer
    side via the same lane. Both horizontal travel and the corridor itself are
    empty by construction; we collision-check and fall back deterministically."""
    sp = _side_points(s)
    tp = _side_points(t)
    global_top = min(ny for _, _, ny, _, _ in rects)
    global_bottom = max(ny + nh for _, _, ny, nh, _ in rects)
    right_corridor = layout.snap(canvas_w + CORRIDOR_PAD)
    left_corridor = layout.snap(-CORRIDOR_PAD)

    for lane in (layout.snap(global_top - layout.GUTTER_Y // 2),
                 layout.snap(global_bottom + layout.GUTTER_Y // 2)):
        if lane <= 0:
            continue
        for corridor, s_side, t_side in (
            (right_corridor, sp["right"], tp["right"]),
            (left_corridor, sp["left"], tp["left"]),
        ):
            pts = [s_side, (s_side[0], lane),
                   (corridor, lane), (corridor, t_side[1]), t_side]
            if _route_clear(pts, rects, skip):
                return pts
    # Deterministic best-effort fallback: right corridor via the above-lane.
    lane = layout.snap(global_top - layout.GUTTER_Y // 2)
    if lane <= 0:
        lane = layout.snap(global_bottom + layout.GUTTER_Y // 2)
    return [sp["right"], (sp["right"][0], lane),
            (right_corridor, lane), (right_corridor, tp["right"][1]),
            tp["right"]]


def _self_loop(box: dict) -> list[tuple[int, int]]:
    """Self-transition: exit the top of the state, loop up and around, re-enter
    the top. Stays clear of the box interior (only touches the top border)."""
    x, y, w, h = box["x"], box["y"], box["w"], box["h"]
    cx = x + w // 2
    out_y = layout.snap(y - layout.GUTTER_Y // 2)
    top_a = (cx - w // 4, y)
    top_b = (cx + w // 4, y)
    return [top_a, (top_a[0], out_y), (top_b[0], out_y), top_b]
