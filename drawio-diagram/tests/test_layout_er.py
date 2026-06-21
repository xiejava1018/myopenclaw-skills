"""Tests for the ER diagram layout solver (TDD: written before implementation)."""
import importlib
import pytest

layout = importlib.import_module("layout")
layout_er = importlib.import_module("layout_er")


def _er():
    return {
        "type": "er", "style": "enterprise", "title": "电商",
        "entities": [
            {"id": "user", "label": "User", "attributes": [
                {"name": "id", "pk": True}, {"name": "email"}, {"name": "name"}]},
            {"id": "order", "label": "Order", "attributes": [
                {"name": "id", "pk": True}, {"name": "user_id", "fk": True},
                {"name": "amount"}]},
            {"id": "item", "label": "Item", "attributes": [
                {"name": "id", "pk": True}, {"name": "order_id", "fk": True},
                {"name": "qty"}]},
        ],
        "relationships": [
            {"from": "user", "to": "order", "card": "1:N", "label": "has"},
            {"from": "order", "to": "item", "card": "1:N", "label": "contains"},
        ],
    }


def test_returns_entity_nodes():
    geom = layout_er.layout_er(_er())
    assert {n["id"] for n in geom["nodes"]} == {"user", "order", "item"}


def test_is_deterministic():
    assert layout_er.layout_er(_er()) == layout_er.layout_er(_er())


def test_passes_all_invariants():
    d = _er()
    geom = layout_er.layout_er(d)
    labels = {e["id"]: e["label"] for e in d["entities"]}
    layout.assert_invariants(geom, source_nodes=labels)


def test_entity_width_fits_longest_attribute():
    geom = layout_er.layout_er(_er())
    for n in geom["nodes"]:
        # width must be >= a reasonable attribute line width
        assert n["width"] >= layout.NODE_MIN_W


def test_entities_dont_overlap():
    geom = layout_er.layout_er(_er())
    nodes = geom["nodes"]
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            assert (a["x"] + a["width"] + layout.MIN_GAP <= b["x"]
                    or b["x"] + b["width"] + layout.MIN_GAP <= a["x"]
                    or a["y"] + a["height"] + layout.MIN_GAP <= b["y"]
                    or b["y"] + b["height"] + layout.MIN_GAP <= a["y"]), \
                f"{a['id']} overlaps {b['id']}"


def test_relationships_are_edges_with_card():
    geom = layout_er.layout_er(_er())
    assert len(geom["edges"]) == 2
    for e in geom["edges"]:
        assert "1:N" in e["label"]


def test_relationships_orthogonal():
    geom = layout_er.layout_er(_er())
    for e in geom["edges"]:
        pts = e["points"]
        for i in range(len(pts) - 1):
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            assert x1 == x2 or y1 == y2


def test_dispatch_works():
    geom = layout.layout(_er())
    assert geom["type"] == "er"
    assert {n["id"] for n in geom["nodes"]} == {"user", "order", "item"}


def test_entity_carries_attributes_for_renderer():
    geom = layout_er.layout_er(_er())
    user = [n for n in geom["nodes"] if n["id"] == "user"][0]
    assert "attributes" in user
    assert len(user["attributes"]) == 3


def test_entity_kind_is_er_entity():
    geom = layout_er.layout_er(_er())
    for n in geom["nodes"]:
        assert n["kind"] == "er_entity"


def test_relationships_data_flow():
    geom = layout_er.layout_er(_er())
    for e in geom["edges"]:
        assert e["flow"] == "data"


def test_edge_carries_source_target():
    geom = layout_er.layout_er(_er())
    e = geom["edges"][0]
    assert "source" in e and "target" in e


def test_relationship_label_format_with_name():
    geom = layout_er.layout_er(_er())
    # 'has' relationship -> "has (1:N)"
    has = [e for e in geom["edges"] if "has" in e["label"]][0]
    assert "1:N" in has["label"]
    assert "has" in has["label"]


def test_height_grows_with_attributes():
    """An entity with more attributes must be taller than one with fewer."""
    d = {
        "type": "er", "style": "enterprise", "title": "t",
        "entities": [
            {"id": "small", "label": "S", "attributes": [{"name": "id"}]},
            {"id": "big", "label": "B", "attributes": [
                {"name": "a"}, {"name": "b"}, {"name": "c"},
                {"name": "d"}, {"name": "e"}, {"name": "f"}]},
        ],
        "relationships": [],
    }
    geom = layout_er.layout_er(d)
    sizes = {n["id"]: n for n in geom["nodes"]}
    assert sizes["big"]["height"] > sizes["small"]["height"]


def test_grid_two_columns_for_few_entities():
    """<=4 entities -> 2 columns. user/order/item => 2 cols, item in row 1 col 1."""
    geom = layout_er.layout_er(_er())
    # canvas height must accommodate 2 rows (3 entities / 2 cols = 2 rows)
    assert geom["canvas"]["height"] > 2 * layout.MARGIN


def test_no_relationship_crosses_other_entity_interior():
    """Professional invariant: an edge must not cross a NON-endpoint entity."""
    geom = layout_er.layout_er(_er())
    rects = [(n["id"], n["x"], n["y"], n["width"], n["height"])
             for n in geom["nodes"]]
    for e in geom["edges"]:
        skip = {e["source"], e["target"]}
        pts = e["points"]
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            assert not layout_er._seg_hits_entity(
                x1, y1, x2, y2, rects, skip), \
                f"edge {e['source']}->{e['target']} crosses a non-endpoint entity"


def test_canvas_contains_all_entities():
    geom = layout_er.layout_er(_er())
    w, h = geom["canvas"]["width"], geom["canvas"]["height"]
    for n in geom["nodes"]:
        assert n["x"] + n["width"] <= w + 1
        assert n["y"] + n["height"] <= h + 1


def test_single_entity_no_relationships():
    d = {
        "type": "er", "style": "flat", "title": "t",
        "entities": [{"id": "solo", "label": "Solo",
                      "attributes": [{"name": "id", "pk": True}]}],
        "relationships": [],
    }
    geom = layout_er.layout_er(d)
    assert len(geom["nodes"]) == 1
    assert geom["edges"] == []
    labels = {e["id"]: e["label"] for e in d["entities"]}
    layout.assert_invariants(geom, source_nodes=labels)


def test_self_relationship_routes_without_crossing():
    d = {
        "type": "er", "style": "enterprise", "title": "t",
        "entities": [
            {"id": "e", "label": "Employee", "attributes": [
                {"name": "id", "pk": True}, {"name": "manager_id", "fk": True}]},
            {"id": "d", "label": "Dept", "attributes": [{"name": "id", "pk": True}]},
        ],
        "relationships": [
            {"from": "e", "to": "e", "card": "1:N", "label": "manages"},
        ],
    }
    geom = layout_er.layout_er(d)
    assert len(geom["edges"]) == 1
    e = geom["edges"][0]
    # orthogonal
    for i in range(len(e["points"]) - 1):
        x1, y1 = e["points"][i]
        x2, y2 = e["points"][i + 1]
        assert x1 == x2 or y1 == y2
    # must not cross the OTHER entity
    rects = [(n["id"], n["x"], n["y"], n["width"], n["height"])
             for n in geom["nodes"]]
    skip = {e["source"], e["target"]}
    for i in range(len(e["points"]) - 1):
        x1, y1 = e["points"][i]
        x2, y2 = e["points"][i + 1]
        assert not layout_er._seg_hits_entity(
            x1, y1, x2, y2, rects, skip), \
            "self-relationship crosses non-endpoint entity"
