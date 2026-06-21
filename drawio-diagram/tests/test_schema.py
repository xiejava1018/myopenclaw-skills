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


# --- Fix 1: no-coordinate invariant ---

def test_coordinate_fields_rejected():
    bad = {**ARCH_OK, "nodes": [{"id": "web", "label": "Web", "kind": "client",
                                 "x": 10, "y": 20}]}
    with pytest.raises(SchemaError, match="coordinate"):
        schema.validate(bad)


def test_coordinate_field_width_rejected():
    bad = {**ARCH_OK, "nodes": [{"id": "web", "label": "Web", "kind": "client",
                                 "width": 100}]}
    with pytest.raises(SchemaError, match="coordinate"):
        schema.validate(bad)


def test_coordinate_field_geometry_rejected_on_entity():
    bad = {**ER_OK, "entities": [{**ER_OK["entities"][0], "geometry": "1,2,3,4"}]}
    with pytest.raises(SchemaError, match="coordinate"):
        schema.validate(bad)


def test_coordinate_field_position_rejected_on_state():
    bad = {**STATE, "states": [{**STATE["states"][0], "position": {"x": 1}}]}
    with pytest.raises(SchemaError, match="coordinate"):
        schema.validate(bad)


def test_coordinate_field_height_rejected_on_participant():
    bad = {**SEQ, "participants": [{**SEQ["participants"][0], "height": 50}]}
    with pytest.raises(SchemaError, match="coordinate"):
        schema.validate(bad)


# --- Fix 2: TypeError → SchemaError for non-string/unhashable values ---

def test_non_string_type_rejected_cleanly():
    with pytest.raises(SchemaError):
        schema.validate({"type": ["architecture"], "title": "x",
                         "style": "enterprise"})


def test_non_string_style_rejected_cleanly():
    with pytest.raises(SchemaError):
        schema.validate({"type": "flowchart", "title": "x",
                         "style": ["enterprise"], "nodes": [], "edges": []})


def test_non_string_initial_rejected_cleanly():
    bad = {**STATE, "initial": ["s0"]}
    with pytest.raises(SchemaError):
        schema.validate(bad)


# --- Fix 3: Non-list collections → SchemaError ---

def test_nodes_not_list_rejected_cleanly():
    bad = {"type": "flowchart", "title": "x", "style": "enterprise",
           "nodes": "a,b", "edges": []}
    with pytest.raises(SchemaError, match="must be a list"):
        schema.validate(bad)


def test_layers_not_list_rejected_cleanly():
    bad = {**ARCH_OK, "layers": "notalist"}
    with pytest.raises(SchemaError, match="must be a list"):
        schema.validate(bad)


def test_participants_not_list_rejected_cleanly():
    bad = {**SEQ, "participants": "a,b"}
    with pytest.raises(SchemaError, match="must be a list"):
        schema.validate(bad)


def test_entities_not_list_rejected_cleanly():
    bad = {**ER_OK, "entities": "user"}
    with pytest.raises(SchemaError, match="must be a list"):
        schema.validate(bad)


# --- Fix 4: duplicate ids ---

def test_duplicate_node_id_rejected():
    bad = {**ARCH_OK, "nodes": [{"id": "web", "label": "A", "kind": "client"},
                                {"id": "web", "label": "B", "kind": "client"}],
           "layers": [{"id": "L0", "label": "x", "nodes": ["web"]}]}
    with pytest.raises(SchemaError, match="duplicate"):
        schema.validate(bad)


def test_duplicate_participant_id_rejected():
    bad = {**SEQ, "participants": [{"id": "a", "label": "A", "kind": "actor"},
                                   {"id": "a", "label": "A2", "kind": "service"}]}
    with pytest.raises(SchemaError, match="duplicate"):
        schema.validate(bad)


def test_duplicate_entity_id_rejected():
    bad = {**ER_OK, "entities": [{"id": "user", "label": "User",
                                  "attributes": []},
                                 {"id": "user", "label": "Dup",
                                  "attributes": []}]}
    with pytest.raises(SchemaError, match="duplicate"):
        schema.validate(bad)


def test_duplicate_state_id_rejected():
    bad = {**STATE, "states": [{"id": "s0", "label": "A"},
                               {"id": "s0", "label": "Dup"},
                               {"id": "s1", "label": "B"}]}
    with pytest.raises(SchemaError, match="duplicate"):
        schema.validate(bad)


# --- Fix 5: layer-membership uniqueness ---

def test_node_in_two_layers_rejected():
    bad = {
        **ARCH_OK,
        "layers": [
            {"id": "L0", "label": "a", "nodes": ["web"]},
            {"id": "L1", "label": "b", "nodes": ["web"]},  # duplicate
        ],
    }
    with pytest.raises(SchemaError, match="duplicate|layer"):
        schema.validate(bad)
