import importlib
import pytest

schema = importlib.import_module("schema")
SchemaError = schema.SchemaError


ARCH_OK = {
    "type": "architecture", "style": "enterprise", "title": "Demo",
    "layers": [{"id": "L0", "label": "客户端", "nodes": ["web", "gw"]}],
    "nodes": [{"id": "web", "label": "Web", "kind": "client"},
              {"id": "gw", "label": "Gateway", "kind": "api"}],
    "edges": [{"source": "web", "target": "gw", "flow": "data"}],
}
FLOW = {
    "type": "flowchart", "style": "enterprise", "title": "F",
    "nodes": [{"id": "s", "label": "Start", "kind": "terminal"},
              {"id": "e", "label": "End", "kind": "terminal"}],
    "edges": [{"source": "s", "target": "e"}],
}
SEQ = {
    "type": "sequence", "style": "enterprise", "title": "S",
    "participants": [{"id": "a", "label": "A", "kind": "actor"},
                     {"id": "b", "label": "B", "kind": "service"}],
    "messages": [{"from": "a", "to": "b", "label": "hi"}],
}
ER_OK = {
    "type": "er", "style": "enterprise", "title": "E",
    "entities": [{"id": "user", "label": "User",
                  "attributes": [{"name": "id", "pk": True}]},
                 {"id": "order", "label": "Order",
                  "attributes": [{"name": "id", "pk": True}]}],
    "relationships": [{"from": "user", "to": "order", "card": "1:N"}],
}
STATE = {
    "type": "state", "style": "enterprise", "title": "St",
    "initial": "s0",
    "states": [{"id": "s0", "label": "A"}, {"id": "s1", "label": "B"}],
    "transitions": [{"from": "s0", "to": "s1", "label": "go"}],
    "final": ["s1"],
}
# Used only for rejection tests (edge references undefined node 'gw'):
ARCH = {
    "type": "architecture", "style": "enterprise", "title": "Demo",
    "layers": [{"id": "L0", "label": "客户端", "nodes": ["web"]}],
    "nodes": [{"id": "web", "label": "Web", "kind": "client"}],
    "edges": [{"source": "web", "target": "gw", "flow": "data"}],
}
ER = {
    "type": "er", "style": "enterprise", "title": "E",
    "entities": [{"id": "user", "label": "User",
                  "attributes": [{"name": "id", "pk": True}]}],
    "relationships": [{"from": "user", "to": "order", "card": "1:N"}],
}


def test_unknown_type_rejected():
    with pytest.raises(SchemaError, match="unknown type"):
        schema.validate({"type": "bogus"})


def test_missing_type_rejected():
    with pytest.raises(SchemaError, match="type"):
        schema.validate({"title": "x"})


def test_each_valid_type_passes():
    for d in (ARCH_OK, FLOW, SEQ, ER_OK, STATE):
        schema.validate(d)  # must not raise


def test_missing_required_field_reported():
    bad = {"type": "architecture", "title": "x", "style": "enterprise"}
    with pytest.raises(SchemaError, match="missing"):
        schema.validate(bad)


def test_edge_refs_unknown_node_rejected():
    with pytest.raises(SchemaError, match="unknown node"):
        schema.validate(ARCH)


def test_layer_node_must_exist():
    bad = {**ARCH, "layers": [{"id": "L0", "label": "x", "nodes": ["ghost"]}]}
    with pytest.raises(SchemaError, match="unknown node"):
        schema.validate(bad)


def test_invalid_style_rejected():
    bad = {**FLOW, "style": "rainbow"}
    with pytest.raises(SchemaError, match="style"):
        schema.validate(bad)


def test_state_initial_must_exist():
    bad = {**STATE, "initial": "nope"}
    with pytest.raises(SchemaError, match="initial"):
        schema.validate(bad)


def test_er_relationship_unknown_entity_rejected():
    with pytest.raises(SchemaError, match="unknown node"):
        schema.validate(ER)
