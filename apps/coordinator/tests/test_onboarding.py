"""Sprint 36: the outside-participant onboarding proof.

The roadmap exit condition: an outside participant can discover the project,
download the worker, install it, configure contribution, join, receive approved
work, and earn contribution credit *without developer assistance*.

These tests pin the pieces that make that true and deterministic without a live
server: the public workload catalog, the documented endpoints existing on the
app, the static website wiring, the participant docs, and the onboarding
script's verdict logic. The live end-to-end run is
`scripts/onboard_participant.py`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.main import app
from app.services.readiness import collect_route_paths
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
WEBSITE = REPO_ROOT / "apps" / "website"
DOCS = REPO_ROOT / "docs"

_spec = importlib.util.spec_from_file_location(
    "onboard_participant", REPO_ROOT / "scripts" / "onboard_participant.py"
)
assert _spec and _spec.loader
onboard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(onboard)


# ---- public workload catalog -------------------------------------------------


def test_public_catalog_served_without_auth(client: TestClient):
    resp = client.get("/workloads")  # deliberately no Authorization header
    assert resp.status_code == 200
    catalog = resp.json()
    names = [w["name"] for w in catalog]
    assert names == sorted(names)
    assert set(names) == {
        "hello_compute",
        "stats_range",
        "embeddings",
        "image_generate",
    }


def test_public_catalog_describes_requirements(client: TestClient):
    by_name = {w["name"]: w for w in client.get("/workloads").json()}
    for entry in by_name.values():
        assert entry["version"]
        assert entry["description"]
        assert "requirements" in entry
        assert isinstance(entry["gpu"], bool)
    assert by_name["hello_compute"]["gpu"] is False
    assert by_name["image_generate"]["gpu"] is True
    assert by_name["image_generate"]["requirements"].get("min_vram_mb") == 2048


def test_public_catalog_has_no_signature(client: TestClient):
    """The visitor view is the human contract; signing stays on the customer API."""
    for entry in client.get("/workloads").json():
        assert "signature" not in entry


# ---- documented endpoints actually exist -------------------------------------


def test_documented_endpoints_exist_on_app():
    paths = collect_route_paths(app.routes)
    for endpoint in onboard.DOCUMENTED_ENDPOINTS:
        _, path = endpoint.split(" ", 1)
        assert path in paths, f"{endpoint} is documented but not served"


def test_joinslide_docs_exist():
    for rel in onboard.SUPPORT_DOCS:
        assert (REPO_ROOT / rel).is_file(), f"missing participant doc {rel}"


# ---- onboarding script verdict logic -----------------------------------------


def test_plan_is_ordered_and_documented():
    steps = onboard.plan()
    assert len(steps) >= 5
    assert "worker --setup" in steps[1]
    assert "--enroll" in steps[2]
    assert "credit" in steps[-1]


def test_summarize_requires_all_three_conditions():
    worker = {"status": "online"}
    stats = {"attempts": 2, "completed_units": 2}
    credits = {"earned": 2, "balance": 2}
    assert onboard.summarize(worker, stats, credits)["ok"] is True

    # joined but never received work -> not done
    assert onboard.summarize(worker, {"attempts": 0, "completed_units": 0},
                            credits)["ok"] is False
    # received work but earned nothing -> not done
    assert onboard.summarize(worker, stats, {"earned": 0, "balance": 0})["ok"] is False
    # nothing at all -> not done
    assert onboard.summarize(None, None, None)["ok"] is False


def test_render_reports_the_exit_condition():
    text = onboard.render(onboard.summarize(
        {"status": "online"},
        {"attempts": 1, "completed_units": 1},
        {"earned": 1, "balance": 1},
    ))
    assert "joined" in text
    assert "earned credit" in text
    assert "exit condition met" in text
    assert "yes" in text


# ---- static website ----------------------------------------------------------


def test_website_assets_exist():
    assert (WEBSITE / "index.html").is_file()
    assert (WEBSITE / "styles.css").is_file()
    assert (WEBSITE / "app.js").is_file()


def test_website_loads_public_catalog_and_states_beta():
    html = (WEBSITE / "index.html").read_text(encoding="utf-8")
    app_js = (WEBSITE / "app.js").read_text(encoding="utf-8")
    assert "styles.css" in html
    assert "app.js" in html
    assert "/workloads" in app_js
    assert "enrollment token" in html.lower()
    assert "beta" in html.lower()


def test_serve_website_points_at_apps_website():
    source = (REPO_ROOT / "scripts" / "serve_website.py").read_text(encoding="utf-8")
    assert '"website"' in source


# ---- participant docs describe the documented path ---------------------------


def test_getting_started_covers_the_join_path():
    text = (DOCS / "getting-started.md").read_text(encoding="utf-8")
    for needle in ("--setup", "--enroll", "enrollment token", "/workloads",
                   "credits", "--diagnostics"):
        assert needle in text


def test_support_doc_offers_redacted_diagnostics():
    text = (DOCS / "support.md").read_text(encoding="utf-8")
    assert "--diagnostics" in text
    assert "--status" in text
    assert "revoke" in text
