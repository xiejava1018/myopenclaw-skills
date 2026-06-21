"""Sequence layout: lifeline columns + time-slotted messages + frames.

Structurally different from architecture/flowchart — participants are COLUMNS,
messages are horizontal arrows at increasing y time-slots, lifelines/frames are
decorations. All geometry is deterministic and passes layout.assert_invariants.
"""
import importlib
import pytest

layout = importlib.import_module("layout")
layout_seq = importlib.import_module("layout_seq")


def _seq():
    return {
        "type": "sequence", "style": "enterprise", "title": "下单",
        "participants": [
            {"id": "u", "label": "User", "kind": "actor"},
            {"id": "web", "label": "Web", "kind": "client"},
            {"id": "api", "label": "API", "kind": "service"},
            {"id": "db", "label": "DB", "kind": "database"},
        ],
        "messages": [
            {"from": "u", "to": "web", "label": "点击下单"},
            {"from": "web", "to": "api", "label": "POST /order"},
            {"from": "api", "to": "db", "label": "INSERT", "dashed": False},
            {"from": "db", "to": "api", "label": "ok", "dashed": True},
            {"from": "api", "to": "web", "label": "200", "dashed": True},
        ],
        "frames": [{"kind": "loop", "label": "重试", "from": 3, "to": 4}],
    }


def test_returns_participant_nodes():
    geom = layout_seq.layout_sequence(_seq())
    assert {n["id"] for n in geom["nodes"]} == {"u", "web", "api", "db"}


def test_node_kind_preserved():
    geom = layout_seq.layout_sequence(_seq())
    kinds = {n["id"]: n["kind"] for n in geom["nodes"]}
    assert kinds["u"] == "actor"
    assert kinds["db"] == "database"


def test_is_deterministic():
    assert layout_seq.layout_sequence(_seq()) == layout_seq.layout_sequence(_seq())


def test_passes_all_invariants():
    d = _seq()
    geom = layout_seq.layout_sequence(d)
    labels = {p["id"]: p["label"] for p in d["participants"]}
    layout.assert_invariants(geom, source_nodes=labels)


def test_messages_stack_top_to_bottom():
    geom = layout_seq.layout_sequence(_seq())
    # message edges (have source/target, not just points)
    msg_edges = [e for e in geom["edges"]]
    ys = [e["points"][0][1] for e in msg_edges]
    # messages strictly increase in y by list order
    assert ys == sorted(ys)
    assert len(ys) == 5


def test_dashed_message_is_async_flow():
    geom = layout_seq.layout_sequence(_seq())
    edges = geom["edges"]
    # the 'ok' and '200' messages are dashed -> async flow
    async_flows = [e for e in edges if e.get("flow") == "async"]
    assert len(async_flows) == 2
    # the non-dashed messages are 'data' flow
    data_flows = [e for e in edges if e.get("flow") == "data"]
    assert len(data_flows) == 3


def test_lifelines_emitted_as_decorations():
    geom = layout_seq.layout_sequence(_seq())
    lifelines = [d for d in geom["decorations"] if d.get("kind") == "lifeline"]
    assert len(lifelines) == 4  # one per participant


def test_lifelines_are_vertical():
    geom = layout_seq.layout_sequence(_seq())
    lifelines = [d for d in geom["decorations"] if d.get("kind") == "lifeline"]
    for ll in lifelines:
        # a vertical line: width is tiny, height is the full span
        assert ll["height"] > ll["width"]
        assert ll["height"] > 0
        assert ll["width"] >= 0


def test_frame_emitted_as_decoration():
    geom = layout_seq.layout_sequence(_seq())
    frames = [d for d in geom["decorations"] if d.get("kind") == "frame"]
    assert len(frames) == 1
    f = frames[0]
    assert f["label"] == "重试"
    assert f["width"] > 0 and f["height"] > 0


def test_frame_spans_correct_message_range():
    geom = layout_seq.layout_sequence(_seq())
    msg_edges = geom["edges"]
    # message indexes are 0-based in edges list; frame uses 1-based (3..4)
    y_msg3 = msg_edges[2]["points"][0][1]  # 'INSERT'
    y_msg4 = msg_edges[3]["points"][0][1]  # 'ok'
    f = next(d for d in geom["decorations"] if d.get("kind") == "frame")
    # frame top is at or above msg3, frame bottom is at or below msg4
    assert f["y"] <= y_msg3
    assert f["y"] + f["height"] >= y_msg4


def test_dispatch_works():
    geom = layout.layout(_seq())
    assert geom["type"] == "sequence"
    assert {n["id"] for n in geom["nodes"]} == {"u", "web", "api", "db"}


def test_self_message_loops():
    d = {"type": "sequence", "style": "enterprise", "title": "s",
         "participants": [{"id": "a", "label": "A", "kind": "service"}],
         "messages": [{"from": "a", "to": "a", "label": "self"}]}
    geom = layout_seq.layout_sequence(d)
    e = geom["edges"][0]
    assert len(e["points"]) >= 3  # a loop, not a straight line


def test_columns_evenly_spaced():
    geom = layout_seq.layout_sequence(_seq())
    centers = sorted(n["x"] + n["width"] // 2 for n in geom["nodes"])
    gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
    # all gaps equal (evenly spaced columns)
    assert len(set(gaps)) == 1
    # gap is generous enough to avoid crowding
    assert gaps[0] >= layout.GUTTER_X


def test_header_boxes_in_a_row_at_top():
    geom = layout_seq.layout_sequence(_seq())
    ys = [n["y"] for n in geom["nodes"]]
    # all participant headers share the same top y
    assert len(set(ys)) == 1
    assert ys[0] == layout.MARGIN


def test_decorations_within_canvas():
    geom = layout_seq.layout_sequence(_seq())
    w, h = geom["canvas"]["width"], geom["canvas"]["height"]
    for d in geom["decorations"]:
        assert d["x"] >= 0 and d["y"] >= 0
        assert d["x"] + d["width"] <= w + 1
        assert d["y"] + d["height"] <= h + 1


def test_no_messages_cross_participant_headers():
    """Messages are horizontal arrows below the header row; none may pass
    through a participant header box. Headers sit at top y=MARGIN..MARGIN+NODE_H,
    messages start strictly below that."""
    d = _seq()
    geom = layout_seq.layout_sequence(d)
    header_bottom = max(n["y"] + n["height"] for n in geom["nodes"])
    for e in geom["edges"]:
        for _, py in e["points"]:
            assert py >= header_bottom, (
                f"message point y={py} crosses header row (bottom={header_bottom})"
            )


def test_canvas_height_has_room_below_last_message():
    geom = layout_seq.layout_sequence(_seq())
    last_y = max(e["points"][0][1] for e in geom["edges"])
    assert geom["canvas"]["height"] >= last_y + layout.MARGIN


def test_input_not_mutated():
    import copy
    d = _seq()
    snapshot = copy.deepcopy(d)
    layout_seq.layout_sequence(d)
    assert d == snapshot


def test_two_participants_minimal():
    d = {"type": "sequence", "style": "enterprise", "title": "ping",
         "participants": [
             {"id": "a", "label": "A", "kind": "service"},
             {"id": "b", "label": "B", "kind": "service"},
         ],
         "messages": [{"from": "a", "to": "b", "label": "ping"}]}
    geom = layout_seq.layout_sequence(d)
    labels = {p["id"]: p["label"] for p in d["participants"]}
    layout.assert_invariants(geom, source_nodes=labels)
    assert {n["id"] for n in geom["nodes"]} == {"a", "b"}
