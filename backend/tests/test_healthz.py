"""Phase 0 acceptance: /healthz answers, and config loads without error."""

from __future__ import annotations

from fastapi.testclient import TestClient

from apix.main import app


def test_healthz_responds() -> None:
    # DB is not required to be up for the endpoint to *respond*; it reports
    # "error" if unreachable. The Phase 0 acceptance test in CI runs against a
    # live Postgres service container and asserts db == "ok" separately.
    with TestClient(app) as client:
        r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["db"] in {"ok", "error"}
    assert "version" in body
    assert body["version"] == "0.1.0"
