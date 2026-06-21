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
