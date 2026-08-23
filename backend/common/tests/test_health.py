"""Health check (spec 09 §8)."""

import pytest

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("url", ["/health/", "/api/v1/health/"])
def test_health_est_accessible_sans_authentification(client, url):
    response = client.get(url)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"] == {"database": "ok", "cache": "ok"}
    assert payload["version"]
    assert payload["time"]


def test_health_repond_503_si_la_base_est_indisponible(client, monkeypatch):
    monkeypatch.setattr("common.views._check_database", lambda: False)

    response = client.get("/health/")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["database"] == "error"
