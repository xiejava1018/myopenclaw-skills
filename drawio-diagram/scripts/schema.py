"""Validate diagram.json semantic structure. Fail fast, precise messages."""
from typing import Any

VALID_TYPES = {"architecture", "flowchart", "sequence", "er", "state"}
VALID_STYLES = {"enterprise", "flat", "notion", "claude", "openai"}

# The layout engine owns all geometry. Claude must never hand in coordinates.
FORBIDDEN_COORD_KEYS = {"x", "y", "width", "height", "geometry", "position"}

REQUIRED = {
    "architecture": {"layers", "nodes", "edges"},
    "flowchart": {"nodes", "edges"},
    "sequence": {"participants", "messages"},
    "er": {"entities", "relationships"},
    "state": {"states", "transitions", "initial"},
}


class SchemaError(Exception):
    pass


def _require(d: dict, key: str, ctx: str):
    if key not in d:
        raise SchemaError(f"{ctx}: missing required field {key!r}")


def _require_list(d: dict, key: str, ctx: str):
    if not isinstance(d[key], list):
        raise SchemaError(f"{ctx}: field {key!r} must be a list")


def _reject_coordinates(d: dict, ctx: str):
    """Coordinate fields are forbidden — the layout engine owns geometry."""
    for k in FORBIDDEN_COORD_KEYS:
        if k in d:
            raise SchemaError(
                f"{ctx}: coordinate field {k!r} not allowed — "
                "layout engine owns geometry"
            )


def _check_node_refs(known: set, refs: list, ctx: str):
    for r in refs:
        if r not in known:
            raise SchemaError(f"{ctx}: unknown node reference {r!r}")


def validate(d: Any) -> None:
    if not isinstance(d, dict):
        raise SchemaError("diagram must be a JSON object")
    if "type" not in d:
        raise SchemaError("missing required field 'type'")
    t = d["type"]
    if not isinstance(t, str) or t not in VALID_TYPES:
        raise SchemaError(
            f"unknown type {t!r}; expected one of {sorted(VALID_TYPES)}"
        )
    _require(d, "title", t)
    _require(d, "style", t)
    s = d["style"]
    if not isinstance(s, str) or s not in VALID_STYLES:
        raise SchemaError(
            f"invalid style {s!r}; expected one of {sorted(VALID_STYLES)}"
        )
    for k in REQUIRED[t]:
        _require(d, k, t)

    if t == "architecture":
        _validate_architecture(d)
    elif t == "flowchart":
        _validate_flowchart(d)
    elif t == "sequence":
        _validate_sequence(d)
    elif t == "er":
        _validate_er(d)
    elif t == "state":
        _validate_state(d)


def _validate_nodes(d):
    _require_list(d, "nodes", "node")
    known = set()
    for n in d["nodes"]:
        _require(n, "id", "node")
        _require(n, "label", "node")
        _reject_coordinates(n, "node")
        if n["id"] in known:
            raise SchemaError(f"duplicate node id {n['id']!r}")
        known.add(n["id"])
    return known


def _validate_architecture(d):
    _require_list(d, "layers", "layer")
    _require_list(d, "edges", "edge")
    known = _validate_nodes(d)
    for layer in d["layers"]:
        _require(layer, "id", "layer")
        _require(layer, "nodes", "layer")
        _check_node_refs(known, layer["nodes"], "layer")
    for e in d["edges"]:
        _require(e, "source", "edge")
        _require(e, "target", "edge")
        _check_node_refs(known, [e["source"], e["target"]], "edge")


def _validate_flowchart(d):
    _require_list(d, "edges", "edge")
    known = _validate_nodes(d)
    for e in d["edges"]:
        _require(e, "source", "edge")
        _require(e, "target", "edge")
        _check_node_refs(known, [e["source"], e["target"]], "edge")


def _validate_sequence(d):
    _require_list(d, "participants", "participant")
    _require_list(d, "messages", "message")
    known = set()
    for p in d["participants"]:
        _require(p, "id", "participant")
        _require(p, "label", "participant")
        _reject_coordinates(p, "participant")
        if p["id"] in known:
            raise SchemaError(f"duplicate participant id {p['id']!r}")
        known.add(p["id"])
    for m in d["messages"]:
        _require(m, "from", "message")
        _require(m, "to", "message")
        _check_node_refs(known, [m["from"], m["to"]], "message")


def _validate_er(d):
    _require_list(d, "entities", "entity")
    _require_list(d, "relationships", "relationship")
    known = set()
    for ent in d["entities"]:
        _require(ent, "id", "entity")
        _require(ent, "label", "entity")
        _require(ent, "attributes", "entity")
        _reject_coordinates(ent, "entity")
        if ent["id"] in known:
            raise SchemaError(f"duplicate entity id {ent['id']!r}")
        known.add(ent["id"])
    for rel in d["relationships"]:
        _require(rel, "from", "relationship")
        _require(rel, "to", "relationship")
        _check_node_refs(known, [rel["from"], rel["to"]], "relationship")


def _validate_state(d):
    _require_list(d, "states", "state")
    _require_list(d, "transitions", "transition")
    known = set()
    for s in d["states"]:
        _require(s, "id", "state")
        _require(s, "label", "state")
        _reject_coordinates(s, "state")
        if s["id"] in known:
            raise SchemaError(f"duplicate state id {s['id']!r}")
        known.add(s["id"])
    initial = d["initial"]
    if not isinstance(initial, str) or initial not in known:
        raise SchemaError(f"initial state {initial!r} not in states")
    for tr in d["transitions"]:
        _require(tr, "from", "transition")
        _require(tr, "to", "transition")
        _check_node_refs(known, [tr["from"], tr["to"]], "transition")
    finals = d.get("final", [])
    _check_node_refs(known, finals, "final")
