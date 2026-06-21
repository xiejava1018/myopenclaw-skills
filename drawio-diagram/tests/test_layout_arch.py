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


def test_non_tb_direction_raises():
    bad = _diagram()
    bad["direction"] = "lr"
    with pytest.raises(layout.LayoutError, match="tb"):
        layout_arch.layout_architecture(bad)
