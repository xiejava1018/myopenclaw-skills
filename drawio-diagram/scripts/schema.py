"""Validate diagram.json semantic structure. Fail fast, precise messages."""
from typing import Any

VALID_TYPES = {"architecture", "flowchart", "sequence", "er", "state"}
VALID_STYLES = {"enterprise", "flat", "notion", "claude", "openai"}

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
    if t not in VALID_TYPES:
        raise SchemaError(
            f"unknown type {t!r}; expected one of {sorted(VALID_TYPES)}"
        )
    _require(d, "title", t)
    _require(d, "style", t)
    if d["style"] not in VALID_STYLES:
        raise SchemaError(
            f"invalid style {d['style']!r}; expected one of {sorted(VALID_STYLES)}"
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
    known = set()
    for n in d["nodes"]:
        _require(n, "id", "node")
        _require(n, "label", "node")
        known.add(n["id"])
    return known


def _validate_architecture(d):
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
    known = _validate_nodes(d)
    for e in d["edges"]:
        _require(e, "source", "edge")
        _require(e, "target", "edge")
        _check_node_refs(known, [e["source"], e["target"]], "edge")


def _validate_sequence(d):
    known = set()
    for p in d["participants"]:
        _require(p, "id", "participant")
        _require(p, "label", "participant")
        known.add(p["id"])
    for m in d["messages"]:
        _require(m, "from", "message")
        _require(m, "to", "message")
        _check_node_refs(known, [m["from"], m["to"]], "message")


def _validate_er(d):
    known = set()
    for ent in d["entities"]:
        _require(ent, "id", "entity")
        _require(ent, "label", "entity")
        _require(ent, "attributes", "entity")
        known.add(ent["id"])
    for rel in d["relationships"]:
        _require(rel, "from", "relationship")
        _require(rel, "to", "relationship")
        _check_node_refs(known, [rel["from"], rel["to"]], "relationship")


def _validate_state(d):
    known = set()
    for s in d["states"]:
        _require(s, "id", "state")
        _require(s, "label", "state")
        known.add(s["id"])
    if d["initial"] not in known:
        raise SchemaError(f"initial state {d['initial']!r} not in states")
    for tr in d["transitions"]:
        _require(tr, "from", "transition")
        _require(tr, "to", "transition")
        _check_node_refs(known, [tr["from"], tr["to"]], "transition")
    finals = d.get("final", [])
    _check_node_refs(known, finals, "final")
