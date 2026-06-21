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
    "state": "rounded_rect",
}
DEFAULT_SHAPE = "rounded_rect"


def shape_for(kind: str | None) -> str:
    return KIND_TO_SHAPE.get(kind or "", DEFAULT_SHAPE)


# --- Cloud provider service -> draw.io stencil shape name ---
# Curated high-frequency services. The draw.io desktop CLI ships the
# mxgraph.aws4.*, mxgraph.azure.*, mxgraph.gcp.* shape libraries built-in, so
# these render as the real provider glyphs without any extra assets.
#
# The value is the exact service suffix appended to the provider namespace, e.g.
# CLOUD_SERVICES["aws"]["s3"] -> "s3" -> shape "mxgraph.aws4.s3".
# Stencil names were verified by rendering probes through the draw.io CLI.
CLOUD_SERVICES: dict[str, dict[str, str]] = {
    "aws": {
        "s3": "s3", "lambda": "lambda", "dynamodb": "dynamodb", "rds": "rds",
        "sqs": "sqs", "sns": "sns", "cloudfront": "cloudfront", "ec2": "ec2",
        "vpc": "vpc", "kinesis": "kinesis", "iam": "iam",
        "cloudwatch": "cloudwatch", "api_gateway": "api_gateway",
        "elasticache": "elasticache", "redshift": "redshift",
        "sagemaker": "sagemaker", "cloudtrail": "cloudtrail",
        "route_53": "route_53", "autoscaling": "autoscaling",
        "cognito": "cognito",
    },
    "gcp": {
        "cloud_storage": "cloud_storage", "cloud_functions": "cloud_functions",
        "cloud_run": "cloud_run", "bigquery": "bigquery",
        "cloud_sql": "cloud_sql", "cloud_pubsub": "cloud_pubsub",
        "google_kubernetes_engine": "google_kubernetes_engine",
        "cloud_firestore": "cloud_firestore", "compute_engine": "compute_engine",
        "virtual_private_cloud": "virtual_private_cloud",
        "cloud_tasks": "cloud_tasks", "cloud_load_balancing": "cloud_load_balancing",
    },
    "azure": {
        "function_apps": "function_apps", "sql_database": "sql_database",
        "web_apps": "web_apps", "api_management": "api_management",
        "virtual_networks": "virtual_networks", "cosmos_db": "cosmos_db",
        "service_bus": "service_bus", "storage_accounts": "storage_accounts",
        "cache_redis": "cache_redis",
        "kubernetes_services": "kubernetes_services",
        "event_grid": "event_grid", "application_gateways": "application_gateways",
    },
}

# draw.io shape namespace prefix per provider.
_PROVIDER_NS = {"aws": "mxgraph.aws4", "azure": "mxgraph.azure", "gcp": "mxgraph.gcp"}


def cloud_icon(provider: str, service: str) -> str:
    """Return a draw.io cell style string that renders the real provider glyph.

    provider: one of aws/azure/gcp (validated upstream by schema).
    service:  the service key in CLOUD_SERVICES[provider]. Unknown services
              fall back to the provider's generic cloud/group shape so the node
              still renders (as a branded box) rather than a blank.

    Returns a style string like 'shape=mxgraph.aws4.s3;html=1;...'.
    """
    ns = _PROVIDER_NS[provider]
    suffix = CLOUD_SERVICES.get(provider, {}).get(service, "resourceIcon")
    return f"shape={ns}.{suffix};html=1;outlineConnect=0;"
