# diagram.json — Input Contract

This is the **authoritative input schema** for `drawio-diagram`. Claude fills a
`diagram.json` object that conforms to this contract; `scripts/schema.py`
validates it before any layout or rendering happens.

Validation is **fail-fast with precise messages**. Every rejected input raises
`SchemaError` with a message that pinpoints the offending field (e.g.
`"edge: unknown node reference 'gw'"`). Fix the JSON and re-run — never hand-edit
layout output to paper over a schema error.

## Global rules (apply to every type)

- `type` — required. One of `architecture`, `flowchart`, `sequence`, `er`, `state`.
- `title` — required. Human-readable diagram title (also rendered as the frame label).
- `style` — required. One of `enterprise`, `flat`, `notion`, `claude`, `openai`. Drives palette + typography.
- **No coordinates allowed.** `x`, `y`, `width`, `height`, `geometry`, `position` are rejected anywhere. The engine computes all geometry.
- `id` fields are strings, unique within their collection, and referenced exactly.

> Optional layout **hints** (see below) influence *direction* or *cardinality*,
> never absolute position.

## Common optional layout hints

These may appear on edges/relationships in any type unless noted:

| Hint | Applies to | Effect |
|------|-----------|--------|
| `direction` | architecture (top-level), flowchart (top-level) | `"TB"` (top-bottom) or `"LR"` (left-right). Defaults per style. |
| `label` | any edge | Text rendered on the connector. |
| `dashed` | any edge (bool) | Renders a dashed connector (e.g. async / optional flows). |
| `flow` | architecture edge | `"data"`, `"control"`, `"sync"` — drives connector color/style. |
| `card` | er relationship | `"1:1"`, `"1:N"`, `"N:M"` — rendered as crow's-foot ends. |
| `guard` | state transition | Condition text (e.g. `[authenticated]`) rendered on the arrow. |
| `pk` | er attribute (bool) | Marks primary key (underline + key glyph). |
| `fk` | er attribute (bool) | Marks foreign key (italic + FK suffix). |

## `kind` → shape

Every node/participant/entity/state may carry a `kind` string. `kind` maps to a
draw.io **shape stencil** (and optional icon). The full `kind` → shape catalog
lives in [`drawio-shapes.md`](./drawio-shapes.md) (added in a later phase).
Until that file exists, use these provisional values:

- **architecture nodes**: `client`, `api`, `service`, `database`, `queue`, `cache`, `storage`, `external`
- **flowchart nodes**: `terminal` (start/end), `process`, `decision`, `io`, `subprocess`
- **sequence participants**: `actor`, `service`, `database`, `external`
- **er entities**: (no `kind`; shape is always the entity/table box)
- **state**: (no `kind`; shape is always a rounded state node)

`kind` is **optional** in the schema — omitting it yields a sensible default
shape per type. Unknown `kind` values are not rejected in Phase 0; they will be
validated once `drawio-shapes.md` lands.

---

## Per-type reference

### architecture

Layered system diagram. Nodes are grouped into swimlane-like **layers**; edges
cross layers.

```json
{
  "type": "architecture",
  "style": "enterprise",
  "title": "电商下单链路",
  "direction": "TB",
  "layers": [
    {"id": "client",  "label": "客户端",   "nodes": ["web", "app"]},
    {"id": "edge",    "label": "接入层",   "nodes": ["gw"]},
    {"id": "service", "label": "业务层",   "nodes": ["order", "pay"]},
    {"id": "data",    "label": "数据层",   "nodes": ["db", "cache"]}
  ],
  "nodes": [
    {"id": "web",   "label": "Web 站点",   "kind": "client"},
    {"id": "app",   "label": "移动 App",   "kind": "client"},
    {"id": "gw",    "label": "网关",       "kind": "api"},
    {"id": "order", "label": "订单服务",   "kind": "service"},
    {"id": "pay",   "label": "支付服务",   "kind": "service"},
    {"id": "db",    "label": "MySQL",      "kind": "database"},
    {"id": "cache", "label": "Redis",      "kind": "cache"}
  ],
  "edges": [
    {"source": "web",  "target": "gw",    "flow": "data"},
    {"source": "app",  "target": "gw",    "flow": "data"},
    {"source": "gw",   "target": "order", "flow": "data"},
    {"source": "order","target": "pay",   "flow": "sync", "dashed": true},
    {"source": "order","target": "db",    "flow": "data"},
    {"source": "order","target": "cache", "flow": "data"}
  ]
}
```

**Required:** `layers`, `nodes`, `edges`.
**Constraints:** every `layer.nodes[]` id must exist in `nodes`; every edge
`source`/`target` must exist in `nodes`.

### flowchart

Process / decision flow.

```json
{
  "type": "flowchart",
  "style": "enterprise",
  "title": "用户登录",
  "direction": "TB",
  "nodes": [
    {"id": "start",   "label": "开始",        "kind": "terminal"},
    {"id": "input",   "label": "输入凭据",    "kind": "process"},
    {"id": "check",   "label": "凭据正确?",   "kind": "decision"},
    {"id": "ok",      "label": "签发 Token",  "kind": "process"},
    {"id": "fail",    "label": "返回错误",    "kind": "process"},
    {"id": "end",     "label": "结束",        "kind": "terminal"}
  ],
  "edges": [
    {"source": "start", "target": "input"},
    {"source": "input", "target": "check"},
    {"source": "check", "target": "ok",   "label": "是"},
    {"source": "check", "target": "fail", "label": "否"},
    {"source": "ok",    "target": "end"},
    {"source": "fail",  "target": "end"}
  ]
}
```

**Required:** `nodes`, `edges`.
**Constraints:** every edge `source`/`target` must exist in `nodes`.

### sequence

Time-ordered message exchange between participants (lifelines).

```json
{
  "type": "sequence",
  "style": "enterprise",
  "title": "下单时序",
  "participants": [
    {"id": "usr",  "label": "用户",   "kind": "actor"},
    {"id": "web",  "label": "Web",    "kind": "service"},
    {"id": "api",  "label": "API",    "kind": "service"},
    {"id": "db",   "label": "DB",     "kind": "database"}
  ],
  "messages": [
    {"from": "usr", "to": "web", "label": "点击下单"},
    {"from": "web", "to": "api", "label": "POST /orders"},
    {"from": "api", "to": "db",  "label": "INSERT"},
    {"from": "db",  "to": "api", "label": "ok", "dashed": true},
    {"from": "api", "to": "web", "label": "201 Created", "dashed": true},
    {"from": "web", "to": "usr", "label": "下单成功", "dashed": true}
  ]
}
```

**Required:** `participants`, `messages`.
**Constraints:** every message `from`/`to` must exist in `participants`.
**Convention:** `dashed: true` marks a return/response message.

### er (entity-relationship)

Data model with entities, attributes, and cardinal relationships.

```json
{
  "type": "er",
  "style": "enterprise",
  "title": "订单数据模型",
  "entities": [
    {
      "id": "user", "label": "User",
      "attributes": [
        {"name": "id",    "pk": true},
        {"name": "email"},
        {"name": "name"}
      ]
    },
    {
      "id": "order", "label": "Order",
      "attributes": [
        {"name": "id",      "pk": true},
        {"name": "user_id", "fk": true},
        {"name": "amount"},
        {"name": "status"}
      ]
    }
  ],
  "relationships": [
    {"from": "user", "to": "order", "card": "1:N"}
  ]
}
```

**Required:** `entities`, `relationships`.
**Constraints:** every relationship `from`/`to` must exist in `entities`;
each entity must carry an `attributes` list (may be empty).

### state (state machine)

States, an initial state, transitions, and optional final states.

```json
{
  "type": "state",
  "style": "enterprise",
  "title": "订单状态机",
  "initial": "created",
  "states": [
    {"id": "created",  "label": "已创建"},
    {"id": "paid",     "label": "已支付"},
    {"id": "shipped",  "label": "已发货"},
    {"id": "done",     "label": "已完成"},
    {"id": "canceled", "label": "已取消"}
  ],
  "transitions": [
    {"from": "created", "to": "paid",     "label": "支付",   "guard": "[未超时]"},
    {"from": "paid",    "to": "shipped",  "label": "发货"},
    {"from": "shipped", "to": "done",     "label": "签收"},
    {"from": "created", "to": "canceled", "label": "取消"},
    {"from": "paid",    "to": "canceled", "label": "退款"}
  ],
  "final": ["done", "canceled"]
}
```

**Required:** `states`, `transitions`, `initial`.
**Constraints:** `initial` must be a defined state id; every transition
`from`/`to` must be a defined state; every id in `final` (optional) must be a
defined state.

---

## Validation summary (mirrors `schema.py`)

| Check | Failure message contains |
|-------|--------------------------|
| Missing `type` | `missing required field 'type'` |
| Bogus / non-string `type` | `unknown type` |
| Bogus / non-string `style` | `invalid style` |
| Missing required field | `missing required field` |
| Required field not a list | `must be a list` |
| Edge / participant / relationship / layer ref to undefined id | `unknown node reference` |
| Duplicate id within a collection | `duplicate` |
| Coordinate field present | `coordinate field` |
| `initial` not a defined state (or not a string) | `initial` |

A rejection message that does not match the table is a schema bug — fix
`schema.py`. The JSON author is right about intent, wrong only about spelling.
