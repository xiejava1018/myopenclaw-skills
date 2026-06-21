# Shapes & Cloud Icons

Two shape systems: **generic kind→shape** (default) and **cloud icons** (opt-in via `provider`/`service`). When a node carries both, the cloud icon wins.

## Generic shapes: `kind → shape`

Every node has a `kind`; the engine maps it to a draw.io shape. This is the default — use it for abstract/logical diagrams where the specific product doesn't matter.

| `kind` | draw.io shape | Visual |
|--------|--------------|--------|
| `client`, `browser` | rounded rect | box |
| `service`, `process`, `llm`, `terminal`, `start`, `end`, `state` | rounded rect | box |
| `api` | hexagon | hexagon |
| `database`, `cache`, `vectorstore` | cylinder3 | cylinder |
| `queue`, `stream` | process bar | rectangle with inner lines |
| `external`, `cloud` | cloud | cloud |
| `actor` | actor | stick figure |
| `decision` | rhombus | diamond |
| `io` | parallelogram | parallelogram |
| *(unknown/omitted)* | rounded rect | default box |

## Cloud icons

For diagrams tied to a specific cloud, add `provider` + `service` to a node and the engine renders the real provider glyph (AWS/Azure/GCP marks) instead of the generic shape. Both fields are **optional** — omit them and nothing changes.

```json
{"id": "store", "label": "Product Images", "kind": "database",
 "provider": "aws", "service": "s3"}
```

Rules:
- `provider` must be one of `aws`, `azure`, `gcp` (rejected otherwise).
- `service` requires `provider` (a service glyph without a provider is rejected).
- `kind` is still required (used for layout sizing and as a fallback description).

### AWS catalog (`provider: "aws"` → `mxgraph.aws4.*`)

`s3`, `lambda`, `dynamodb`, `rds`, `sqs`, `sns`, `cloudfront`, `ec2`, `vpc`, `kinesis`, `iam`, `cloudwatch`, `api_gateway`, `elasticache`, `redshift`, `sagemaker`, `cloudtrail`, `route_53`, `autoscaling`, `cognito`

### GCP catalog (`provider: "gcp"` → `mxgraph.gcp.*`)

`cloud_storage`, `cloud_functions`, `cloud_run`, `bigquery`, `cloud_sql`, `cloud_pubsub`, `google_kubernetes_engine`, `cloud_firestore`, `compute_engine`, `virtual_private_cloud`, `cloud_tasks`, `cloud_load_balancing`

### Azure catalog (`provider: "azure"` → `mxgraph.azure.*`)

`function_apps`, `sql_database`, `web_apps`, `api_management`, `virtual_networks`, `cosmos_db`, `service_bus`, `storage_accounts`, `cache_redis`, `kubernetes_services`, `event_grid`, `application_gateways`

An unknown `service` falls back to the provider's generic resource icon (still branded), so the node never renders as an empty box.

## When to use which

- **Generic shapes** — logical/conceptual architecture, vendor-neutral diagrams, flowcharts, anything where "a database" matters more than "DynamoDB specifically".
- **Cloud icons** — deployment diagrams, cloud-migration plans, cost-anchored architectures, or any diagram where the reader benefits from recognizing exact products. Use them consistently within one diagram — don't mix one branded node with five generic ones unless the generic ones are genuinely vendor-agnostic.

Stencils are built into the draw.io desktop CLI; no extra assets or downloads are needed.
