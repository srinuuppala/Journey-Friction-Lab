"""The website's data files can be built from an exported dataset."""
import json

from journeylab.dashboard import build_dashboard
from journeylab.export import export


def test_dashboard_data_builds(ds, report, ev_report, tmp_path):
    from journeylab.cli import _reports
    export(ds, tmp_path / "d", formats=("csv",), extra_reports=_reports(ds, report, ev_report))
    dash = build_dashboard(tmp_path / "d", tmp_path / "web")
    saved = json.loads((tmp_path / "web" / "data" / "dashboard.json").read_text())
    assert saved["kpis"]["sessions"] == len(ds.tables["session"])
    assert saved["kpis"]["orders"] == len(ds.tables["order"])
    assert [s["stage"] for s in saved["funnel"]["all"]][0] == "visit"
    assert len(saved["incidents"]["series"]) == 4
    sessions = json.loads((tmp_path / "web" / "data" / "sessions.json").read_text())
    assert sessions and all(s["events"] for s in sessions)
    assert dash["quality"]["validation"]["passed"]


def test_website_files_exist():
    from pathlib import Path
    web = Path(__file__).resolve().parents[1] / "web"
    for f in ("index.html", "app.js", "charts.js", "styles.css", "data/dashboard.json", "data/sessions.json"):
        assert (web / f).exists(), f
