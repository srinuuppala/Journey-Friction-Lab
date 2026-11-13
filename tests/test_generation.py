"""Data-generation acceptance tests: IDs, keys, joins, derived values, edge cases, ground truth."""
import json
import re

import numpy as np
import pandas as pd

from journeylab.config import GeneratorConfig
from journeylab.schema import TABLES
from journeylab.taxonomy import GROUND_TRUTH_ONLY_COLUMNS


def test_scale_is_parameterised(ds, cfg):
    assert len(ds.tables["session"]) == cfg.n_sessions == 2_000
    assert GeneratorConfig(scale=1.0).n_sessions == 100_000
    assert len(ds.tables["customer"]) == cfg.n_customers


def test_validation_suite_passes(report):
    df = report.df()
    failed = df[df.status != "PASS"]
    assert failed.empty, failed.to_string()
    assert len(df) > 300


def test_primary_and_foreign_keys(report):
    df = report.df()
    for cat in ("pk", "fk", "unique"):
        sub = df[df.category == cat]
        assert len(sub) > 0 and (sub.violations == 0).all(), sub[sub.violations > 0]


def test_id_conventions(ds):
    t = ds.tables
    assert t["customer"].customer_id.str.fullmatch(r"CUS-\d{6}").all()
    assert t["session"].session_id.str.fullmatch(r"SES-2026-\d{6}").all()
    assert t["experiment"].experiment_id.str.fullmatch(r"EXP-2026-\d{6}").all()
    ev = t["journey_event"]
    assert ev.event_id.str.fullmatch(r"EVT-SES-2026-\d{6}-\d{6}").all()
    assert (ev.event_id.str[4:19] == ev.session_id).all()
    jo = t["journey_outcome"]
    assert (jo.outcome_id == "OUT-" + jo.session_id).all()
    # counters are zero-padded and contiguous
    n = len(t["session"])
    assert t["session"].session_id.tolist() == [f"SES-2026-{i:06d}" for i in range(1, n + 1)]
    seq = ev.groupby("session_id").event_id.apply(lambda s: s.str[-6:].astype(int).tolist())
    assert all(v == list(range(1, len(v) + 1)) for v in seq)


def test_sessions_chronological_ids(ds):
    s = ds.tables["session"]
    assert s.session_start_ts.is_monotonic_increasing


def test_all_joins_complete(ds):
    t = ds.tables
    ev = t["journey_event"]
    assert ev.merge(t["session"], on="session_id").shape[0] == len(ev)
    o = t["order"].merge(t["cart"], on="cart_id", suffixes=("", "_c"))
    assert len(o) == len(t["order"]) and (o.session_id == o.session_id_c).all()
    assert t["order_line"].merge(t["order"], on="order_id").shape[0] == len(t["order_line"])
    assert t["experiment_assignment"].merge(t["session"], on="session_id").shape[0] == len(t["experiment_assignment"])


def test_derived_values_reconcile(ds):
    t = ds.tables
    ol = t["order_line"].groupby("order_id").line_amount.sum().round(2)
    o = t["order"].set_index("order_id")
    assert np.allclose(ol.reindex(o.index), o.subtotal, atol=0.005)
    assert np.allclose((o.subtotal - o.discount + o.tax + o.shipping_fee).round(2), o.total, atol=0.005)
    ev = t["journey_event"]
    cnt = ev.groupby("session_id").size()
    s = t["session"].set_index("session_id")
    assert (cnt.reindex(s.index) == s.event_count).all()
    pur = ev[ev.event_type == "purchase"]
    assert np.allclose(pur.order_id.map(o.total), pur.value)


def test_history_is_append_only_and_valid(report, ds):
    df = report.df()
    lc = df[df.category == "lifecycle"]
    assert (lc.violations == 0).all()
    ce = ds.tables["consent_event"]
    # customers who withdrew keep the earlier grant row (history not overwritten)
    w = ce[ce.action == "withdrawn"].customer_id
    g = ce[(ce.action == "granted") & ce.customer_id.isin(w)]
    assert len(w) > 0 and set(w) <= set(g.customer_id) | set(ce[ce.consent_type == "marketing"].customer_id)


def test_required_edge_cases_present_and_labelled(ds):
    an = ds.truth["anomalies"]
    counts = an.issue_type.value_counts()
    for issue in ("ingestion_order_inversion", "incorrect_identity_merge", "duplicate_conversion", "bot_traffic",
                  "late_arrival"):
        assert counts.get(issue, 0) > 0, issue
    assert {"cookie_replay", "declared_crawler"} <= set(an[an.issue_type == "bot_traffic"].subtype)
    assert an.anomaly_id.is_unique
    for d in an.detail:
        json.loads(d)


def test_coverage_of_required_scenarios(ds):
    t = ds.tables
    s = t["session"]
    assert (s.customer_id.isna() & (s.channel != "support")).mean() > 0.4          # anonymous journeys
    assert set(s.channel) == {"web", "app", "support"}
    multi = t["identity_link"].groupby("customer_id").device_id.nunique()
    assert (multi > 1).any()                                                    # multiple devices
    assert set(t["customer"].analytics_consent_status) >= {"granted", "denied", "unknown"}  # consent gaps
    lag = (pd.to_datetime(t["journey_event"].ingestion_ts) - pd.to_datetime(t["journey_event"].event_ts))
    assert (lag > pd.Timedelta(hours=1)).any()                                   # delayed events
    assert (t["order"].customer_id.isna()).any()                                 # guest checkout
    assert set(t["journey_outcome"].outcome_type) >= {"converted", "abandoned_cart", "abandoned_checkout",
                                                      "bounced", "support_resolved"}


def test_ground_truth_is_separate(ds):
    for name, df in ds.tables.items():
        leaked = set(df.columns) & GROUND_TRUTH_ONLY_COLUMNS
        assert not leaked, (name, leaked)
    lab = ds.truth["session_labels"]
    assert {"actor_type", "true_customer_id", "expected_outcome"} <= set(lab.columns)
    assert set(lab.session_id) == set(ds.tables["session"].session_id)
    # incidents / experiment effects only in expected_findings
    assert "INC-2026-001" not in ds.tables["journey_event"].to_csv(index=False)
    assert len(ds.expected_findings["incidents"]) == 4


def test_labels_derived_from_rules_not_random(ds):
    """expected_outcome must equal the documented rules applied to the clean baseline events."""
    lab = ds.truth["session_labels"].set_index("session_id")
    jo = ds.tables["journey_outcome"].set_index("session_id")
    assert (lab.expected_outcome == jo.outcome_type.reindex(lab.index)).all()
    conv = jo[jo.converted]
    assert conv.order_id.notna().all() and conv.order_id.is_unique


def test_schema_dictionary_covers_all_tables(ds):
    names = {t.name for t in TABLES}
    assert names == set(ds.tables)
    for t in TABLES:
        assert [f.name for f in t.fields] == list(ds.tables[t.name].columns), t.name
