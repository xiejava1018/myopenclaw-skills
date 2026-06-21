# drawio-diagram Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a `drawio-diagram` Claude Code skill that turns natural-language diagram descriptions into professional `.drawio` files (plus rendered PNG) via a deterministic Python layout engine + the local draw.io CLI.

**Architecture:** Single-direction pipeline — Claude emits a semantic JSON (no coordinates) → `schema.py` validates → `layout.py` computes deterministic geometry (5 per-type solvers, 5 enforced invariants) → `render_drawio.py` emits mxGraph XML → `export.py` calls `drawio` CLI headless for PNG. Claude never computes coordinates; the layout engine owns all spacing/alignment.

**Tech Stack:** Python 3 stdlib only (`json`, `xml.etree.ElementTree`, `argparse`, `subprocess`, `shutil`, `pathlib`, `dataclasses`), `pytest` for tests, draw.io CLI (`/opt/homebrew/bin/drawio`, v30.0.2, headless export already verified).

**Repo context:** Skill lives at `myopenclaw-skills/drawio-diagram/` (source of truth), later symlinked to `~/.claude/skills/drawio-diagram`. Conventions mirror sibling `scheme-writer/`. Commits go to `master`, scoped as `feat(drawio-diagram):` / `test(drawio-diagram):` / `docs(drawio-diagram):`. Attribution is disabled globally — do NOT add Co-Authored-By.

**Design doc:** `docs/plans/2026-06-21-drawio-diagram-design.md` (read it first for rationale).

---

## Conventions for every task

- **TDD strict:** write failing test → run (see FAIL) → minimal impl → run (see PASS) → commit. Never skip the "run to verify it fails" step.
- **Run tests from the skill dir:** `cd drawio-diagram && python -m pytest tests/ -q`
- **No third-party runtime deps.** If you reach for one, stop — use stdlib.
- **Files < 800 lines, functions < 50 lines.** Split when a solver grows large.
- **Frequent commits** — one logical step per commit.

---

# Phase 0 — Scaffold + dependency check + schema

## Task 0.1: Create skill scaffold

**Files:**
- Create: `drawio-diagram/.gitignore`
- Create: `drawio-diagram/requirements.txt`
- Create: `drawio-diagram/scripts/.gitkeep`
- Create: `drawio-diagram/tests/__init__.py`
- Create: `drawio-diagram/tests/conftest.py`

**Step 1:** Create directory structure and files.

`drawio-diagram/.gitignore`:
```
__pycache__/
*.pyc
output/
*.png
*.svg
*.pdf
!examples/*.png
!examples/*.svg
.pytest_cache/
```

`drawio-diagram/requirements.txt`:
```
# Runtime: zero third-party dependencies (Python 3 stdlib only)
# Dev only:
pytest>=7.0
```

`drawio-diagram/tests/__init__.py`: empty file.

`drawio-diagram/tests/conftest.py`:
```python
import sys
from pathlib import Path

# Make scripts/ importable as a package root for tests.
SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
```

**Step 2:** Verify pytest collects zero tests cleanly.
Run: `cd drawio-diagram && python -m pytest tests/ -q`
Expected: `no tests ran` (exit 0, no import errors).

**Step 3:** Commit.
```bash
git add drawio-diagram/.gitignore drawio-diagram/requirements.txt drawio-diagram/scripts/.gitkeep drawio-diagram/tests/__init__.py drawio-diagram/tests/conftest.py
git commit -m "feat(drawio-diagram): scaffold skill directory"
```

---

## Task 0.2: `cli.py check` — dependency detection (TDD)

**Files:**
- Create: `drawio-diagram/scripts/__init__.py` (empty)
- Create: `drawio-diagram/scripts/export.py`
- Test: `drawio-diagram/tests/test_export.py`

The `check` command verifies the draw.io CLI is on PATH.

**Step 1: Write failing tests.**

`drawio-diagram/tests/test_export.py`:
```python
import importlib
export = importlib.import_module("export")  # scripts/export.py


def test_drawio_available_true_when_which_returns_path(monkeypatch):
    monkeypatch.setattr(export.shutil, "which", lambda name: "/opt/homebrew/bin/drawio")
    assert export.drawio_available() is True


def test_drawio_available_false_when_missing(monkeypatch):
    monkeypatch.setattr(export.shutil, "which", lambda name: None)
    assert export.drawio_available() is False


def test_check_status_returns_dict(monkeypatch):
    monkeypatch.setattr(export, "drawio_available", lambda: True)
    monkeypatch.setattr(export, "drawio_version", lambda: "30.0.2")
    status = export.check_status()
    assert status["available"] is True
    assert status["version"] == "30.0.2"
    assert "drawio" in status["install_hint"]
```

**Step 2:** Run — verify FAIL (module not found / AttributeError).
Run: `python -m pytest tests/test_export.py -q`
Expected: FAIL — `ModuleNotFoundError: export`.

**Step 3: Implement.**

`drawio-diagram/scripts/export.py`:
```python
"""draw.io CLI wrapper: availability check + headless export."""
import re
import shutil
import subprocess

DRAWIO_CMD = "drawio"
INSTALL_HINT = (
    "draw.io CLI not found. Install: brew install --cask drawio  "
    "(macOS), or download from https://github.com/jgraph/drawio-desktop/releases"
)


def drawio_available() -> bool:
    return shutil.which(DRAWIO_CMD) is not None


def drawio_version() -> str | None:
    if not drawio_available():
        return None
    try:
        out = subprocess.run(
            [DRAWIO_CMD, "--version"], capture_output=True, text=True, timeout=30
        )
        m = re.search(r"(\d+\.\d+\.\d+)", out.stdout)
        return m.group(1) if m else None
    except Exception:
        return None


def check_status() -> dict:
    available = drawio_available()
    return {
        "available": available,
        "version": drawio_version() if available else None,
        "install_hint": "" if available else INSTALL_HINT,
    }
```

**Step 4:** Run — verify PASS.
Run: `python -m pytest tests/test_export.py -q`
Expected: 3 passed.

**Step 5:** Now wire `check` into `cli.py`.

Create `drawio-diagram/scripts/cli.py`:
```python
"""Unified CLI entry point: build / check."""
import argparse
import json
import sys

import export


def cmd_check(_args) -> int:
    status = export.check_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    if not status["available"]:
        print(status["install_hint"], file=sys.stderr)
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="drawio-diagram")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="verify draw.io CLI is available")
    # `build` added in Task 1.5
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 6:** Smoke-test the real CLI.
Run: `cd drawio-diagram && python scripts/cli.py check`
Expected: JSON with `"available": true`, `"version": "30.0.2"`, exit 0.

**Step 7:** Commit.
```bash
git add drawio-diagram/scripts/__init__.py drawio-diagram/scripts/export.py drawio-diagram/scripts/cli.py drawio-diagram/tests/test_export.py
git commit -m "feat(drawio-diagram): draw.io CLI availability check + cli.py check"
```

---

## Task 0.3: `schema.py` — input validation for all 5 types (TDD)

**Files:**
- Create: `drawio-diagram/scripts/schema.py`
- Test: `drawio-diagram/tests/test_schema.py`

`schema.py` validates `diagram.json` structure per type and fails fast with precise messages.

**Step 1: Write failing tests.**

`drawio-diagram/tests/test_schema.py`:
```python
import importlib
import pytest

schema = importlib.import_module("schema")
SchemaError = schema.SchemaError


# --- valid fixtures (one per type) ---
ARCH = {
    "type": "architecture", "style": "enterprise", "title": "Demo",
    "layers": [{"id": "L0", "label": "客户端", "nodes": ["web"]}],
    "nodes": [{"id": "web", "label": "Web", "kind": "client"}],
    "edges": [{"source": "web", "target": "gw", "flow": "data"}],
}
# (web→gw but gw undefined — invalid edge; fixed below)

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

ER = {
    "type": "er", "style": "enterprise", "title": "E",
    "entities": [{"id": "user", "label": "User",
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
    bad = {**ARCH, "layers": [{"id": "L0", "label": "x", "nodes": ["web"]}],
           "nodes": [{"id": "web", "label": "Web", "kind": "client"}]}
    with pytest.raises(SchemaError, match="unknown node"):
        schema.validate(bad)


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
```

Note: define `ARCH_OK` and `ER_OK` as corrected versions (edges/relationships only reference defined ids):
```python
ARCH_OK = {
    "type": "architecture", "style": "enterprise", "title": "Demo",
    "layers": [{"id": "L0", "label": "客户端", "nodes": ["web", "gw"]}],
    "nodes": [{"id": "web", "label": "Web", "kind": "client"},
              {"id": "gw", "label": "Gateway", "kind": "api"}],
    "edges": [{"source": "web", "target": "gw", "flow": "data"}],
}
ER_OK = {
    "type": "er", "style": "enterprise", "title": "E",
    "entities": [{"id": "user", "label": "User",
                  "attributes": [{"name": "id", "pk": True}]},
                 {"id": "order", "label": "Order",
                  "attributes": [{"name": "id", "pk": True}]}],
    "relationships": [{"from": "user", "to": "order", "card": "1:N"}],
}
```

**Step 2:** Run — verify FAIL.
Run: `python -m pytest tests/test_schema.py -q`
Expected: FAIL — `ModuleNotFoundError: schema`.

**Step 3: Implement.**

`drawio-diagram/scripts/schema.py`:
```python
"""Validate diagram.json semantic structure. Fail fast, precise messages."""
from typing import Any

VALID_TYPES = {"architecture", "flowchart", "sequence", "er", "state"}
VALID_STYLES = {"enterprise", "flat", "notion", "claude", "openai"}

# required top-level keys per type (plus type/style/title checked universally)
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


def _check_node_refs(known: set[str], refs: list[str], ctx: str):
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


def _validate_nodes(d, kind_field="kind"):
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
```

**Step 4:** Run — verify PASS.
Run: `python -m pytest tests/test_schema.py -q`
Expected: all pass.

**Step 5:** Commit.
```bash
git add drawio-diagram/scripts/schema.py drawio-diagram/tests/test_schema.py
git commit -m "feat(drawio-diagram): schema.py validates all 5 diagram types"
```

---

## Task 0.4: Write `references/json-schema.md`

**Files:**
- Create: `drawio-diagram/references/json-schema.md`

**Step 1:** Document every field per type, mirroring `schema.py`. Include one full example per type (architecture, flowchart, sequence, er, state). State explicitly: **no coordinate fields allowed**; list the optional layout hints (`direction` for arch/flow, `layer` semantics, `card`, `guard`, `dashed`, `pk`/`fk`). Cross-link to `drawio-shapes.md` for `kind` values (added in Phase 3).

Keep it under 250 lines. This is the contract Claude reads when filling JSON.

**Step 2:** Commit.
```bash
git add drawio-diagram/references/json-schema.md
git commit -m "docs(drawio-diagram): json-schema.md input contract reference"
```

---

# Phase 1 — Architecture diagram full pipeline (flagship)

Goal: one diagram type end-to-end to prove the whole architecture, plus the shared engine (styles, invariants, render, export, cli build).

## Task 1.1: `styles.py` — style presets → draw.io cell style (TDD)

**Files:**
- Create: `drawio-diagram/scripts/styles.py`
- Test: `drawio-diagram/tests/test_styles.py`

Each style = canvas bg + palette by `kind` + render flags. `cell_style(kind, style_name, shape)` returns the draw.io style string.

**Step 1: Write failing tests.**
```python
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


def test_enterprise_has_no_shadow_flat_has_no_shadow():
    assert styles.STYLES["enterprise"]["shadow"] is False


def test_edge_style_data_is_blue_solid():
    s = styles.edge_style("data", "enterprise")
    assert "edgeStyle=orthogonalEdgeStyle" in s
    assert "2563eb" in s  # blue
    assert "dashed=0" in s


def test_edge_style_async_is_dashed():
    s = styles.edge_style("async", "enterprise")
    assert "dashed=1" in s
```

**Step 2:** Run — verify FAIL (no module).

**Step 3: Implement** `drawio-diagram/scripts/styles.py`:
```python
"""5 visual styles mapped to draw.io cell/edge style strings."""

STYLES = {
    "enterprise": {
        "background": "#ffffff", "shadow": False, "rounded": True, "font_size": 14,
        "font_color": "#1a1a1a", "stroke": "#404040",
        "palette": {
            "client": "#dae8fc", "browser": "#dae8fc", "service": "#d5e8d4",
            "api": "#d5e8d4", "database": "#ffe6cc", "cache": "#fff2cc",
            "vectorstore": "#e1d5e7", "queue": "#f8cecc", "external": "#f5f5f5",
            "cloud": "#f5f5f5", "llm": "#d5e8d4", "actor": "#dae8fc",
            "process": "#f5f5f5", "decision": "#fff2cc", "terminal": "#d5e8d4",
            "io": "#dae8fc", "default": "#f5f5f5",
        },
    },
    "flat": {
        "background": "#ffffff", "shadow": False, "rounded": True, "font_size": 14,
        "font_color": "#333333", "stroke": "#555555",
        "palette": {k: v for k, v in STYLES["enterprise"]["palette"].items()},
    },
    "notion": {
        "background": "#ffffff", "shadow": False, "rounded": False, "font_size": 14,
        "font_color": "#37352f", "stroke": "#9b9a97",
        "palette": {
            "client": "#e8e8e8", "service": "#e8e8e8", "database": "#d6d6d6",
            "cache": "#e8e8e8", "vectorstore": "#d6d6d6", "default": "#f0f0f0",
        },
    },
    "claude": {
        "background": "#f8f6f3", "shadow": True, "rounded": True, "font_size": 14,
        "font_color": "#3d3929", "stroke": "#c9b98a",
        "palette": {
            "client": "#efe7d6", "service": "#e6dcc4", "database": "#dcc9a8",
            "cache": "#efe7d6", "vectorstore": "#dcc9a8", "default": "#ece3d2",
        },
    },
    "openai": {
        "background": "#ffffff", "shadow": False, "rounded": True, "font_size": 14,
        "font_color": "#000000", "stroke": "#000000",
        "palette": {
            "client": "#000000", "service": "#000000", "database": "#000000",
            "cache": "#000000", "vectorstore": "#000000", "default": "#ffffff",
        },
    },
}

EDGE_COLORS = {
    "data": "#2563eb", "control": "#ea580c", "async": "#6b7280",
    "memory_read": "#059669", "memory_write": "#059669", "feedback": "#7c3aed",
    "default": "#404040",
}
DASHED_FLOWS = {"async", "memory_write"}


def _shape_prefix(shape: str) -> str:
    return {
        "cylinder3": "shape=cylinder3;size=15;",
        "hexagon": "shape=hexagon;",
        "rhombus": "rhombus;",
        "cloud": "shape=cloud;",
        "actor": "shape=actor;",
        "parallelogram": "shape=parallelogram;",
        "document": "shape=document;",
        "process": "shape=process;",
        "rounded_rect": "rounded=1;",
        "rect": "rounded=0;",
    }.get(shape, "rounded=1;")


def cell_style(kind: str, style_name: str, shape: str) -> str:
    st = STYLES[style_name]
    color = st["palette"].get(kind, st["palette"]["default"])
    parts = [
        _shape_prefix(shape),
        "whiteSpace=wrap;", "html=1;",
        f"fillColor={color};",
        f"strokeColor={st['stroke']};",
        f"fontColor={st['font_color']};",
        f"fontSize={st['font_size']};",
        f"rounded={'1' if st['rounded'] else '0'};",
    ]
    if st["shadow"]:
        parts.append("shadow=1;")
    return "".join(parts)


def canvas_style(style_name: str) -> dict:
    st = STYLES[style_name]
    return {"background": st["background"]}


def edge_style(flow: str, style_name: str) -> str:
    st = STYLES[style_name]
    color = EDGE_COLORS.get(flow, EDGE_COLORS["default"])
    width = "2" if flow == "data" else "1.5"
    dashed = "1" if flow in DASHED_FLOWS else "0"
    return (
        f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=classic;"
        f"strokeColor={color};strokeWidth={width};dashed={dashed};"
        f"fontColor={st['font_color']};fontSize=12;"
    )
```

**Step 4:** Run — verify PASS.
**Step 5:** Commit.
```bash
git add drawio-diagram/scripts/styles.py drawio-diagram/tests/test_styles.py
git commit -m "feat(drawio-diagram): styles.py maps 5 styles to draw.io cell/edge styles"
```

---

## Task 1.2: Shape registry — semantic `kind` → draw.io shape (TDD)

**Files:**
- Create: `drawio-diagram/scripts/shapes.py`
- Test: `drawio-diagram/tests/test_shapes.py`

Centralize the `kind → shape` mapping so render code is DRY.

**Step 1: Failing tests.**
```python
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
```

**Step 2:** Run — FAIL.
**Step 3:** Implement `drawio-diagram/scripts/shapes.py`:
```python
"""Map semantic node kind -> draw.io shape key (consumed by styles.cell_style)."""

KIND_TO_SHAPE = {
    "client": "rounded_rect",
    "browser": "rounded_rect",
    "service": "rounded_rect",
    "api": "hexagon",
    "database": "cylinder3",
    "cache": "cylinder3",
    "vectorstore": "cylinder3",
    "queue": "process",
    "stream": "process",
    "external": "cloud",
    "cloud": "cloud",
    "llm": "rounded_rect",
    "actor": "actor",
    "process": "rounded_rect",
    "decision": "rhombus",
    "terminal": "rounded_rect",
    "io": "parallelogram",
    "start": "rounded_rect",
    "end": "rounded_rect",
}
DEFAULT_SHAPE = "rounded_rect"


def shape_for(kind: str | None) -> str:
    return KIND_TO_SHAPE.get(kind or "", DEFAULT_SHAPE)
```

**Step 4:** PASS. **Step 5:** Commit.
```bash
git add drawio-diagram/scripts/shapes.py drawio-diagram/tests/test_shapes.py
git commit -m "feat(drawio-diagram): shapes.py semantic kind to draw.io shape map"
```

---

## Task 1.3: `layout.py` — shared invariants module (TDD)

**Files:**
- Create: `drawio-diagram/scripts/layout.py` (constants + invariant helpers + dispatch stub)
- Test: `drawio-diagram/tests/test_layout_invariants.py`

Build the invariant engine BEFORE any solver, so solvers are tested against it.

**Step 1: Failing tests.**
```python
import importlib
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
    layout.assert_no_overlap(geom)  # no exception

def test_assert_no_overlap_fails_for_overlapping():
    geom = layout.empty_geometry("architecture", "enterprise", "T")
    geom["nodes"] = [
        {"id":"a","x":0,"y":0,"width":100,"height":50},
        {"id":"b","x":50,"y":0,"width":100,"height":50},  # overlaps
    ]
    try:
        layout.assert_no_overlap(geom)
        assert False, "expected LayoutError"
    except layout.LayoutError:
        pass

def test_assert_in_bounds_passes():
    geom = layout.empty_geometry("architecture", "enterprise", "T")
    geom["canvas"] = {"width": 500, "height": 300}
    geom["nodes"] = [{"id":"a","x":10,"y":10,"width":100,"height":50}]
    layout.assert_in_bounds(geom)

def test_assert_in_bounds_fails_on_overflow():
    geom = layout.empty_geometry("architecture", "enterprise", "T")
    geom["canvas"] = {"width": 100, "height": 100}
    geom["nodes"] = [{"id":"a","x":10,"y":10,"width":200,"height":50}]
    try:
        layout.assert_in_bounds(geom)
        assert False
    except layout.LayoutError:
        pass

def test_assert_all_snapped():
    geom = layout.empty_geometry("architecture", "enterprise", "T")
    geom["nodes"] = [{"id":"a","x":0,"y":0,"width":140,"height":60}]
    layout.assert_snapped(geom)  # 140/60 not multiples of 20 -> fix this expectation
```

Fix the last test's expectation: `NODE_MIN_W=140` and `60` are NOT multiples of `SNAP=20`. Decide: **snap only x/y positions, not width/height** (widths derive from text, heights are fixed bands). Update test to check x/y only, and have `assert_snapped` check x and y.

**Step 2:** Run — FAIL.
**Step 3: Implement** the shared part of `drawio-diagram/scripts/layout.py`:
```python
"""Deterministic layout engine: constants, invariants, dispatch."""
from typing import Any

# --- spacing constants (single source of truth, tunable) ---
NODE_MIN_W = 140
NODE_H = 76
GUTTER_X = 80
GUTTER_Y = 120
MARGIN = 60
SNAP = 20
MIN_GAP = 24

# font metric for width estimation (px per char, roughly)
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


def _rects(nodes):
    return [(n["x"], n["y"], n["width"], n["height"]) for n in nodes]


def _overlaps(a, b, gap):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax < bx + bw + gap and ax + aw + gap > bx
            and ay < by + bh + gap and ay + ah + gap > by)


def assert_no_overlap(geom: dict) -> None:
    rects = _rects(geom["nodes"])
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if _overlaps(rects[i], rects[j], MIN_GAP):
                raise LayoutError(f"nodes overlap: {geom['nodes'][i]['id']} <-> {geom['nodes'][j]['id']}")


def assert_in_bounds(geom: dict) -> None:
    w, h = geom["canvas"]["width"], geom["canvas"]["height"]
    for n in geom["nodes"]:
        if n["x"] < 0 or n["y"] < 0 or n["x"] + n["width"] > w + 1 or n["y"] + n["height"] > h + 1:
            raise LayoutError(f"node {n['id']} out of canvas bounds")


def assert_snapped(geom: dict) -> None:
    for n in geom["nodes"]:
        for key in ("x", "y"):
            if n[key] % SNAP != 0:
                raise LayoutError(f"node {n['id']} {key}={n[key]} not snapped to {SNAP}")


def assert_width_from_text(geom: dict, source_nodes: dict) -> None:
    """source_nodes: {id: label}. Verify each node width >= text_width(label)."""
    for n in geom["nodes"]:
        label = source_nodes.get(n["id"], "")
        if n["width"] < text_width(label):
            raise LayoutError(f"node {n['id']} too narrow for label {label!r}")


def assert_invariants(geom: dict, source_nodes: dict | None = None) -> None:
    """Run the full 5-invariant check (call after every solver)."""
    assert_no_overlap(geom)
    assert_in_bounds(geom)
    assert_snapped(geom)
    if source_nodes is not None:
        assert_width_from_text(geom, source_nodes)
    # determinism is tested separately by comparing two runs.


def layout(diagram: dict) -> dict:
    """Dispatch to per-type solver. Raises LayoutError on invariant violation."""
    t = diagram["type"]
    if t == "architecture":
        from layout_arch import layout_architecture
        return layout_architecture(diagram)
    raise LayoutError(f"no solver yet for type {t!r}")
```

Note: keep solver imports lazy so `layout.py` tests don't require solvers that don't exist yet. The architecture solver (`layout_arch.py`) is created in Task 1.4.

**Step 4:** Run invariant tests — PASS.
**Step 5:** Commit.
```bash
git add drawio-diagram/scripts/layout.py drawio-diagram/tests/test_layout_invariants.py
git commit -m "feat(drawio-diagram): layout engine constants + 5 invariant checks"
```

---

## Task 1.4: Architecture solver (TDD)

**Files:**
- Create: `drawio-diagram/scripts/layout_arch.py`
- Test: `drawio-diagram/tests/test_layout_arch.py`

Layout: layers as horizontal bands; nodes left-to-right within a band; orthogonal edges between bands.

**Step 1: Failing tests.**
```python
import importlib
layout = importlib.import_module("layout")
layout_arch = importlib.import_module("layout_arch")


def _diagram():
    return {
        "type": "architecture", "style": "enterprise", "title": "T", "direction": "tb",
        "layers": [
            {"id": "L0", "label": "客户端", "nodes": ["web", "app"]},
            {"id": "L1", "label": "服务", "nodes": ["api"]},
            {"id": "L2", "label": "存储", "nodes": ["db"]},
        ],
        "nodes": [
            {"id": "web", "label": "Web Client", "kind": "client"},
            {"id": "app", "label": "Mobile App", "kind": "client"},
            {"id": "api", "label": "API Gateway", "kind": "api"},
            {"id": "db", "label": "PostgreSQL", "kind": "database"},
        ],
        "edges": [
            {"source": "web", "target": "api", "flow": "data"},
            {"source": "app", "target": "api", "flow": "data"},
            {"source": "api", "target": "db", "flow": "data"},
        ],
    }


def test_layout_returns_all_nodes():
    geom = layout_arch.layout_architecture(_diagram())
    ids = {n["id"] for n in geom["nodes"]}
    assert ids == {"web", "app", "api", "db"}


def test_layout_is_deterministic():
    a = layout_arch.layout_architecture(_diagram())
    b = layout_arch.layout_architecture(_diagram())
    assert a == b


def test_layout_passes_all_invariants():
    d = _diagram()
    geom = layout_arch.layout_architecture(d)
    labels = {n["id"]: n["label"] for n in d["nodes"]}
    layout.assert_invariants(geom, source_nodes=labels)  # no exception


def test_layers_ordered_top_to_bottom():
    geom = layout_arch.layout_architecture(_diagram())
    y = {n["id"]: n["y"] for n in geom["nodes"]}
    assert y["web"] < y["api"] < y["db"]


def test_edges_have_orthogonal_points():
    geom = layout_arch.layout_architecture(_diagram())
    for e in geom["edges"]:
        assert len(e["points"]) >= 2
        # orthogonal: consecutive segments share x or y
        pts = e["points"]
        for i in range(len(pts) - 1):
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            assert x1 == x2 or y1 == y2


def test_containers_one_per_layer():
    geom = layout_arch.layout_architecture(_diagram())
    assert len(geom["containers"]) == 3
```

**Step 2:** Run — FAIL.

**Step 3: Implement** `drawio-diagram/scripts/layout_arch.py`:
```python
"""Architecture diagram layout: layered horizontal bands."""
import layout

NODE_H = layout.NODE_H


def layout_architecture(d: dict) -> dict:
    direction = d.get("direction", "tb")
    if direction != "tb":
        # v1 supports tb; lr is a follow-up. Fail loud rather than guess.
        raise layout.LayoutError("architecture v1 supports direction='tb' only")

    geom = layout.empty_geometry("architecture", d["style"], d["title"])
    node_map = {n["id"]: n for n in d["nodes"]}

    y_cursor = layout.MARGIN
    max_right = 0
    centers = {}  # id -> (cx, cy, x, y, w, h)

    for layer in d["layers"]:
        lids = layer["nodes"]
        sized = []
        for nid in lids:
            nd = node_map[nid]
            w = layout.snap(layout.text_width(nd["label"]))
            h = layout.snap(NODE_H)
            sized.append((nid, nd, w, h))
        band_h = layout.snap(max((h for _, _, _, h in sized), default=NODE_H))

        row_w = sum(w for _, _, w, _ in sized) + layout.GUTTER_X * (len(sized) - 1)
        x_cursor = layout.MARGIN
        layer_left = x_cursor
        for nid, nd, w, h in sized:
            nx, ny = layout.snap(x_cursor), layout.snap(y_cursor)
            geom["nodes"].append({
                "id": nid, "label": nd["label"],
                "kind": nd.get("kind", "service"),
                "x": nx, "y": ny, "width": w, "height": band_h,
            })
            centers[nid] = (nx + w // 2, ny + band_h // 2, nx, ny, w, band_h)
            x_cursor += w + layout.GUTTER_X
        layer_right = x_cursor - layout.GUTTER_X
        max_right = max(max_right, layer_right)

        geom["containers"].append({
            "id": layer["id"], "label": layer.get("label", ""),
            "x": layout.snap(layer_left - 10), "y": layout.snap(y_cursor - 10),
            "width": layout.snap(layer_right - layer_left + 20),
            "height": layout.snap(band_h + 20),
        })
        y_cursor += band_h + layout.GUTTER_Y

    geom["canvas"] = {
        "width": layout.snap(max_right + layout.MARGIN),
        "height": layout.snap(y_cursor - layout.GUTTER_Y + layout.MARGIN),
    }

    for e in d["edges"]:
        src = centers[e["source"]]
        tgt = centers[e["target"]]
        pts = _orthogonal(src, tgt)
        geom["edges"].append({
            "source": e["source"], "target": e["target"],
            "label": e.get("label", ""), "flow": e.get("flow", "data"),
            "points": pts,
        })

    labels = {n["id"]: n["label"] for n in d["nodes"]}
    layout.assert_invariants(geom, source_nodes=labels)
    return geom


def _orthogonal(src, tgt):
    """src/tgt = (cx, cy, x, y, w, h). Route bottom-of-src -> top-of-tgt with L-bend."""
    sx, sy, sxx, syy, sw, sh = src
    tx, ty, txx, tyy, tw, th = tgt
    start = (sx, syy + sh)           # bottom-center of source
    mid_y = (syy + sh + tyy) // 2    # halfway into the gutter
    end = (tx, tyy)                  # top-center of target
    if sx == tx:
        return [start, end]
    return [start, (sx, mid_y), (tx, mid_y), end]
```

**Step 4:** Run — verify PASS. If an invariant fails, **fix the solver, not the test** (tests encode the contract).
**Step 5:** Commit.
```bash
git add drawio-diagram/scripts/layout_arch.py drawio-diagram/tests/test_layout_arch.py
git commit -m "feat(drawio-diagram): architecture layered layout solver"
```

---

## Task 1.5: `render_drawio.py` — geometry → mxGraph XML (TDD)

**Files:**
- Create: `drawio-diagram/scripts/render_drawio.py`
- Test: `drawio-diagram/tests/test_render.py`

Render geometry dict to a `.drawio` (mxfile) XML string using `xml.etree.ElementTree`. Parseable + round-trippable.

**Step 1: Failing tests.**
```python
import importlib
import xml.etree.ElementTree as ET
render = importlib.import_module("render_drawio")


def _geom():
    return {
        "type": "architecture", "title": "T", "style": "enterprise",
        "canvas": {"width": 600, "height": 300},
        "nodes": [{"id": "a", "label": "Web", "kind": "client",
                   "x": 60, "y": 60, "width": 140, "height": 76}],
        "edges": [{"source": "a", "target": "a", "label": "loop",
                   "flow": "feedback", "points": [[60, 60], [60, 136]]}],
        "containers": [], "decorations": [],
    }


def test_render_produces_valid_xml():
    xml = render.render(_geom())
    root = ET.fromstring(xml)  # raises if invalid
    assert root.tag == "mxfile"


def test_render_contains_node_cell():
    xml = render.render(_geom())
    root = ET.fromstring(xml)
    cells = root.iter("mxCell")
    values = [c.get("value") for c in cells]
    assert "Web" in values


def test_render_canvas_size_set():
    xml = render.render(_geom())
    root = ET.fromstring(xml)
    model = root.find(".//mxGraphModel")
    assert model.get("pageWidth") == "600"
    assert model.get("pageHeight") == "300"


def test_render_edge_uses_orthogonal_style():
    xml = render.render(_geom())
    assert "edgeStyle=orthogonalEdgeStyle" in xml
```

**Step 2:** Run — FAIL.

**Step 3: Implement** `drawio-diagram/scripts/render_drawio.py`:
```python
"""Render layout geometry -> draw.io mxfile XML string."""
import xml.etree.ElementTree as ET
import shapes
import styles

_ROOT_PARENT_ID = "1"


def render(geom: dict) -> str:
    canvas = geom["canvas"]
    style_name = geom["style"]
    cs = styles.canvas_style(style_name)

    mxfile = ET.Element("mxfile", {"host": "app.diagrams.net"})
    diagram = ET.SubElement(mxfile, "diagram", {"name": geom.get("title", "Diagram"), "id": "d0"})
    model = ET.SubElement(diagram, "mxGraphModel", {
        "dx": "800", "dy": "600", "grid": "1", "gridSize": "10",
        "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1",
        "fold": "1", "page": "1", "pageScale": "1",
        "pageWidth": str(canvas["width"]), "pageHeight": str(canvas["height"]),
        "math": "0", "shadow": "0", "background": cs["background"],
    })
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": _ROOT_PARENT_ID, "parent": "0"})

    # containers (layer bands) first so nodes render on top
    for c in geom.get("containers", []):
        _add_container(root, c, style_name)
    for n in geom["nodes"]:
        _add_node(root, n, style_name)
    for d in geom.get("decorations", []):
        _add_node(root, d, style_name)
    for e in geom["edges"]:
        _add_edge(root, e, style_name)

    _indent(mxfile)
    return ET.tostring(mxfile, encoding="unicode")


def _add_node(root, n, style_name):
    shape = shapes.shape_for(n.get("kind"))
    cell = ET.SubElement(root, "mxCell", {
        "id": n["id"], "value": n.get("label", ""),
        "style": styles.cell_style(n.get("kind", "default"), style_name, shape),
        "vertex": "1", "parent": _ROOT_PARENT_ID,
    })
    ET.SubElement(cell, "mxGeometry", {
        "x": str(n["x"]), "y": str(n["y"]),
        "width": str(n["width"]), "height": str(n["height"]), "as": "geometry",
    })


def _add_container(root, c, style_name):
    st = styles.STYLES[style_name]
    style_str = (
        f"rounded=0;whiteSpace=wrap;html=1;fillColor=none;"
        f"strokeColor={st['stroke']};dashed=1;dashPattern=8 4;"
        f"verticalAlign=top;fontColor={st['font_color']};fontSize=12;"
    )
    cell = ET.SubElement(root, "mxCell", {
        "id": c["id"], "value": c.get("label", ""), "style": style_str,
        "vertex": "1", "parent": _ROOT_PARENT_ID,
    })
    ET.SubElement(cell, "mxGeometry", {
        "x": str(c["x"]), "y": str(c["y"]),
        "width": str(c["width"]), "height": str(c["height"]), "as": "geometry",
    })


def _add_edge(root, e, style_name):
    cell = ET.SubElement(root, "mxCell", {
        "id": f"edge_{e['source']}_{e['target']}",
        "value": e.get("label", ""),
        "style": styles.edge_style(e.get("flow", "data"), style_name),
        "edge": "1", "parent": _ROOT_PARENT_ID,
        "source": e["source"], "target": e["target"],
    })
    geo = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
    pts = e.get("points", [])
    if len(pts) >= 2:
        arr = ET.SubElement(geo, "Array", {"as": "points"})
        for px, py in pts[1:-1]:  # endpoints come from source/target vertices
            ET.SubElement(arr, "mxPoint", {"x": str(px), "y": str(py)})
    sx, sy = pts[0]
    ET.SubElement(geo, "mxPoint", {"x": str(sx), "y": str(sy), "as": "sourcePoint"})
    ex, ey = pts[-1]
    ET.SubElement(geo, "mxPoint", {"x": str(ex), "y": str(ey), "as": "targetPoint"})


def _indent(elem, level=0):
    """Pretty-print without lxml (stdlib only)."""
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i
```

**Step 4:** Run — PASS. **Step 5:** Commit.
```bash
git add drawio-diagram/scripts/render_drawio.py drawio-diagram/tests/test_render.py
git commit -m "feat(drawio-diagram): render_drawio.py geometry to mxGraph XML"
```

---

## Task 1.6: `export.py` — headless PNG export (TDD)

Extend `export.py` (started in Task 0.2) with the actual export call.

**Files:**
- Modify: `drawio-diagram/scripts/export.py`
- Modify: `drawio-diagram/tests/test_export.py`

**Step 1: Failing tests.**
```python
def test_export_builds_correct_command(monkeypatch, tmp_path):
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        class R: returncode = 0; stdout = ""; stderr = ""
        return R()
    monkeypatch.setattr(export.subprocess, "run", fake_run)
    export.export_image("in.drawio", str(tmp_path / "out.png"), fmt="png", scale=2, border=20)
    cmd = captured["cmd"]
    assert cmd[0] == "drawio"
    assert "-x" in cmd and "-f" in cmd and "png" in cmd
    assert "--scale" in cmd and "2" in cmd
    assert "--border" in cmd and "20" in cmd


def test_export_raises_if_drawio_missing(monkeypatch):
    monkeypatch.setattr(export, "drawio_available", lambda: False)
    try:
        export.export_image("in.drawio", "out.png")
        assert False
    except export.ExportError:
        pass


def test_export_raises_on_nonzero_exit(monkeypatch, tmp_path):
    def fake_run(cmd, **kw):
        class R: returncode = 1; stdout = ""; stderr = "boom"
        return R()
    monkeypatch.setattr(export.subprocess, "run", fake_run)
    monkeypatch.setattr(export, "drawio_available", lambda: True)
    try:
        export.export_image("in.drawio", str(tmp_path/"o.png"))
        assert False
    except export.ExportError as e:
        assert "boom" in str(e)
```

**Step 2:** Run — FAIL (ExportError / export_image undefined).

**Step 3: Add** to `export.py`:
```python
class ExportError(Exception):
    pass


def export_image(drawio_path: str, out_path: str, fmt: str = "png",
                 scale: int = 2, border: int = 20) -> None:
    if not drawio_available():
        raise ExportError(INSTALL_HINT)
    cmd = [
        DRAWIO_CMD, "-x", "-f", fmt, "-o", out_path, drawio_path,
        "--scale", str(scale), "--border", str(border),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise ExportError(
            f"drawio export failed (exit {result.returncode}): {result.stderr.strip()}"
        )
```

**Step 4:** Run — PASS. **Step 5:** Commit.
```bash
git add drawio-diagram/scripts/export.py drawio-diagram/tests/test_export.py
git commit -m "feat(drawio-diagram): export_image headless PNG via drawio CLI"
```

---

## Task 1.7: `cli.py build` — orchestrate the full pipeline (TDD)

**Files:**
- Modify: `drawio-diagram/scripts/cli.py`
- Test: `drawio-diagram/tests/test_cli.py`

**Step 1: Failing tests.**
```python
import importlib, json
cli = importlib.import_module("cli")


ARCH_JSON = {
    "type": "architecture", "style": "enterprise", "title": "Demo", "direction": "tb",
    "layers": [{"id": "L0", "label": "客户端", "nodes": ["web", "gw"]},
               {"id": "L1", "label": "存储", "nodes": ["db"]}],
    "nodes": [{"id": "web", "label": "Web", "kind": "client"},
              {"id": "gw", "label": "Gateway", "kind": "api"},
              {"id": "db", "label": "Postgres", "kind": "database"}],
    "edges": [{"source": "web", "target": "gw", "flow": "data"},
              {"source": "gw", "target": "db", "flow": "data"}],
}


def test_build_writes_drawio_and_png(tmp_path, monkeypatch):
    # stub the actual drawio export so the test doesn't need the CLI
    import export
    written = {}
    def fake_export(drawio_path, out_path, **kw):
        written["png"] = out_path
        with open(out_path, "w") as f: f.write("PNG")
    monkeypatch.setattr(export, "export_image", fake_export)

    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(ARCH_JSON), encoding="utf-8")
    out = tmp_path / "out"

    rc = cli.main(["build", str(inp), "-o", str(out)])
    assert rc == 0
    assert (tmp_path / "out.drawio").exists()
    assert (tmp_path / "out.png").exists()


def test_build_invalid_schema_exits_nonzero(tmp_path):
    inp = tmp_path / "bad.json"
    inp.write_text(json.dumps({"type": "bogus"}), encoding="utf-8")
    rc = cli.main(["build", str(inp), "-o", str(tmp_path / "out")])
    assert rc != 0
```

**Step 2:** Run — FAIL.

**Step 3: Implement** `build` in `cli.py`:
```python
import schema
import layout
import render_drawio
import export


def cmd_build(args) -> int:
    try:
        with open(args.input, encoding="utf-8") as f:
            diagram = json.load(f)
        schema.validate(diagram)
    except schema.SchemaError as e:
        print(f"schema error: {e}", file=sys.stderr)
        return 2
    try:
        geom = layout.layout(diagram)
    except layout.LayoutError as e:
        print(f"layout error: {e}", file=sys.stderr)
        return 3
    xml = render_drawio.render(geom)
    drawio_path = args.output + ".drawio"
    with open(drawio_path, "w", encoding="utf-8") as f:
        f.write(xml)
    fmt = args.format
    img_path = f"{args.output}.{fmt}"
    try:
        export.export_image(drawio_path, img_path, fmt=fmt, scale=args.scale, border=args.border)
    except export.ExportError as e:
        print(f"export warning: {e}", file=sys.stderr)
        print(f".drawio source still written: {drawio_path}", file=sys.stderr)
        return 4
    print(f"wrote {drawio_path}")
    print(f"wrote {img_path}")
    return 0


# in main(), add:
# p_build = sub.add_parser("build", help="build .drawio + rendered image from diagram.json")
# p_build.add_argument("input")
# p_build.add_argument("-o", "--output", required=True, help="output basename (no extension)")
# p_build.add_argument("-f", "--format", default="png", choices=["png", "svg", "pdf"])
# p_build.add_argument("--scale", type=int, default=2)
# p_build.add_argument("--border", type=int, default=20)
# elif args.command == "build": return cmd_build(args)
```

**Step 4:** Run — PASS. **Step 5:** Commit.
```bash
git add drawio-diagram/scripts/cli.py drawio-diagram/tests/test_cli.py
git commit -m "feat(drawio-diagram): cli.py build orchestrates full pipeline"
```

---

## Task 1.8: End-to-end smoke test — real architecture diagram

**Files:**
- Create: `drawio-diagram/examples/rag-architecture.json` (input)
- No test file — manual verification step.

**Step 1:** Write a realistic RAG architecture input (Client → API → Orchestrator → {LLM, VectorStore} → Postgres) following `references/json-schema.md`.

**Step 2:** Run the real pipeline against the installed CLI.
```bash
cd drawio-diagram
python scripts/cli.py build examples/rag-architecture.json -o examples/rag-architecture
```
Expected: exit 0, `examples/rag-architecture.drawio` + `examples/rag-architecture.png` written.

**Step 3:** **Visual self-review** — open the PNG (use the Read tool on the image, or open in Preview). Check: no overlapping nodes, arrows connect cleanly, layer bands visible, text fits. If broken, fix the solver (`layout_arch.py`) — do NOT hand-edit coordinates. The deterministic rebuild must fix it.

**Step 4:** Verify the `.drawio` opens in the draw.io app:
```bash
open examples/rag-architecture.drawio
```
Confirm it's editable with real shapes.

**Step 5:** Commit the example input + outputs (PNG/SVG are gitignored except under `examples/`, which `.gitignore` whitelists).
```bash
git add drawio-diagram/examples/rag-architecture.json drawio-diagram/examples/rag-architecture.drawio drawio-diagram/examples/rag-architecture.png
git commit -m "feat(drawio-diagram): end-to-end RAG architecture example (validates pipeline)"
```

**This is the milestone** — the whole architecture is proven. Everything after this is repetition/expansion.

---

# Phase 2 — Remaining 4 solvers

Each solver follows the **exact pattern of Task 1.4**:
1. Create `scripts/layout_<type>.py` with `layout_<type>(d) -> geom`.
2. Start from `layout.empty_geometry(...)`, compute geometry using shared constants, build edges/decorations, call `layout.assert_invariants(geom, source_nodes=labels)` before returning.
3. Write `tests/test_layout_<type>.py` with: returns all nodes, deterministic, passes all invariants, type-specific structural assertions.
4. Register in `layout.py` dispatch.
5. Add one example input under `examples/`, run real `cli.py build`, visual self-review, commit.

Apply DRY: extract any repeated edge-routing into a shared helper in `layout.py` (e.g. `_orthogonal` currently lives in `layout_arch.py` — move it to `layout.py` and import it).

## Task 2.1: Flowchart solver

**Algorithm:** topological rank assignment (longest path from roots) → nodes placed in rank rows top-to-bottom → decision branches route sideways via `target_port`-style orthogonal bends. Reduce crossings with a simple barycenter sort within each rank.

**Specific structural test:** start node at rank 0 (top), decision "否" branch goes to a node at the same rank (sideways), terminal `end` at the deepest rank. All nodes pass `assert_invariants`.

**Files:** `scripts/layout_flow.py`, `tests/test_layout_flow.py`, register dispatch, `examples/order-flowchart.json`.

## Task 2.2: Sequence solver

**Algorithm:** participants = evenly spaced vertical columns; each message = a horizontal arrow at its own y slot (top-to-bottom by list order); lifelines = vertical dashed decorations behind; activation boxes = thin filled rects (optional v1 — skip if time-boxed); `frames` (loop/alt) = rect decorations spanning message y-ranges with a label tab.

**Decorations** (new geom field, already in the schema): `{"kind":"lifeline","x":..,"y":..,"width":0,"height":..,"label":participant}` and `{"kind":"frame","x":..,"y":..,"width":..,"height":..,"label":"loop"}`. Render lifelines as edges with `dashed=1` and no arrowhead (extend `render_drawio.py` to handle decoration kinds — add a test).

**Specific structural test:** participant columns equally spaced; message y strictly increasing with list index; return messages (`dashed=true`) rendered with dashed edge.

**Files:** `scripts/layout_seq.py`, `tests/test_layout_seq.py`, extend `render_drawio.py` for lifelines/frames (+test), register dispatch, `examples/checkout-sequence.json`.

## Task 2.3: ER solver

**Algorithm:** entities = 3-compartment rects (header + attribute rows) sized by longest attribute; placed in a 2-3 column grid (auto-pick columns by count). Relationships = orthogonal edges between entity edges with cardinality labels near endpoints and a relationship label mid-edge.

**Render detail:** an entity is a single mxCell with HTML label containing header + `<br>`-separated underlined PK / FK-marked attributes (`<u>id</u>` for PK, italic FK). Add a `render_entity` helper in `render_drawio.py` (+test).

**Specific structural test:** entity width ≥ text_width(longest attribute); no two entities overlap; relationships reference existing entities (schema guarantees this).

**Files:** `scripts/layout_er.py`, `tests/test_layout_er.py`, extend `render_drawio.py` for entities (+test), register dispatch, `examples/ecommerce-er.json`.

## Task 2.4: State machine solver

**Algorithm:** BFS from `initial` to assign ranks; states placed left-to-right by rank; initial pseudo-state = filled circle decoration at far left, finals = bullseye decorations at the rank of the target state; transitions = orthogonal edges with `label` and optional `[guard]` prefix.

**Decorations:** `{"kind":"initial_pseudostate",...}` and `{"kind":"final_pseudostate",...}`. Render as small circle / bullseye cells (add helpers + tests in `render_drawio.py`).

**Specific structural test:** BFS determinism — same transitions always produce same ranks; initial pseudostate has exactly one outgoing edge; final states have no outgoing.

**Files:** `scripts/layout_state.py`, `tests/test_layout_state.py`, extend `render_drawio.py` for pseudo-states (+test), register dispatch, `examples/order-state.json`.

---

# Phase 3 — Styles polish + icon catalog

## Task 3.1: Remaining styles + `references/styles.md`

- Verify `flat`, `notion`, `claude`, `openai` produce visually distinct, clean output by generating the same architecture diagram in all 5 styles (`examples/rag-architecture-<style>.png`) and visually diffing.
- Write `references/styles.md`: per-style swatches (bg/palette hex table), best-for guidance, default = enterprise.

## Task 3.2: Cloud icon catalog + `references/drawio-shapes.md`

- Add optional `provider`+`service` fields to `schema.py` architecture/flowchart nodes (optional, backward-compatible — no new required field). Add a `cloud_icon(provider, service)` lookup in `shapes.py`/`styles.py` returning `shape=mxgraph.<lib>.<icon>` cell style. Curate ~30 high-frequency icons across AWS/Azure/GCP (S3, Lambda, EC2, RDS, VPC; Azure Functions, SQL DB, Storage; GCP Cloud Functions, Cloud SQL, GCS).
- Document the catalog in `references/drawio-shapes.md` with the full `kind → shape` table + cloud-icon table.
- Test: `test_shapes.py` — `cloud_icon("aws","s3")` returns a string containing `mxgraph.aws4`.

## Task 3.3: `references/diagram-types.md`

Document the 5 diagram types: when to use each, the semantic fields, and the layout hints Claude should provide. This is Claude's "how to think about each diagram" reference.

---

# Phase 4 — SKILL.md, templates, README, coverage

## Task 4.1: `SKILL.md` + `templates/`

Write `drawio-diagram/SKILL.md` with frontmatter `description` carrying the trigger words and the 6-step workflow from the design doc (check → classify → fill JSON → build → visual self-review → report). Emphasize: **never compute coordinates; never hand-write `.drawio`**.

Create `templates/{architecture,flowchart,sequence,er-diagram,state-machine}.json` — minimal valid skeletons Claude copies and edits.

## Task 4.2: `README.md`

Human-readable doc: install (requires draw.io CLI), quickstart, the 5 styles, the 5 types, examples, how to edit `.drawio` afterward.

## Task 4.3: `examples/` final

Ensure each of the 5 types has a committed `.json` + `.drawio` + `.png` example (generated from real CLI). Visual self-review each.

## Task 4.4: Coverage + full test run

Run: `cd drawio-diagram && python -m pytest tests/ -q --tb=short`
Expected: all green. Add tests for any branch below 80% coverage. Re-run until ≥80%.

---

# Phase 5 — Install

## Task 5.1: Symlink to `~/.claude/skills/` + uninstall draw-diagram

```bash
ln -s "$PWD/drawio-diagram" ~/.claude/skills/drawio-diagram
# Verify Claude loads it (restart Claude Code, check /skills or trigger word)
# Then remove the old skill:
rm -rf ~/.claude/skills/draw-diagram
```

**Confirm with user before deleting `~/.claude/skills/draw-diagram`** (the user said they'll uninstall it — but verify the new skill works first).

Update repo `README.md` skill table: add `drawio-diagram` row, remove reference to draw-diagram (it was never in this repo's table anyway — just add the new row).

---

## Done criteria

- [ ] `python -m pytest tests/ -q` all green, ≥80% coverage
- [ ] All 5 diagram types render via real `drawio` CLI with valid PNG + editable `.drawio`
- [ ] 5 styles each produce distinct, professional output
- [ ] All 5 layout invariants enforced in tests
- [ ] SKILL.md + templates + references + examples + README complete
- [ ] Symlinked to `~/.claude/skills/drawio-diagram`; draw-diagram removed
- [ ] Repo README updated
