import importlib
import pytest
layout = importlib.import_module("layout")
layout_arch = importlib.import_module("layout_arch")


def _diagram():
    return {
        "type": "architecture", "style": "enterprise", "title": "T", "direction": "tb",
        "layers": [
            {"id": "L0", "label": "客户端", "nodes": ["web", "app"]},
            {"id": "L1", "label": "服务", "nodes": ["api"]},
            {"id": "L2", "label": "存储", "nodes": ["db"]},
        ],
        "nodes": [
            {"id": "web", "label": "Web Client", "kind": "client"},
            {"id": "app", "label": "Mobile App", "kind": "client"},
            {"id": "api", "label": "API Gateway", "kind": "api"},
            {"id": "db", "label": "PostgreSQL", "kind": "database"},
        ],
        "edges": [
            {"source": "web", "target": "api", "flow": "data"},
            {"source": "app", "target": "api", "flow": "data"},
            {"source": "api", "target": "db", "flow": "data"},
        ],
    }


def test_layout_returns_all_nodes():
    geom = layout_arch.layout_architecture(_diagram())
    ids = {n["id"] for n in geom["nodes"]}
    assert ids == {"web", "app", "api", "db"}


def test_layout_is_deterministic():
    a = layout_arch.layout_architecture(_diagram())
    b = layout_arch.layout_architecture(_diagram())
    assert a == b


def test_layout_passes_all_invariants():
    d = _diagram()
    geom = layout_arch.layout_architecture(d)
    labels = {n["id"]: n["label"] for n in d["nodes"]}
    layout.assert_invariants(geom, source_nodes=labels)  # must not raise


def test_layers_ordered_top_to_bottom():
    geom = layout_arch.layout_architecture(_diagram())
    y = {n["id"]: n["y"] for n in geom["nodes"]}
    assert y["web"] < y["api"] < y["db"]
    # app and web share a layer
    assert y["web"] == y["app"]


def test_edges_have_orthogonal_points():
    geom = layout_arch.layout_architecture(_diagram())
    for e in geom["edges"]:
        assert len(e["points"]) >= 2
        pts = e["points"]
        for i in range(len(pts) - 1):
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            assert x1 == x2 or y1 == y2  # orthogonal segments


def test_containers_one_per_layer():
    geom = layout_arch.layout_architecture(_diagram())
    assert len(geom["containers"]) == 3
    cids = {c["id"] for c in geom["containers"]}
    assert cids == {"L0", "L1", "L2"}


def test_dispatch_in_layout_now_works():
    """layout() should now resolve the lazy import and call layout_arch."""
    geom = layout.layout(_diagram())
    assert geom["type"] == "architecture"
    assert {n["id"] for n in geom["nodes"]} == {"web", "app", "api", "db"}


def test_node_width_snapped_up_for_non_grid_text_width():
    """Regression: a label whose text_width is not a multiple of SNAP must get a
    box snapped UP to the next grid line (text_width 144 -> 160), never rounded
    down, so the box always holds the label. Caught by assert_width_from_text."""
    d = {
        "type": "architecture", "style": "enterprise", "title": "T", "direction": "tb",
        "layers": [{"id": "L0", "label": "x", "nodes": ["rag"]}],
        "nodes": [{"id": "rag", "label": "RAG Orchestrator", "kind": "service"}],
        "edges": [],
    }
    # sanity: this label's text_width is deliberately not a multiple of SNAP
    tw = layout.text_width("RAG Orchestrator")
    assert tw % layout.SNAP != 0, "fixture label must have non-grid text_width"
    geom = layout_arch.layout_architecture(d)
    n = geom["nodes"][0]
    assert n["width"] >= tw, "node too narrow for label"
    assert n["width"] % layout.SNAP == 0, "node width must be grid-aligned"


def test_non_tb_direction_raises():
    bad = _diagram()
    bad["direction"] = "lr"
    with pytest.raises(layout.LayoutError, match="tb"):
        layout_arch.layout_architecture(bad)


def test_empty_layer_is_skipped_cleanly():
    """An empty layer must not produce a malformed container or zero-width geometry."""
    d = {
        "type": "architecture", "style": "enterprise", "title": "T", "direction": "tb",
        "layers": [
            {"id": "L0", "label": "Empty", "nodes": []},
            {"id": "L1", "label": "Real", "nodes": ["only"]},
        ],
        "nodes": [{"id": "only", "label": "Solo", "kind": "service"}],
        "edges": [],
    }
    geom = layout_arch.layout_architecture(d)
    container_ids = {c["id"] for c in geom["containers"]}
    assert "L0" not in container_ids, "empty layer should not emit a container"
    assert "L1" in container_ids
    # Real node should land at MARGIN (the empty layer shouldn't shift it)
    assert geom["nodes"][0]["y"] == layout.MARGIN
    # All containers have positive width and height
    for c in geom["containers"]:
        assert c["width"] > 0 and c["height"] > 0


def test_orthogonal_routes_are_3_segment_z_bend_for_horizontal_offsets():
    """Cross-layer edges with different x-positions must produce 3-segment Z-bends.

    Three nodes in the top layer force a left/center/right column split so the
    bottom layer's single node (c) only aligns in x with the leftmost top node.
    Edges from the center and right nodes thus have sx != tx and must take the
    Z-bend branch (3 segments)."""
    d = {
        "type": "architecture", "style": "enterprise", "title": "T", "direction": "tb",
        "layers": [
            {"id": "L0", "label": "top", "nodes": ["a", "b", "d"]},
            {"id": "L1", "label": "bot", "nodes": ["c"]},
        ],
        "nodes": [
            {"id": "a", "label": "Alpha", "kind": "service"},
            {"id": "b", "label": "Beta", "kind": "service"},
            {"id": "c", "label": "Gamma", "kind": "service"},
            {"id": "d", "label": "Delta", "kind": "service"},
        ],
        "edges": [
            {"source": "b", "target": "c"},  # sx=350, tx=130 → Z-bend
            {"source": "d", "target": "c"},  # sx=570, tx=130 → Z-bend
        ],
    }
    geom = layout_arch.layout_architecture(d)
    for edge in geom["edges"]:
        pts = edge["points"]
        assert len(pts) == 4, (
            f"expected 4 points (3 segments) for Z-bend {edge['source']}->"
            f"{edge['target']}, got {len(pts)}"
        )
        # All segments must remain orthogonal
        for i in range(len(pts) - 1):
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            assert x1 == x2 or y1 == y2
        # First segment exits source downward; last segment enters target from above
        src_node = next(n for n in geom["nodes"] if n["id"] == edge["source"])
        tgt_node = next(n for n in geom["nodes"] if n["id"] == edge["target"])
        assert pts[0] == (src_node["x"] + src_node["width"] // 2,
                          src_node["y"] + src_node["height"])
        assert pts[-1] == (tgt_node["x"] + tgt_node["width"] // 2, tgt_node["y"])


def test_orthogonal_centers_tuple_uses_5_fields():
    """White-box: after the cy cleanup, _orthogonal must unpack a 5-tuple.
    We exercise the function directly with a 5-tuple to lock the contract."""
    # (cx, x, y, w, h)
    src = (130, 60, 60, 140, 80)
    tgt = (350, 280, 180, 140, 80)
    pts = layout_arch._orthogonal(src, tgt)
    assert len(pts) == 4
    # Vertical down, horizontal, vertical down — the Z-bend
    assert pts[0] == (130, 140)   # bottom-center of source (cx, y+h)
    assert pts[-1] == (350, 180)  # top-center of target (tx, y)
    # The middle two points share a y (mid_y) and route from sx to tx
    assert pts[1][1] == pts[2][1]
    assert pts[1][0] == 130
    assert pts[2][0] == 350
