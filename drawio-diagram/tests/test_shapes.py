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

def test_shape_for_returns_string_for_all_documented_kinds():
    for k in ["client","service","api","database","cache","vectorstore",
              "queue","external","cloud","llm","actor","process","decision",
              "terminal","io","browser"]:
        assert isinstance(shapes.shape_for(k), str)
