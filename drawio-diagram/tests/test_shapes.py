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

def test_shape_for_returns_expected_shape_for_each_kind():
    # Source of truth: shapes.KIND_TO_SHAPE. If the table changes, update here too.
    expected = {
        "client": "rounded_rect", "browser": "rounded_rect",
        "service": "rounded_rect", "api": "hexagon",
        "database": "cylinder3", "cache": "cylinder3",
        "vectorstore": "cylinder3", "queue": "process",
        "stream": "process", "external": "cloud", "cloud": "cloud",
        "llm": "rounded_rect", "actor": "actor",
        "process": "rounded_rect", "decision": "rhombus",
        "terminal": "rounded_rect", "io": "parallelogram",
        "start": "rounded_rect", "end": "rounded_rect",
    }
    for kind, shape in expected.items():
        assert shapes.shape_for(kind) == shape


# --- cloud_icon() ---

def test_cloud_icon_aws_s3_returns_aws4_stencil():
    s = shapes.cloud_icon("aws", "s3")
    assert isinstance(s, str)
    assert "mxgraph.aws4." in s
    assert "html=1" in s


def test_cloud_icon_azure_uses_azure_namespace():
    s = shapes.cloud_icon("azure", "function_apps")
    assert "mxgraph.azure." in s


def test_cloud_icon_gcp_uses_gcp_namespace():
    s = shapes.cloud_icon("gcp", "bigquery")
    assert "mxgraph.gcp." in s


def test_cloud_icon_known_catalog_entries_render_stencils():
    # spot-check a few curated entries from each provider
    for prov, svc in [("aws", "lambda"), ("aws", "dynamodb"),
                      ("gcp", "cloud_storage"), ("azure", "sql_database")]:
        s = shapes.cloud_icon(prov, svc)
        assert "html=1" in s
        # the service name appears in the shape string
        assert svc in s


def test_cloud_icon_provider_prefix_in_shape():
    # the returned string embeds the service name so a render test can assert
    s = shapes.cloud_icon("aws", "s3")
    assert "s3" in s
