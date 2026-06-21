import importlib
import copy
import pytest

layout = importlib.import_module("layout")
layout_flow = importlib.import_module("layout_flow")


def _flow():
    return {
        "type": "flowchart", "style": "enterprise", "title": "注册",
        "nodes": [
            {"id": "start", "label": "开始", "kind": "terminal"},
            {"id": "input", "label": "输入信息", "kind": "io"},
            {"id": "valid", "label": "有效?", "kind": "decision"},
            {"id": "create", "label": "创建账号", "kind": "process"},
            {"id": "error", "label": "提示错误", "kind": "process"},
            {"id": "end", "label": "结束", "kind": "terminal"},
        ],
        "edges": [
            {"source": "start", "target": "input"},
            {"source": "input", "target": "valid"},
            {"source": "valid", "target": "create", "label": "是"},
            {"source": "valid", "target": "error", "label": "否"},
            {"source": "error", "target": "input"},   # back edge (loop back)
            {"source": "create", "target": "end"},
        ],
    }


def test_layout_returns_all_nodes():
    geom = layout_flow.layout_flowchart(_flow())
    assert {n["id"] for n in geom["nodes"]} == {
        "start", "input", "valid", "create", "error", "end",
    }


def test_layout_is_deterministic():
    a = layout_flow.layout_flowchart(_flow())
    b = layout_flow.layout_flowchart(_flow())
    assert a == b


def test_layout_passes_all_invariants():
    d = _flow()
    geom = layout_flow.layout_flowchart(d)
    labels = {n["id"]: n["label"] for n in d["nodes"]}
    layout.assert_invariants(geom, source_nodes=labels)  # must not raise


def test_ranks_increase_along_edges():
    geom = layout_flow.layout_flowchart(_flow())
    pos = {n["id"]: (n["x"], n["y"]) for n in geom["nodes"]}
    # forward chain goes down: start above input above valid
    assert pos["start"][1] < pos["input"][1] < pos["valid"][1]


def test_edges_are_orthogonal():
    geom = layout_flow.layout_flowchart(_flow())
    assert len(geom["edges"]) > 0
    for e in geom["edges"]:
        pts = e["points"]
        assert len(pts) >= 2
        for i in range(len(pts) - 1):
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            assert x1 == x2 or y1 == y2


def test_cycle_detected_raises():
    bad = {
        "type": "flowchart", "style": "enterprise", "title": "cyc",
        "nodes": [
            {"id": "a", "label": "A", "kind": "process"},
            {"id": "b", "label": "B", "kind": "process"},
        ],
        "edges": [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "a"},
        ],
    }
    with pytest.raises(layout.LayoutError, match="cycle|DAG"):
        layout_flow.layout_flowchart(bad)


def test_dispatch_in_layout_works():
    geom = layout.layout(_flow())
    assert geom["type"] == "flowchart"
    assert {n["id"] for n in geom["nodes"]} == {
        "start", "input", "valid", "create", "error", "end",
    }


def test_does_not_mutate_input():
    """The solver must not mutate the diagram dict handed to it."""
    d = _flow()
    snapshot = copy.deepcopy(d)
    layout_flow.layout_flowchart(d)
    assert d == snapshot, "solver must not mutate input diagram"


def test_node_widths_snapped_to_grid():
    """Every node width must be a multiple of SNAP and wide enough for label."""
    d = _flow()
    geom = layout_flow.layout_flowchart(d)
    widths = {n["id"]: n["width"] for n in geom["nodes"]}
    for n in geom["nodes"]:
        assert n["width"] % layout.SNAP == 0
    # decision node label "有效?" needs a box wide enough (snap-up behavior)
    assert widths["valid"] >= layout.text_width("有效?")


def test_forward_edge_exits_bottom_enters_top():
    """A forward edge (rank increases) must exit src bottom-center and
    enter tgt top-center — the standard Z-bend contract."""
    geom = layout_flow.layout_flowchart(_flow())
    fwd = next(e for e in geom["edges"]
               if e["source"] == "start" and e["target"] == "input")
    src = next(n for n in geom["nodes"] if n["id"] == "start")
    tgt = next(n for n in geom["nodes"] if n["id"] == "input")
    assert fwd["points"][0] == (src["x"] + src["width"] // 2,
                                src["y"] + src["height"])
    assert fwd["points"][-1] == (tgt["x"] + tgt["width"] // 2, tgt["y"])


def test_back_edge_uses_side_routing():
    """A back edge (error -> input) must NOT exit the bottom of the source —
    it routes out the side so it doesn't overlap forward traffic. The first
    point must be on a horizontal edge (right/left center) of the source."""
    geom = layout_flow.layout_flowchart(_flow())
    back = next(e for e in geom["edges"]
                if e["source"] == "error" and e["target"] == "input")
    src = next(n for n in geom["nodes"] if n["id"] == "error")
    p0 = back["points"][0]
    sy_mid = src["y"] + src["height"] // 2
    # The exit point is at the source's vertical mid-line (side exit), and
    # it must NOT be the bottom-center exit used by forward edges.
    assert p0[1] != src["y"] + src["height"], "back edge must not exit bottom"
    assert p0[1] == sy_mid, "back edge must exit at source vertical-center"


def test_isolated_node_lands_at_rank_zero():
    """A node with no edges gets rank 0 (top row)."""
    d = {
        "type": "flowchart", "style": "enterprise", "title": "iso",
        "nodes": [
            {"id": "lonely", "label": "Solo", "kind": "process"},
        ],
        "edges": [],
    }
    geom = layout_flow.layout_flowchart(d)
    assert geom["nodes"][0]["y"] == layout.MARGIN


def _count_edge_node_crossings(geom: dict, step: int = 2, inset: int = 2) -> int:
    """Test oracle: sample points along every edge polyline (excluding the two
    endpoint nodes of that edge) and count how many fall strictly inside a
    non-endpoint node's bounding box (with a small inset so merely touching an
    endpoint node's border does not count).

    A real "edge crosses a node interior" violation yields >= 1 here. Uses
    sampling along each axis-aligned segment so vertical crossings are caught
    as readily as horizontal ones.
    """
    node_by_id = {n["id"]: n for n in geom["nodes"]}
    crossings = 0
    for e in geom["edges"]:
        skip = {e["source"], e["target"]}
        pts = e["points"]
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            length = max(abs(x2 - x1), abs(y2 - y1))
            if length == 0:
                continue
            n_steps = max(1, int(length // step))
            for s in range(n_steps + 1):
                t = s / n_steps
                px = x1 + (x2 - x1) * t
                py = y1 + (y2 - y1) * t
                for nid, n in node_by_id.items():
                    if nid in skip:
                        continue
                    nx, ny, nw, nh = n["x"], n["y"], n["width"], n["height"]
                    if (nx + inset < px < nx + nw - inset
                            and ny + inset < py < ny + nh - inset):
                        crossings += 1
    return crossings


def test_side_routed_edge_does_not_cross_rank_sibling():
    """Regression: a back/side edge whose target shares its rank with a
    rightward sibling must not have its enter-segment cut through that sibling.

    The bug: _orthogonal_side routed the final horizontal enter-segment at
    tgt_mid_y (the vertical CENTER of the target's rank) across the full width
    from the right corridor to the target's right edge. When a sibling node
    sits between target and corridor at the same rank, that enter-segment
    crosses straight through the sibling's interior.

    Fixture: 'a' and 'b' share rank 1 (both reached from 'start'); 'c' is a
    rank-2 descendant of 'a'. The back edge c->a makes 'a' a side-routed
    target, and 'b' sits to its right — exactly the trigger.
    """
    d = {
        "type": "flowchart", "style": "enterprise", "title": "side-cross",
        "nodes": [
            {"id": "start", "label": "Start", "kind": "terminal"},
            {"id": "a", "label": "Step A", "kind": "process"},   # rank 1 (back-edge target)
            {"id": "b", "label": "Step B", "kind": "process"},   # rank 1, rightward sibling of 'a'
            {"id": "c", "label": "Step C", "kind": "process"},   # rank 2, descendant of 'a'
        ],
        "edges": [
            {"source": "start", "target": "a"},
            {"source": "start", "target": "b"},   # forces 'b' into 'a's rank, to its right
            {"source": "a", "target": "c"},
            {"source": "c", "target": "a"},       # back edge → 'a' side-routed, sibling 'b' crossed
        ],
    }
    geom = layout_flow.layout_flowchart(d)
    # Verify NO edge segment passes through a non-endpoint node's interior.
    crossings = _count_edge_node_crossings(geom)
    assert crossings == 0, f"edge crosses a node interior: {crossings} crossing(s)"


def test_flow_defaults_to_control():
    """Flowchart edges default to 'control' flow when flow field absent."""
    geom = layout_flow.layout_flowchart(_flow())
    for e in geom["edges"]:
        assert e["flow"] == "control"
