# Diagram Types — Pick & Fill

Five diagram types. Choose by the **question the diagram answers**, then fill the semantic fields — never coordinates, the engine owns layout.

| Question | Type |
|----------|------|
| "What are the components and how do they connect, by layer?" | `architecture` |
| "What is the step-by-step procedure / branching logic?" | `flowchart` |
| "Who talks to whom, and in what order, over time?" | `sequence` |
| "What entities exist and how are they related (data model)?" | `er` |
| "What states can a thing be in, and how does it transition?" | `state` |

All types share `type`, `title`, `style`. Edges in graph types take `flow` (color-codes the arrow — see `styles.md`). Common optional hints: `label` on any edge; `direction` (`"tb"`/`"lr"`) on architecture/flowchart.

---

## architecture

Layered component diagram. Use for system overviews, service maps, deployment topologies.

Required: `layers` (ordered bands), `nodes`, `edges`.
- `layers[i]`: `{id, label, nodes: [node_ids]}` — a node belongs to exactly one layer.
- `nodes[i]`: `{id, label, kind}`. Optional: `provider`+`service` for cloud glyphs (see `drawio-shapes.md`).
- `edges[i]`: `{source, target, flow?, label?}`. `flow` ∈ data/control/async/...

```json
{"type":"architecture","style":"enterprise","title":"RAG","direction":"tb",
 "layers":[{"id":"L0","label":"Client","nodes":["app"]},
           {"id":"L1","label":"API","nodes":["gw"]}],
 "nodes":[{"id":"app","label":"Web","kind":"client"},
          {"id":"gw","label":"Gateway","kind":"api"}],
 "edges":[{"source":"app","target":"gw","flow":"data"}]}
```
Layout: top-to-bottom bands, one row per layer.

## flowchart

Procedural/branching logic. Use for algorithms, business processes, decision trees.

Required: `nodes`, `edges`.
- `nodes[i]`: `{id, label, kind}`. Kinds drive shape: `terminal` (start/end pill), `io` (parallelogram), `decision` (diamond), `process` (box).
- `edges[i]`: `{source, target, label?, flow?}`.

```json
{"type":"flowchart","style":"enterprise","title":"Checkout",
 "nodes":[{"id":"s","label":"Start","kind":"terminal"},
          {"id":"d","label":"In stock?","kind":"decision"},
          {"id":"p","label":"Pay","kind":"process"}],
 "edges":[{"source":"s","target":"d"},{"source":"d","target":"p","label":"yes"}]}
```
Layout: ranked top-to-bottom (or left-right with `direction:"lr"`), decisions branch.

## sequence

Time-ordered interactions between participants. Use for request/response flows, protocols, RPC traces.

Required: `participants`, `messages`.
- `participants[i]`: `{id, label, kind?}` — `kind: actor` draws a stick figure.
- `messages[i]`: `{from, to, label, dashed?}`. `dashed: true` = response/async (dotted arrow).

```json
{"type":"sequence","style":"enterprise","title":"Login",
 "participants":[{"id":"u","label":"User","kind":"actor"},
                 {"id":"api","label":"API"}],
 "messages":[{"from":"u","to":"api","label":"POST /login"},
             {"from":"api","to":"u","label":"200 OK","dashed":true}]}
```
Layout: participants as vertical lifelines left-to-right; messages ordered top-to-bottom.

## er (entity-relationship)

Data model. Use for database schemas, domain models.

Required: `entities`, `relationships`.
- `entities[i]`: `{id, label, attributes: [{name, pk?, fk?}]}`. `pk` underlines, `fk` italicizes.
- `relationships[i]`: `{from, to, card?, label?}`. `card` e.g. `"1:N"` rendered as the edge label.

```json
{"type":"er","style":"enterprise","title":"Shop",
 "entities":[{"id":"user","label":"User","attributes":[{"name":"id","pk":true}]},
             {"id":"order","label":"Order","attributes":[{"name":"user_id","fk":true}]}],
 "relationships":[{"from":"user","to":"order","card":"1:N"}]}
```
Layout: grid of entity boxes with 3-compartment HTML labels (name / attributes).

## state

State machine. Use for object lifecycles, protocol states, order/status flows.

Required: `states`, `transitions`, `initial`. Optional: `final: [ids]`.
- `states[i]`: `{id, label}`.
- `transitions[i]`: `{from, to, label?}`.
- `initial`: a state id (drawn with an initial pseudo-state arrow into it).
- `final`: list of state ids (drawn with bullseye final pseudo-states).

```json
{"type":"state","style":"enterprise","title":"Order","initial":"new",
 "states":[{"id":"new","label":"New"},{"id":"paid","label":"Paid"}],
 "transitions":[{"from":"new","to":"paid","label":"pay"}],
 "final":["paid"]}
```
Layout: states as rounded boxes; initial arrow enters the start state; finals get bullseye glyphs.
