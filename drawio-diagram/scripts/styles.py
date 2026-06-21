"""5 visual styles mapped to draw.io cell/edge style strings."""

# Enterprise palette is referenced by other styles, so define it first.
_ENTERPRISE_PALETTE = {
    "client": "#dae8fc", "browser": "#dae8fc", "service": "#d5e8d4",
    "api": "#d5e8d4", "database": "#ffe6cc", "cache": "#fff2cc",
    "vectorstore": "#e1d5e7", "queue": "#f8cecc", "external": "#f5f5f5",
    "cloud": "#f5f5f5", "llm": "#d5e8d4", "actor": "#dae8fc",
    "process": "#f5f5f5", "decision": "#fff2cc", "terminal": "#d5e8d4",
    "io": "#dae8fc", "default": "#f5f5f5",
}

STYLES = {
    "enterprise": {
        "background": "#ffffff", "shadow": False, "rounded": True, "font_size": 14,
        "font_color": "#1a1a1a", "stroke": "#404040",
        "palette": dict(_ENTERPRISE_PALETTE),
    },
    "flat": {
        "background": "#ffffff", "shadow": False, "rounded": True, "font_size": 14,
        "font_color": "#333333", "stroke": "#555555",
        "palette": dict(_ENTERPRISE_PALETTE),
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
    # OpenAI-brand high-contrast: black ink on white fill. A pure-black fill
    # would put #000 text on #000 boxes (unreadable), so every fill is white
    # and only stroke + font carry the black. This yields the clean
    # black-on-white editorial look the style is named for.
    "openai": {
        "background": "#ffffff", "shadow": False, "rounded": True, "font_size": 14,
        "font_color": "#000000", "stroke": "#000000",
        "palette": {
            "client": "#ffffff", "service": "#ffffff", "database": "#ffffff",
            "cache": "#ffffff", "vectorstore": "#ffffff", "llm": "#ffffff",
            "api": "#ffffff", "queue": "#ffffff", "external": "#ffffff",
            "cloud": "#ffffff", "actor": "#ffffff", "process": "#ffffff",
            "decision": "#ffffff", "terminal": "#ffffff", "io": "#ffffff",
            "browser": "#ffffff", "stream": "#ffffff", "default": "#ffffff",
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
