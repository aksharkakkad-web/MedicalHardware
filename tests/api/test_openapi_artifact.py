import json
from pathlib import Path

from backend.app.openapi import generate_openapi_document, render_openapi_document


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_ARTIFACT = PROJECT_ROOT / "docs/openapi/product-api-v1.json"


def test_committed_openapi_artifact_matches_the_real_application() -> None:
    committed = json.loads(OPENAPI_ARTIFACT.read_text(encoding="utf-8"))

    assert committed == generate_openapi_document()
    assert OPENAPI_ARTIFACT.read_text(encoding="utf-8") == (
        render_openapi_document(committed)
    )


def test_openapi_operation_ids_are_present_and_unique() -> None:
    document = generate_openapi_document()
    operation_ids = [
        operation["operationId"]
        for path in document["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]

    assert operation_ids
    assert len(operation_ids) == len(set(operation_ids))
    assert document["paths"]["/v1/events"]["get"]["operationId"] == (
        "listClinicEvents"
    )


def test_every_v1_operation_documents_development_access_headers() -> None:
    document = generate_openapi_document()
    for route, path in document["paths"].items():
        if not route.startswith("/v1"):
            continue
        for method, operation in path.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            parameters = {item["name"] for item in operation["parameters"]}
            assert {"X-Tenant-Id", "X-Actor-Id"} <= parameters

