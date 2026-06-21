"""Deterministic layout engine: constants, invariants, dispatch."""

# spacing constants (single source of truth, tunable)
NODE_MIN_W = 140
NODE_H = 76
GUTTER_X = 80
GUTTER_Y = 120
MARGIN = 60
SNAP = 20
MIN_GAP = 24

PX_PER_CHAR = 7
TEXT_PADDING = 32


class LayoutError(Exception):
    pass


def text_width(label: str) -> int:
    return max(NODE_MIN_W, len(label) * PX_PER_CHAR + TEXT_PADDING)


def snap(value: int) -> int:
    return round(value / SNAP) * SNAP


def empty_geometry(type_: str, style: str, title: str) -> dict:
    return {
        "type": type_, "title": title, "style": style,
        "canvas": {"width": 0, "height": 0},
        "nodes": [], "edges": [], "containers": [], "decorations": [],
    }


def _rects(nodes: list[dict]) -> list[tuple[int, int, int, int]]:
    return [(n["x"], n["y"], n["width"], n["height"]) for n in nodes]


def _overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int], gap: int) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax < bx + bw + gap and ax + aw + gap > bx
            and ay < by + bh + gap and ay + ah + gap > by)


def assert_no_overlap(geom: dict) -> None:
    rects = _rects(geom["nodes"])
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if _overlaps(rects[i], rects[j], MIN_GAP):
                raise LayoutError(
                    f"nodes overlap: {geom['nodes'][i]['id']} <-> {geom['nodes'][j]['id']}"
                )


def assert_in_bounds(geom: dict) -> None:
    w, h = geom["canvas"]["width"], geom["canvas"]["height"]
    for n in geom["nodes"]:
        # +1 absorbs float→int rounding from snap() (current values are ints,
        # but keeps the check robust against future fractional coordinates and
        # avoids off-by-one false positives at the canvas boundary).
        if (n["x"] < 0 or n["y"] < 0
                or n["x"] + n["width"] > w + 1
                or n["y"] + n["height"] > h + 1):
            raise LayoutError(f"node {n['id']} out of canvas bounds")


def assert_snapped(geom: dict) -> None:
    for n in geom["nodes"]:
        for key in ("x", "y"):
            if n[key] % SNAP != 0:
                raise LayoutError(f"node {n['id']} {key}={n[key]} not snapped to {SNAP}")


def assert_width_from_text(geom: dict, source_nodes: dict[str, str]) -> None:
    """source_nodes: {id: label}. Verify each node width >= text_width(label)."""
    for n in geom["nodes"]:
        label = source_nodes.get(n["id"], "")
        if n["width"] < text_width(label):
            raise LayoutError(f"node {n['id']} too narrow for label {label!r}")


def assert_invariants(geom: dict, source_nodes: dict[str, str] | None = None) -> None:
    """Full 5-invariant check (call after every solver)."""
    assert_no_overlap(geom)
    assert_in_bounds(geom)
    assert_snapped(geom)
    if source_nodes is not None:
        assert_width_from_text(geom, source_nodes)
    # determinism is tested by comparing two runs of a solver.


def layout(diagram: dict) -> dict:
    """Dispatch to per-type solver. Raises LayoutError on invariant violation
    or if no solver exists yet for the type."""
    t = diagram["type"]
    if t == "architecture":
        from layout_arch import layout_architecture  # lazy; created in Phase 1b
        return layout_architecture(diagram)
    if t == "flowchart":
        from layout_flow import layout_flowchart  # lazy; created in Phase 2
        return layout_flowchart(diagram)
    raise LayoutError(f"no solver yet for type {t!r}")
