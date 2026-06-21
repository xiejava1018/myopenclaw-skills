import importlib
styles = importlib.import_module("styles")


def test_known_styles_exist():
    for s in ("enterprise", "flat", "notion", "claude", "openai"):
        assert s in styles.STYLES


def test_cell_style_enterprise_database():
    s = styles.cell_style(kind="database", style_name="enterprise", shape="cylinder3")
    assert "shape=cylinder3" in s
    assert "fillColor=" in s
    assert "strokeColor=" in s
    assert "fontSize=" in s


def test_cell_style_unknown_kind_falls_back():
    s = styles.cell_style(kind="bogus", style_name="enterprise", shape="rounded_rect")
    assert "fillColor=" in s  # uses default palette color


def test_canvas_style_enterprise():
    cs = styles.canvas_style("enterprise")
    assert cs["background"] == "#ffffff"


def test_claude_has_warm_background():
    assert styles.STYLES["claude"]["background"] == "#f8f6f3"


def test_enterprise_has_no_shadow():
    assert styles.STYLES["enterprise"]["shadow"] is False


def test_edge_style_data_is_blue_solid():
    s = styles.edge_style("data", "enterprise")
    assert "edgeStyle=orthogonalEdgeStyle" in s
    assert "2563eb" in s  # blue
    assert "dashed=0" in s


def test_edge_style_async_is_dashed():
    s = styles.edge_style("async", "enterprise")
    assert "dashed=1" in s
