"""Acceptance criteria from the brief:
  * session and funnel definitions are documented
  * event deduplication works
  * drop-off metrics are reproducible
  * identity stitching respects consent
plus fixed-seed reproducibility of every exported file.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from journeylab.config import GeneratorConfig, INACTIVITY_TIMEOUT_MS
from journeylab.evaluate import frame_hash
from journeylab.export import export, load_tables, load_truth, sqlite_check
from journeylab.generate import build
from journeylab.pipeline import consent_lookup, run_pipeline, stitch, to_ms
from journeylab.taxonomy import FUNNEL_STAGES, OUTCOME_RULES, EVENT_TAXONOMY
from journeylab.validate import validate

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- documented definitions
def test_session_and_funnel_definitions_documented():
    readme = (ROOT / "README.md").read_text()
    meth = (ROOT / "docs" / "methodology.md").read_text()
    assert "30-minute inactivity" in meth and "Sessionization" in meth
    for _, name, ev in FUNNEL_STAGES:
        assert name in meth and ev in meth
    for rid, name, _ in OUTCOME_RULES:
        assert rid in meth and name in meth
    for e in EVENT_TAXONOMY:
        assert e[0] in meth
    assert "Quick start" in readme


# ---------------------------------------------------------------- dedup
def test_event_deduplication_works(ds, ev_report):
    an = ds.truth["anomalies"]
    dropped = set(ds.derived["dedup_decisions"].event_id)
    labelled = set(an.loc[an.issue_type == "duplicate_conversion", "entity_id"])
    assert dropped == labelled and len(labelled) > 0
    clean = ds.derived["events_clean"]
    assert not clean.client_event_id.duplicated().any()
    pur = clean[clean.event_type == "purchase"]
    assert pur.order_id.is_unique
    assert len(pur) == len(ds.tables["order"])
    raw = ds.tables["journey_event"]
    assert (raw.event_type == "purchase").sum() > len(ds.tables["order"])      # double counting existed
    assert ev_report["deduplication"]["reconciled"]


def test_resequencing_by_event_time(ds):
    clean = ds.derived["events_clean"]
    t = clean._ts.to_numpy()
    s = clean.session_id.to_numpy()
    same = s[1:] == s[:-1]
    assert (np.diff(t)[same] >= 0).all()
    flagged = set(ds.derived["resequenced_sessions"].query("events_out_of_order > 0").session_id)
    an = ds.truth["anomalies"]
    assert flagged == set(an.loc[an.issue_type == "ingestion_order_inversion", "session_id"])


def test_sessionization_rule(ds):
    sc = ds.derived["sessionization"]
    assert sc["event_time"]["match_rate"] == 1.0
    assert sc["ingestion_time"]["match_rate"] < 1.0       # ordering by arrival would break sessions
    assert sc["max_within_session_gap_min"] <= INACTIVITY_TIMEOUT_MS / 60000


# ---------------------------------------------------------------- consent-aware stitching
def test_identity_stitching_respects_consent(ds, ev_report):
    clean = ds.derived["events_clean"]
    st = clean.stitched_customer_id.to_numpy(dtype=object)
    has = pd.notna(st)
    assert has.any()
    ok = consent_lookup(ds.tables["consent_event"], st, clean._ts.to_numpy())
    assert not (has & ~ok).any(), "stitched an event without active analytics consent"
    # customers without any consent record are never stitched
    unknown = set(ds.tables["customer"].query("analytics_consent_status == 'unknown'").customer_id)
    no_rec = unknown - set(ds.tables["consent_event"].query("consent_type == 'analytics'").customer_id)
    assert not set(st[has]) & no_rec
    # blocked events exist (consent gaps were exercised)
    assert (clean.stitch_status == "blocked_no_consent").any()
    # detected bots are never stitched, incl. cookie-replay bots carrying a real customer's cookie
    bots = set(ds.derived["bot_scores"].query("is_bot_detected").session_id)
    assert clean[clean.session_id.isin(bots)].stitched_customer_id.isna().all()
    assert ev_report["identity_stitching"]["consent_violations_events"] == 0
    assert ev_report["identity_stitching"]["naive_consent_violations_events"] > 0


def test_consent_lookup_semantics():
    ce = pd.DataFrame(dict(customer_id=["C1", "C1", "C1", "C2"], consent_type="analytics",
                           action=["granted", "withdrawn", "granted", "denied"],
                           effective_at=["2026-01-01T00:00:00.000Z", "2026-02-01T00:00:00.000Z",
                                         "2026-03-01T00:00:00.000Z", "2026-01-01T00:00:00.000Z"]))
    ts = to_ms(pd.Series(["2025-12-31T00:00:00.000Z", "2026-01-15T00:00:00.000Z", "2026-02-15T00:00:00.000Z",
                          "2026-03-15T00:00:00.000Z", "2026-01-15T00:00:00.000Z", "2026-01-15T00:00:00.000Z"]))
    got = consent_lookup(ce, np.array(["C1", "C1", "C1", "C1", "C2", None], dtype=object), ts)
    assert got.tolist() == [False, True, False, True, False, False]


def test_incorrect_merges_rejected(ev_report):
    x = ev_report["identity_link_review"]
    assert x["recall"] >= 0.8
    st = ev_report["identity_stitching"]
    assert st["wrong_customer_sessions"] < st["naive_wrong_customer_sessions"]


def test_bot_detection_quality(ev_report):
    b = ev_report["bot_detection"]
    assert b["precision"] >= 0.9 and b["recall"] >= 0.8
    assert b["recall_by_type"]["cookie_replay"] >= 0.9
    assert b["human_false_positive_rate"] < 0.01


# ---------------------------------------------------------------- reproducibility
def test_dropoff_metrics_reproducible(ds, cfg):
    again = build(cfg, log=lambda *_: None)
    assert frame_hash(again.derived["funnel_metrics"]) == frame_hash(ds.derived["funnel_metrics"])
    assert frame_hash(again.derived["friction_paths"]) == frame_hash(ds.derived["friction_paths"])
    other = build(GeneratorConfig(seed=cfg.seed + 1, scale=cfg.scale), log=lambda *_: None)
    assert frame_hash(other.derived["funnel_metrics"]) != frame_hash(ds.derived["funnel_metrics"])


def test_dropoff_metrics_reproducible_from_exported_files(ds, tmp_path):
    export(ds, tmp_path / "d", formats=("csv",))
    t = load_tables(tmp_path / "d" / "data")
    res = run_pipeline(t)
    a = pd.read_csv(tmp_path / "d" / "derived" / "funnel_metrics.csv")
    b = pd.read_csv(pd.io.common.StringIO(res["funnel_metrics"].to_csv(index=False)))
    pd.testing.assert_frame_equal(a, b)
    rep = validate(t, load_truth(tmp_path / "d" / "ground_truth"))
    assert rep.ok, rep.df().query("status != 'PASS'").to_string()


def test_same_seed_same_checksums(cfg, tmp_path):
    mans = []
    for tag in ("a", "b"):
        d = build(cfg, log=lambda *_: None)
        mans.append(export(d, tmp_path / tag, formats=("csv", "json", "sql")))
    fa = {f["path"]: (f["rows"], f["sha256"]) for f in mans[0]["files"]}
    fb = {f["path"]: (f["rows"], f["sha256"]) for f in mans[1]["files"]}
    assert fa == fb and len(fa) > 40


def test_sqlite_foreign_keys(ds, tmp_path):
    res = sqlite_check(ds.tables, tmp_path / "x.sqlite")
    assert res["foreign_key_violations"] == 0 and res["joins_complete"]


def test_manifest_provenance(ds, tmp_path):
    man = export(ds, tmp_path / "m", formats=("csv",))
    assert man["seed"] == 20261022 and "generate" in man["generator_command"]
    assert man["provenance"]["external_sources"] == []
    assert all(len(f["sha256"]) == 64 for f in man["files"])
