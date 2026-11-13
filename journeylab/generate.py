"""End-to-end build: simulate -> inject -> finalize -> ground truth -> pipeline."""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from . import config as C
from .finalize import Dataset, finalize
from .inject import inject_all
from .pipeline import outcomes, run_pipeline, stitch, stitch_sessions, to_ms, DETERMINISTIC
from .simulate import Simulator


def build(cfg: C.GeneratorConfig, log=print) -> Dataset:
    t0 = time.time()
    sim = Simulator(cfg)
    sim.run()
    log(f"  simulated baseline: {len(sim.w.sessions):,} sessions, {len(sim.ev):,} events ({time.time() - t0:.1f}s)")
    ing, dup_of = inject_all(sim)
    log(f"  injected edge cases: {len(sim.w.anomalies):,} labelled anomalies ({time.time() - t0:.1f}s)")
    D = finalize(sim, ing, dup_of)
    log(f"  finalized IDs & derived values ({time.time() - t0:.1f}s)")
    add_truth(D)
    log(f"  ground truth computed ({time.time() - t0:.1f}s)")
    res = run_pipeline(D.tables)
    D.tables["journey_outcome"] = res["journey_outcome"]
    D.derived = res
    log(f"  analytics pipeline done ({time.time() - t0:.1f}s)")
    return D


def add_truth(D: Dataset):
    t = D.tables
    lab = D.truth["session_labels"]
    an = D.truth["anomalies"]
    base = t["journey_event"][D.meta["baseline_event_mask"]].copy()
    base["_ts"] = to_ms(base["event_ts"])
    exp_out = outcomes(base, t["session"]).set_index("session_id")
    true_bots = set(lab.loc[lab.actor_type == "bot", "session_id"])
    links = t["identity_link"][~t["identity_link"]["link_id"].isin(D.meta["bogus_link_ids"])].copy()
    links["valid_from_ms"] = to_ms(links["valid_from"])
    shared = links[links.link_method.isin(DETERMINISTIC)].groupby("device_id").customer_id.nunique()
    links["decision"] = "accept"
    links["device_shared"] = links.device_id.map(shared).fillna(0).astype(int) > 1
    st, status, rule = stitch(base, links, t["consent_event"], true_bots)
    ss = stitch_sessions(base, st, status, rule).set_index("session_id")
    sid = lab.session_id
    lab["expected_stitched_customer_id"] = sid.map(ss.stitched_customer_id).to_numpy(dtype=object)
    lab["expected_outcome"] = sid.map(exp_out.outcome_type).to_numpy()
    lab["expected_furthest_stage"] = sid.map(exp_out.furthest_stage).to_numpy()
    lab["expected_order_id"] = sid.map(exp_out.order_id).to_numpy(dtype=object)

    def flag(issue):
        return sid.isin(set(an.loc[an.issue_type == issue, "session_id"].dropna()))
    lab["has_ingestion_inversion"] = flag("ingestion_order_inversion")
    lab["has_late_arrival"] = flag("late_arrival")
    lab["has_duplicate_conversion"] = flag("duplicate_conversion")
    bogus = t["identity_link"][t["identity_link"].link_id.isin(D.meta["bogus_link_ids"])]
    sdev = t["session"].set_index("session_id").device_id
    lab["device_has_incorrect_link"] = sid.map(sdev).isin(set(bogus.device_id)).to_numpy()
    lab["auth_events_without_consent"] = sid.map(ss.events_blocked_no_consent).fillna(0).astype(int).to_numpy()
    D.truth["session_labels"] = lab
    D.expected_findings = dict(
        incidents=[{k: v for k, v in i.items() if not k.endswith("_ms")} for i in C.INCIDENTS],
        experiments=[dict(experiment_id=e, name=n, **C.EXPERIMENT_TRUTH[n])
                     for e, n in zip(t["experiment"].experiment_id, t["experiment"].name)],
        anomaly_counts={f"{a}/{b}": int(c) for (a, b), c in an.groupby(["issue_type", "subtype"]).size().items()},
        bogus_identity_links=sorted(D.meta["bogus_link_ids"]),
        notes=["Incidents and experiment effects are simulation parameters; they never appear in input tables.",
               "expected_outcome is computed with outcome rules R1-R8 on the pre-injection (baseline) events.",
               "expected_stitched_customer_id uses only true identity links, true bot labels and consent history."])
