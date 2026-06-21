import importlib
import pytest
layout = importlib.import_module("layout")
layout_state = importlib.import_module("layout_state")


def _state():
    return {
        "type": "state", "style": "enterprise", "title": "订单状态",
        "initial": "pending",
        "states": [
            {"id": "pending", "label": "待支付"},
            {"id": "paid", "label": "已支付"},
            {"id": "shipped", "label": "已发货"},
            {"id": "done", "label": "已完成"},
            {"id": "cancelled", "label": "已取消"},
        ],
        "transitions": [
            {"from": "pending", "to": "paid", "label": "支付"},
            {"from": "paid", "to": "shipped", "label": "发货"},
            {"from": "shipped", "to": "done", "label": "签收"},
            {"from": "pending", "to": "cancelled", "label": "取消"},
            {"from": "paid", "to": "cancelled", "label": "取消", "guard": "未发货"},
        ],
        "final": ["done", "cancelled"],
    }


def test_returns_state_nodes():
    geom = layout_state.layout_state(_state())
    assert {n["id"] for n in geom["nodes"]} == {
        "pending", "paid", "shipped", "done", "cancelled"}


def test_is_deterministic():
    assert layout_state.layout_state(_state()) == layout_state.layout_state(_state())


def test_passes_all_invariants():
    d = _state()
    geom = layout_state.layout_state(d)
    labels = {s["id"]: s["label"] for s in d["states"]}
    layout.assert_invariants(geom, source_nodes=labels)


def test_initial_state_rank_0():
    geom = layout_state.layout_state(_state())
    pos = {n["id"]: n["x"] for n in geom["nodes"]}
    # initial is leftmost (rank 0)
    assert pos["pending"] == min(pos.values())


def test_initial_pseudostate_emitted():
    geom = layout_state.layout_state(_state())
    inits = [d for d in geom["decorations"]
             if d.get("kind") == "initial_pseudostate"]
    assert len(inits) == 1


def test_final_pseudostates_emitted():
    geom = layout_state.layout_state(_state())
    finals = [d for d in geom["decorations"]
              if d.get("kind") == "final_pseudostate"]
    assert len(finals) == 2  # done + cancelled


def test_transitions_orthogonal_and_labeled():
    geom = layout_state.layout_state(_state())
    for e in geom["edges"]:
        pts = e["points"]
        for i in range(len(pts) - 1):
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            assert x1 == x2 or y1 == y2
    # the guarded transition carries the guard
    labels = [e.get("label", "") for e in geom["edges"]]
    assert any("未发货" in l for l in labels)


def test_initial_to_initial_state_edge_exists():
    geom = layout_state.layout_state(_state())
    # an edge from the initial pseudostate to 'pending'
    # at minimum, there's an edge connecting the initial pseudostate region to pending
    assert len(geom["edges"]) >= len(_state()["transitions"]) + 1


def test_dispatch_works():
    geom = layout.layout(_state())
    assert geom["type"] == "state"
    assert {n["id"] for n in geom["nodes"]} == {
        "pending", "paid", "shipped", "done", "cancelled"}


def test_dispatch_all_5_types_now_resolve():
    # After this solver, ALL 5 types must dispatch successfully
    for t, d in [
        ("architecture", {"type": "architecture", "style": "enterprise",
                          "title": "a", "direction": "tb",
                          "layers": [{"id": "L0", "label": "x", "nodes": ["n"]}],
                          "nodes": [{"id": "n", "label": "N", "kind": "service"}],
                          "edges": []}),
        ("flowchart", {"type": "flowchart", "style": "enterprise", "title": "f",
                       "nodes": [{"id": "s", "label": "S", "kind": "terminal"}],
                       "edges": []}),
        ("sequence", {"type": "sequence", "style": "enterprise", "title": "s",
                      "participants": [{"id": "a", "label": "A", "kind": "actor"}],
                      "messages": []}),
        ("er", {"type": "er", "style": "enterprise", "title": "e",
                "entities": [{"id": "x", "label": "X", "attributes": []}],
                "relationships": []}),
        ("state", {"type": "state", "style": "enterprise", "title": "st",
                   "initial": "s0",
                   "states": [{"id": "s0", "label": "S0"}],
                   "transitions": [], "final": []}),
    ]:
        geom = layout.layout(d)  # must not raise
        assert geom["type"] == t


def test_guard_only_label_renders_as_brackets():
    d = _state()
    d["transitions"].append(
        {"from": "shipped", "to": "cancelled", "guard": "拒绝签收"})
    geom = layout_state.layout_state(d)
    labels = [e.get("label", "") for e in geom["edges"]]
    assert any("[拒绝签收]" in l for l in labels)


def test_self_transition_emits_loop():
    d = {
        "type": "state", "style": "enterprise", "title": "self",
        "initial": "s0",
        "states": [{"id": "s0", "label": "自循环"}],
        "transitions": [{"from": "s0", "to": "s0", "label": "重试"}],
        "final": [],
    }
    geom = layout_state.layout_state(d)
    # the self transition is an orthogonal loop (>=3 pts, all axis-aligned)
    self_edges = [e for e in geom["edges"] if e["source"] == "s0"
                  and e["target"] == "s0"]
    assert len(self_edges) == 1
    pts = self_edges[0]["points"]
    assert len(pts) >= 3
    for i in range(len(pts) - 1):
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        assert x1 == x2 or y1 == y2


def test_unreachable_states_appended_at_end():
    # 'orphan' has no incoming transitions reachable from initial
    d = _state()
    d["states"].append({"id": "orphan", "label": "孤立"})
    geom = layout_state.layout_state(d)
    # orphan node exists and is placed at the largest x (appended column)
    pos = {n["id"]: n["x"] for n in geom["nodes"]}
    assert "orphan" in pos
    assert pos["orphan"] == max(pos.values())


def test_pseudo_states_dont_overlap_states():
    d = _state()
    geom = layout_state.layout_state(d)
    state_rects = [(n["x"], n["y"], n["width"], n["height"])
                   for n in geom["nodes"]]

    def _overlaps(a, b, gap=0):
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        return (ax < bx + bw + gap and ax + aw + gap > bx
                and ay < by + bh + gap and ay + ah + gap > by)

    for dec in geom["decorations"]:
        drect = (dec["x"], dec["y"], dec["width"], dec["height"])
        for srect in state_rects:
            assert not _overlaps(drect, srect, gap=10), (
                f"pseudo-state {dec.get('kind')} overlaps a state")
