import importlib
import pytest
layout = importlib.import_module("layout")


def test_text_width_respects_min():
    assert layout.text_width("Hi") == layout.NODE_MIN_W

def test_text_width_grows_with_label():
    short = layout.text_width("DB")
    long = layout.text_width("Vector Database Cluster")
    assert long > short

def test_snap_rounds_to_grid():
    assert layout.snap(17) == 20
    assert layout.snap(10) == 0
    assert layout.snap(23) == 20

def test_geometry_shape():
    geom = layout.empty_geometry("architecture", "enterprise", "T")
    assert set(geom) == {"type", "title", "style", "canvas", "nodes",
                         "edges", "containers", "decorations"}
    assert geom["canvas"] == {"width": 0, "height": 0}

def test_assert_no_overlap_passes_for_disjoint():
    geom = layout.empty_geometry("architecture", "enterprise", "T")
    geom["nodes"] = [
        {"id":"a","x":0,"y":0,"width":100,"height":50},
        {"id":"b","x":200,"y":0,"width":100,"height":50},
    ]
    layout.assert_no_overlap(geom)

def test_assert_no_overlap_fails_for_overlapping():
    geom = layout.empty_geometry("architecture", "enterprise", "T")
    geom["nodes"] = [
        {"id":"a","x":0,"y":0,"width":100,"height":50},
        {"id":"b","x":50,"y":0,"width":100,"height":50},
    ]
    with pytest.raises(layout.LayoutError):
        layout.assert_no_overlap(geom)

def test_assert_in_bounds_passes():
    geom = layout.empty_geometry("architecture", "enterprise", "T")
    geom["canvas"] = {"width": 500, "height": 300}
    geom["nodes"] = [{"id":"a","x":10,"y":10,"width":100,"height":50}]
    layout.assert_in_bounds(geom)

def test_assert_in_bounds_fails_on_overflow():
    geom = layout.empty_geometry("architecture", "enterprise", "T")
    geom["canvas"] = {"width": 100, "height": 100}
    geom["nodes"] = [{"id":"a","x":10,"y":10,"width":200,"height":50}]
    with pytest.raises(layout.LayoutError):
        layout.assert_in_bounds(geom)

def test_assert_snapped_checks_x_y():
    # x/y must be snapped to SNAP; width/height are derived (not required to be multiples)
    geom = layout.empty_geometry("architecture", "enterprise", "T")
    geom["nodes"] = [{"id":"a","x":20,"y":40,"width":140,"height":76}]
    layout.assert_snapped(geom)
    bad = layout.empty_geometry("architecture", "enterprise", "T")
    bad["nodes"] = [{"id":"a","x":17,"y":40,"width":140,"height":76}]
    with pytest.raises(layout.LayoutError):
        layout.assert_snapped(bad)

def test_assert_width_from_text():
    geom = layout.empty_geometry("architecture", "enterprise", "T")
    geom["nodes"] = [{"id":"a","x":0,"y":0,"width":layout.text_width("Hello"),"height":76}]
    layout.assert_width_from_text(geom, {"a": "Hello"})
    narrow = layout.empty_geometry("architecture", "enterprise", "T")
    narrow["nodes"] = [{"id":"a","x":0,"y":0,"width":10,"height":76}]
    with pytest.raises(layout.LayoutError):
        layout.assert_width_from_text(narrow, {"a": "Hello"})

def test_dispatch_raises_for_unimplemented_type():
    with pytest.raises(layout.LayoutError, match="no solver"):
        layout.layout({"type": "state", "title": "x", "style": "enterprise",
                       "states": [], "transitions": [], "initial": ""})
