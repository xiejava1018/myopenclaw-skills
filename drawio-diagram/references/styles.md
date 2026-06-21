# Visual Styles

`diagram.style` drives palette, typography, shadows, and corner rounding. Five
named styles; pick one per diagram and keep it consistent. **Default = `enterprise`** — reach for it unless you have a reason not to.

## Swatch table

| Style | Background | Key fills (client / service / database) | Shadow | Rounded | Best for |
|-------|-----------|------------------------------------------|--------|---------|----------|
| `enterprise` | `#ffffff` white | `#dae8fc` blue / `#d5e8d4` green / `#ffe6cc` peach | off | on | Default. Neutral, readable, client-ready diagrams |
| `flat` | `#ffffff` white | same pastel blocks as enterprise, slightly darker stroke `#555` | off | on | Modern decks / docs wanting a flatter, less outlined look |
| `notion` | `#ffffff` white | near-gray `#e8e8e8` / `#e8e8e8` / `#d6d6d6` | off | **off** (sharp corners) | Notion-style docs, wiki embeds, minimal monochrome |
| `claude` | `#f8f6f3` warm cream | `#efe7d6` / `#e6dcc4` / `#dcc9a8` warm tans | **on** | on | Warm, editorial, presentation/report aesthetic |
| `openai` | `#ffffff` white | `#ffffff` / `#ffffff` / `#ffffff` all white | off | on | High-contrast black-on-white, print, accessibility |

All styles share the same edge palette (color encodes `flow`, see `diagram-types.md`):

| Flow | Color | Line |
|------|-------|------|
| `data` | `#2563eb` blue | solid, width 2 |
| `control` | `#ea580c` orange | solid, width 1.5 |
| `async` | `#6b7280` gray | **dashed**, width 1.5 |
| `memory_read` / `memory_write` | `#059669` green | read solid / write dashed |
| `feedback` | `#7c3aed` purple | solid |
| `default` (no flow set) | `#404040` dark gray | solid |

## Choosing a style

- **`enterprise`** — the safe default. Distinct pastels per node kind (client=blue, service=green, data=peach, vectorstore=lilac, queue=red), clean strokes. Use unless you specifically want a different mood.
- **`flat`** — same palette as enterprise with a heavier stroke for a flatter, more poster-like feel. Good for slide decks.
- **`notion`** — monochrome grays, no rounded corners. Ideal for embedding in Notion/wiki pages where you want the diagram to feel like part of the doc, not a graphic.
- **`claude`** — warm cream background with soft shadows. Pick for client reports, one-pagers, editorial layouts where warmth matters.
- **`openai`** — strict black-on-white (white fill, black stroke + font). Best for print, PDF, high-contrast/accessibility needs, and brand alignment with minimal aesthetics.

## Notes

- Font color is always dark (black or near-black) for readability. Node fills are always light enough to contrast with it — no style produces unreadable text.
- Shadows are off by default everywhere except `claude`.
- Rounded corners are on everywhere except `notion`.
- Only `enterprise`/`flat` carry the full per-kind palette (queue=red, vectorstore=lilac, etc.); the others reduce to fewer hues for a more uniform look, falling back to `default` for unmapped kinds.
