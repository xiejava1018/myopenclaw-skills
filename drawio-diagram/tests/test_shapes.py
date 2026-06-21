import importlib
shapes = importlib.import_module("shapes")


def test_database_is_cylinder():
    assert shapes.shape_for("database") == "cylinder3"

def test_decision_is_rhombus():
    assert shapes.shape_for("decision") == "rhombus"

def test_terminal_is_pill():
    assert shapes.shape_for("terminal") == "rounded_rect"

def test_unknown_kind_defaults_to_rounded_rect():
    assert shapes.shape_for("mystery") == "rounded_rect"

def test_shape_for_returns_expected_shape_for_each_kind():
    # Source of truth: shapes.KIND_TO_SHAPE. If the table changes, update here too.
    expected = {
        "client": "rounded_rect", "browser": "rounded_rect",
        "service": "rounded_rect", "api": "hexagon",
        "database": "cylinder3", "cache": "cylinder3",
        "vectorstore": "cylinder3", "queue": "process",
        "stream": "process", "external": "cloud", "cloud": "cloud",
        "llm": "rounded_rect", "actor": "actor",
        "process": "rounded_rect", "decision": "rhombus",
        "terminal": "rounded_rect", "io": "parallelogram",
        "start": "rounded_rect", "end": "rounded_rect",
    }
    for kind, shape in expected.items():
        assert shapes.shape_for(kind) == shape
