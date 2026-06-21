"""Flowchart layout: Sugiyama-lite rank-based layout (deterministic).

Pipeline:
  1. Rank assignment — longest path from roots on the forward DAG. Back edges
     (cycle-closing edges whose cycle has an external entry, e.g. an error
     retry loop reached from 'start') are dropped from ranking and routed
     sideways. A pure cycle with no entry point is rejected.
  2. Within-rank ordering — barycenter heuristic to reduce crossings.
  3. Coordinate placement — left-to-right per rank, y by rank.
  4. Edge routing — orthogonal; forward edges Z-bend top/bottom, back/same-rank
     edges and forward edges blocked by an intermediate node route out the side
     through a right-of-content corridor using empty gutter lanes.

All geometry goes through layout.assert_invariants before return.
The input diagram is never mutated.
"""
import layout

NODE_H = layout.NODE_H


def layout_flowchart(d: dict) -> dict:
    geom = layout.empty_geometry("flowchart", d["style"], d["title"])
    nodes = d["nodes"]
    edges = d["edges"]
    ids = [n["id"] for n in nodes]

    ranks = _assign_ranks(ids, edges)
    order = _order_by_barycenter(ids, edges, ranks)

    # Group node ids by rank preserving barycenter order within each rank.
    by_rank: dict[int, list[str]] = {}
    for nid in order:
        by_rank.setdefault(ranks[nid], []).append(nid)

    # Coordinate placement (track geometry for edge routing).
    centers: dict[str, tuple[int, int, int, int, int]] = {}  # id -> (cx,x,y,w,h)
    max_right = 0
    for r in sorted(by_rank):
        y = layout.snap(layout.MARGIN + r * (NODE_H + layout.GUTTER_Y))
        x_cursor = layout.MARGIN
        for nid in by_rank[r]:
            nd = next(n for n in nodes if n["id"] == nid)
            tw = layout.text_width(nd["label"])
            w = tw if tw % layout.SNAP == 0 else tw + (layout.SNAP - tw % layout.SNAP)
            h = layout.snap(NODE_H)
            x = layout.snap(x_cursor)
            geom["nodes"].append({
                "id": nid, "label": nd["label"],
                "kind": nd.get("kind", "process"),
                "x": x, "y": y, "width": w, "height": h,
            })
            centers[nid] = (x + w // 2, x, y, w, h)
            x_cursor += w + layout.GUTTER_X
            max_right = max(max_right, x + w)

    canvas_w = layout.snap(max_right + layout.MARGIN)
    geom["canvas"] = {
        "width": canvas_w,
        "height": layout.snap(
            layout.MARGIN + max(by_rank) * (NODE_H + layout.GUTTER_Y)
            + NODE_H + layout.MARGIN
        ),
    }

    # Node rects for overlap-aware routing. Excludes the two endpoints of each
    # edge when checking for blockers.
    rects: list[tuple[str, int, int, int, int]] = [
        (n["id"], n["x"], n["y"], n["width"], n["height"]) for n in geom["nodes"]
    ]

    # Gutter lanes (horizontal, between ranks) are guaranteed empty — use them
    # as travel lanes for side-routed edges so horizontal segments never cross
    # a co-rank node on the way to the right corridor.
    gutter_ys = _gutter_lanes(by_rank)

    for e in edges:
        src = centers[e["source"]]
        tgt = centers[e["target"]]
        forward = ranks[e["target"]] > ranks[e["source"]]
        blocked = forward and _forward_path_blocked(src, tgt, rects,
                                                    e["source"], e["target"])
        if forward and not blocked:
            pts = _orthogonal_forward(src, tgt)
        else:
            # Back edge, same-rank edge, OR a forward edge whose straight
            # vertical path would cut through an intermediate node: route via
            # a corridor to the right of all content, using gutter lanes.
            pts = _orthogonal_side(src, tgt, canvas_w, gutter_ys, rects,
                                   e["source"], e["target"])
        geom["edges"].append({
            "source": e["source"], "target": e["target"],
            "label": e.get("label", ""),
            "flow": e.get("flow", "control"),
            "points": pts,
        })

    labels = {n["id"]: n["label"] for n in nodes}
    layout.assert_invariants(geom, source_nodes=labels)
    return geom


def _assign_ranks(ids: list[str], edges: list[dict]) -> dict[str, int]:
    """Longest-path rank from roots via topological relaxation.

    Cycle policy (v1): a back edge — the closing edge of a cycle that has an
    external entry (some node in the cycle is reached from outside it) — is
    allowed and routed sideways; only its forward DAG is used for ranking. A
    pure cycle with no entry point (every node's incoming edges stay inside the
    cycle) makes ranking impossible and is rejected. This is what distinguishes
    an error-retry loop (reachable from 'start') from a bare a<->b cycle."""
    back_edges = _cycle_closing_edges(ids, edges)  # raises on a pure cycle
    forward = [e for e in edges if (e["source"], e["target"]) not in back_edges]
    order = _topo_order(ids, forward)
    rank = {nid: 0 for nid in ids}
    # Relax along forward edges in topological order: a single pass converges
    # because every forward edge's source is processed before its target.
    for nid in order:
        for e in forward:
            if e["source"] == nid:
                t = e["target"]
                if rank[nid] + 1 > rank[t]:
                    rank[t] = rank[nid] + 1
    return rank


def _cycle_closing_edges(
    ids: list[str], edges: list[dict]
) -> set[tuple[str, str]]:
    """Return the set of edges that close a cycle (u->v where v reaches u via
    other edges). Raises LayoutError if a cycle has no external entry.

    Uses SCC condensation: within each non-trivial SCC, every edge whose
    endpoints share the SCC is a cycle-closing candidate. The SCC is rankable
    iff some node in it has an incoming edge from a different SCC (an entry).
    If no non-trivial SCC has an entry, the graph is a pure cycle -> raise.
    """
    scc_id = _tarjan_sccs(ids, edges)
    # external entry: does any node in this SCC have an incoming edge from a
    # node in a DIFFERENT SCC?
    has_entry: dict[int, bool] = {}
    # Collect SCCs of size >= 2 (self-loops handled too: a self-loop edge has
    # source==target in a size-1 SCC — treat as a cycle with no entry).
    self_loops = {e["source"] for e in edges if e["source"] == e["target"]}
    sizes: dict[int, int] = {}
    for nid in ids:
        sizes[scc_id[nid]] = sizes.get(scc_id[nid], 0) + 1
    nontrivial = {sid for sid, sz in sizes.items() if sz >= 2}
    # Map each non-trivial SCC: does it have an external incoming edge?
    for e in edges:
        s, t = e["source"], e["target"]
        if scc_id[s] != scc_id[t] and scc_id[t] in nontrivial:
            has_entry[scc_id[t]] = True
    for nid in self_loops:
        # self-loop node is its own SCC; treat as a pure cycle (no entry).
        if scc_id[nid] not in has_entry:
            has_entry[scc_id[nid]] = False
    # Any non-trivial SCC lacking an external entry => pure cycle => reject.
    for sid in nontrivial:
        if not has_entry.get(sid, False):
            raise layout.LayoutError(
                "flowchart v1 requires a DAG (cycle detected)"
            )
    # Break cycles: within each non-trivial SCC, run a DFS and classify edges.
    # Tree/forward/cross edges are kept; back edges (to a DFS ancestor) close a
    # cycle and are dropped. This keeps the SCC connected as a forward chain
    # while removing exactly the edges that form cycles. DFS roots at the SCC's
    # entry nodes (external incoming edge) so the kept forward chain matches the
    # natural entry direction (e.g. start -> input, not error -> input).
    external_in: dict[str, bool] = {}  # node -> has an incoming edge from outside its SCC
    for e in edges:
        if scc_id[e["source"]] != scc_id[e["target"]]:
            external_in[e["target"]] = True
    back: set[tuple[str, str]] = set()
    scc_members: dict[int, list[str]] = {}
    for nid in ids:
        scc_members.setdefault(scc_id[nid], []).append(nid)
    for sid in nontrivial:
        members = scc_members[sid]
        member_set = set(members)
        internal = [(e["source"], e["target"]) for e in edges
                    if e["source"] in member_set and e["target"] in member_set]
        entries = sorted(m for m in members if external_in.get(m))
        back |= _dfs_back_edges(members, internal, roots=entries)
    return back


def _dfs_back_edges(
    members: list[str],
    internal: list[tuple[str, str]],
    roots: list[str] | None = None,
) -> set[tuple[str, str]]:
    """Classify internal edges via iterative DFS. Returns the set of back edges
    (those whose target is an ancestor of source on the DFS stack) — these are
    the cycle-closing edges we drop. If `roots` is given, DFS starts from those
    nodes first (sorted), then any unvisited members, so the kept forward chain
    respects the external entry direction."""
    adj: dict[str, list[str]] = {m: [] for m in members}
    for s, t in internal:
        adj[s].append(t)
    for m in members:
        adj[m].sort()
    color = {}  # 0=unvisited,1=in-progress(gray),2=done(black)
    back: set[tuple[str, str]] = set()
    order: list[str] = []
    seen = set()
    for r in (roots or []):
        if r not in seen:
            order.append(r)
            seen.add(r)
    for m in members:
        if m not in seen:
            order.append(m)
            seen.add(m)
    for start in order:
        if start in color:
            continue
        stack: list[tuple[str, int]] = [(start, 0)]
        color[start] = 1
        while stack:
            nid, pi = stack[-1]
            neighbors = adj[nid]
            if pi < len(neighbors):
                w = neighbors[pi]
                stack[-1] = (nid, pi + 1)
                if color.get(w, 0) == 0:
                    color[w] = 1
                    stack.append((w, 0))
                elif color[w] == 1:
                    back.add((nid, w))  # gray target => cycle-closing
                continue
            color[nid] = 2
            stack.pop()
    return back


def _tarjan_sccs(ids: list[str], edges: list[dict]) -> dict[str, int]:
    """Iterative Tarjan. Returns {node: scc_index}. Handles large/deep graphs
    without recursion limits."""
    index = {}
    lowlink = {}
    on_stack = {}
    stack: list[str] = []
    counter = [0]
    scc = {}
    next_scc = [0]
    adj: dict[str, list[str]] = {nid: [] for nid in ids}
    for e in edges:
        adj[e["source"]].append(e["target"])

    for root in ids:
        if root in index:
            continue
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            nid, pi = work[-1]
            if pi == 0:
                index[nid] = lowlink[nid] = counter[0]
                counter[0] += 1
                stack.append(nid)
                on_stack[nid] = True
            recursed = False
            neighbors = adj[nid]
            for i in range(pi, len(neighbors)):
                w = neighbors[i]
                if w not in index:
                    work[-1] = (nid, i + 1)
                    work.append((w, 0))
                    recursed = True
                    break
                if on_stack.get(w):
                    lowlink[nid] = min(lowlink[nid], index[w])
            if recursed:
                continue
            if lowlink[nid] == index[nid]:
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc[w] = next_scc[0]
                    if w == nid:
                        break
                next_scc[0] += 1
            work.pop()
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[nid])
    return scc


def _topo_order(ids: list[str], edges: list[dict]) -> list[str]:
    """Kahn's algorithm. Deterministic via sorted node-id tie-breaking.
    Raises LayoutError if the graph is not a DAG."""
    adj: dict[str, list[str]] = {nid: [] for nid in ids}
    indeg: dict[str, int] = {nid: 0 for nid in ids}
    for e in edges:
        adj[e["source"]].append(e["target"])
        indeg[e["target"]] += 1
    ready = sorted(nid for nid in ids if indeg[nid] == 0)
    order: list[str] = []
    while ready:
        nid = ready.pop(0)
        order.append(nid)
        for t in adj[nid]:
            indeg[t] -= 1
            if indeg[t] == 0:
                ready.append(t)
                ready.sort()
    if len(order) != len(ids):
        # Should not happen after back-edge removal, but guard anyway.
        raise layout.LayoutError(
            "flowchart v1 requires a DAG (cycle detected)"
        )
    return order


def _order_by_barycenter(
    ids: list[str], edges: list[dict], ranks: dict[str, int]
) -> list[str]:
    """Deterministic within-rank ordering via upward barycenter (avg position
    of source-neighbors in rank-1). Two passes; ties broken by node id."""
    by_rank: dict[int, list[str]] = {}
    for nid in ids:
        by_rank.setdefault(ranks[nid], []).append(nid)

    # source-of: target -> list of source ids (for upward barycenter).
    sources_of: dict[str, list[str]] = {nid: [] for nid in ids}
    for e in edges:
        sources_of[e["target"]].append(e["source"])

    for r in sorted(by_rank):
        if r == 0:
            by_rank[r].sort()
            continue
        # Upward barycenter: average position of this node's sources in the
        # previous (already-sorted) rank. Two passes; ties broken by node id.
        for _ in range(2):
            prev_pos = {nid: i for i, nid in enumerate(by_rank[r - 1])}
            def bary(nid: str, _pp=prev_pos) -> float:
                srcs = [s for s in sources_of[nid] if s in _pp]
                if not srcs:
                    return float("inf")
                return sum(_pp[s] for s in srcs) / len(srcs)
            by_rank[r].sort(key=lambda nid: (bary(nid), nid))
    # Flatten ranks back into a single list ordered by rank then barycenter.
    ordered: list[str] = []
    for r in sorted(by_rank):
        ordered.extend(by_rank[r])
    return ordered


def _forward_path_blocked(
    src: tuple[int, int, int, int, int],
    tgt: tuple[int, int, int, int, int],
    rects: list[tuple[str, int, int, int, int]],
    src_id: str,
    tgt_id: str,
) -> bool:
    """True if the straight/Z-bend forward route from src to tgt would pass
    through any other node's bounding box. src/tgt = (cx,x,y,w,h)."""
    scx, _, syy, _, sh = src
    tcx, _, tyy, _, _ = tgt
    src_bottom = syy + sh
    tgt_top = tyy
    if scx == tcx:
        # Straight vertical at x=scx from src_bottom to tgt_top.
        return _seg_hits_node(scx, src_bottom, scx, tgt_top, rects,
                              {src_id, tgt_id})
    mid_y = (src_bottom + tyy) // 2
    # Three segments: down at scx (src_bottom..mid_y), across at mid_y
    # (scx..tcx), down at tcx (mid_y..tgt_top).
    for x1, y1, x2, y2 in (
        (scx, src_bottom, scx, mid_y),
        (scx, mid_y, tcx, mid_y),
        (tcx, mid_y, tcx, tgt_top),
    ):
        if _seg_hits_node(x1, y1, x2, y2, rects, {src_id, tgt_id}):
            return True
    return False


def _seg_hits_node(
    x1: int, y1: int, x2: int, y2: int,
    rects: list[tuple[str, int, int, int, int]],
    skip: set[str],
) -> bool:
    """Does the axis-aligned segment (x1,y1)-(x2,y2) intersect any node box
    not in `skip`? Segments here are horizontal or vertical."""
    for nid, nx, ny, nw, nh in rects:
        if nid in skip:
            continue
        # Horizontal segment: y constant, x spans [min,max].
        if y1 == y2:
            sx_lo, sx_hi = (x1, x2) if x1 <= x2 else (x2, x1)
            # hit if y is strictly within the node's vertical span (a route
            # along the node's own top/bottom edge would coincide with the
            # border; require strict interior to avoid false positives).
            if ny < y1 < ny + nh and sx_lo < nx + nw and sx_hi > nx:
                return True
        else:
            # Vertical segment: x constant, y spans [min,max].
            sy_lo, sy_hi = (y1, y2) if y1 <= y2 else (y2, y1)
            if nx < x1 < nx + nw and sy_lo < ny + nh and sy_hi > ny:
                return True
    return False


def _orthogonal_forward(
    src: tuple[int, int, int, int, int],
    tgt: tuple[int, int, int, int, int],
) -> list[tuple[int, int]]:
    """Forward edge: bottom-center of source -> top-center of target, Z-bend
    when columns differ, straight when aligned. Mirrors layout_arch._orthogonal.
    Returns tuples (consistent with the architecture solver contract)."""
    scx, sxx, syy, sw, sh = src
    tcx, txx, tyy, tw, th = tgt
    start = (scx, syy + sh)
    mid_y = (syy + sh + tyy) // 2
    end = (tcx, tyy)
    if scx == tcx:
        return [start, end]
    return [start, (scx, mid_y), (tcx, mid_y), end]


def _gutter_lanes(by_rank: dict[int, list[str]]) -> list[int]:
    """Y-coordinates of the horizontal gutters between consecutive ranks.
    Each lane is the snap of (bottom of rank r + top of rank r+1)/2 — empty
    space by construction, safe for horizontal edge travel."""
    ranks = sorted(by_rank)
    lanes: list[int] = []
    for i in range(len(ranks) - 1):
        y_lo = layout.MARGIN + ranks[i] * (NODE_H + layout.GUTTER_Y) + NODE_H
        y_hi = layout.MARGIN + ranks[i + 1] * (NODE_H + layout.GUTTER_Y)
        lanes.append(layout.snap((y_lo + y_hi) // 2))
    return lanes


def _orthogonal_side(
    src: tuple[int, int, int, int, int],
    tgt: tuple[int, int, int, int, int],
    canvas_w: int,
    gutter_ys: list[int],
    rects: list[tuple[str, int, int, int, int]],
    src_id: str,
    tgt_id: str,
) -> list[tuple[int, int]]:
    """Back / same-rank / blocked-forward edge. Exit source right-center, drop
    to the nearest clear horizontal gutter lane, run out to the right corridor,
    down/up to the target's lane, and into the target's right-center. All
    horizontal travel happens in empty gutters or the right corridor, so the
    route never crosses a node body.

    src/tgt = (cx, x, y, w, h). Returns tuples."""
    corridor = layout.snap(canvas_w - layout.MARGIN // 2)
    _, sxx, syy, sw, sh = src
    _, txx, tyy, tw, th = tgt
    src_mid_y = syy + sh // 2
    tgt_mid_y = tyy + th // 2

    # Find a horizontal lane that is clear of every node (excluding endpoints)
    # for the full span [sxx+sw .. corridor]. Prefer a gutter between the two
    # ranks; fall back to the source/target mid-y if already clear.
    candidates = []
    if src_mid_y != tgt_mid_y:
        lo, hi = (src_mid_y, tgt_mid_y)
        candidates = [g for g in gutter_ys if lo < g < hi or hi < g < lo]
    candidates = candidates + [src_mid_y]
    skip = {src_id, tgt_id}
    lane = src_mid_y
    for cand in candidates:
        if not _seg_hits_node(sxx + sw, cand, corridor, cand, rects, skip):
            lane = cand
            break

    start = (sxx + sw, src_mid_y)
    enter = (txx + tw, tgt_mid_y)  # right-center of target
    if lane == src_mid_y and lane == tgt_mid_y:
        return [start, (corridor, lane), enter]
    if lane == src_mid_y:
        # exit lane clear, drop to target mid along corridor then enter
        return [start, (corridor, lane), (corridor, tgt_mid_y), enter]
    pts = [start, (sxx + sw, lane), (corridor, lane), (corridor, tgt_mid_y), enter]
    return pts
