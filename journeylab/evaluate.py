"""Evaluate pipeline decisions against the separate ground truth."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from .pipeline import consent_lookup, stitch, stitch_sessions, to_ms, outcomes


def prf(pred: set, true: set) -> dict:
    tp = len(pred & true)
    p = tp / len(pred) if pred else 1.0
    r = tp / len(true) if true else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return dict(true=len(true), predicted=len(pred), tp=tp, fp=len(pred - true), fn=len(true - pred),
                precision=round(p, 4), recall=round(r, 4), f1=round(f, 4))


def frame_hash(df: pd.DataFrame) -> str:
    return hashlib.sha256(df.to_csv(index=False, lineterminator="\n").encode()).hexdigest()


def evaluate(t: dict, truth: dict, res: dict, expected: dict) -> dict:
    an, lab = truth["anomalies"], truth["session_labels"]
    E = {}
    ev = t["journey_event"]
    # 1 dedup ------------------------------------------------------------------
    dropped = set(res["dedup_decisions"].event_id)
    true_dup = set(an.loc[an.issue_type == "duplicate_conversion", "entity_id"])
    raw_purchase = int((ev.event_type == "purchase").sum())
    jo = res["journey_outcome"]
    E["deduplication"] = dict(prf(dropped, true_dup), raw_purchase_events=raw_purchase,
                              orders=int(len(t["order"])), conversions_after_dedup=int(jo.converted.sum()),
                              double_counted_before_dedup=raw_purchase - int(len(t["order"])),
                              reconciled=bool(int(jo.converted.sum()) == len(t["order"])))
    # 2 ordering -------------------------------------------------------------------
    rs = res["resequenced_sessions"]
    E["ingestion_order"] = prf(set(rs.loc[rs.events_out_of_order > 0, "session_id"]),
                               set(an.loc[an.issue_type == "ingestion_order_inversion", "session_id"]))
    inv_late = {r.session_id for r in an[an.issue_type == "ingestion_order_inversion"].itertuples()
                if json.loads(r.detail)["delay_ms"] > 3_600_000}
    E["late_arrival"] = prf(set(rs.loc[rs.late_events > 0, "session_id"]),
                            set(an.loc[an.issue_type == "late_arrival", "session_id"]) | inv_late)
    # what a naive analyst would get by trusting arrival order (event_id) instead of event_ts
    inv_s = set(an.loc[an.issue_type == "ingestion_order_inversion", "session_id"])
    x = ev[ev.session_id.isin(inv_s) & ~ev.event_id.isin(true_dup)].copy()
    x["_t"] = to_ms(x.event_ts)
    by_arrival = x.sort_values(["session_id", "event_id"]).groupby("session_id").event_type.agg(lambda s: tuple(s.tail(3)))
    by_time = x.sort_values(["session_id", "_t", "event_id"]).groupby("session_id").event_type.agg(lambda s: tuple(s.tail(3)))
    E["ingestion_order"]["naive_last3_steps_wrong_share"] = round(float((by_arrival != by_time.reindex(by_arrival.index)).mean()), 4) if len(x) else 0.0
    sc = res["sessionization"]
    E["sessionization"] = {k: {kk: vv for kk, vv in v.items() if kk != "mismatched_ids"} if isinstance(v, dict) else v
                           for k, v in sc.items()}
    inv = set(an.loc[an.issue_type == "ingestion_order_inversion", "session_id"])
    mism = set(sc["ingestion_time"]["mismatched_ids"])
    E["sessionization"]["ingestion_time_mismatches_explained_by_inversion_or_late"] = round(
        len(mism & (inv | set(an.loc[an.issue_type == "late_arrival", "session_id"]))) / max(1, len(mism)), 4)
    # 3 bots ---------------------------------------------------------------------------
    bs = res["bot_scores"]
    det = set(bs.loc[bs.is_bot_detected, "session_id"])
    true_b = set(lab.loc[lab.actor_type == "bot", "session_id"])
    E["bot_detection"] = prf(det, true_b)
    E["bot_detection"]["recall_by_type"] = {
        bt: round(len(det & set(g.session_id)) / len(g), 4) for bt, g in lab[lab.actor_type == "bot"].groupby("bot_type")}
    humans = lab[lab.actor_type == "human"]
    E["bot_detection"]["human_false_positive_rate"] = round(len(det & set(humans.session_id)) / max(1, len(humans)), 5)
    # 4 identity links ------------------------------------------------------------------
    rv = res["identity_link_review"]
    rej = set(rv.loc[rv.decision == "reject", "link_id"])
    bogus = set(an.loc[an.issue_type == "incorrect_identity_merge", "entity_id"])
    E["identity_link_review"] = prf(rej, bogus)
    E["identity_link_review"]["rejections_by_rule"] = rv[rv.decision == "reject"].rule.value_counts().sort_index().to_dict()
    # 5 stitching -----------------------------------------------------------------------
    ec = res["events_clean"]
    st = ec["stitched_customer_id"].to_numpy(dtype=object)
    has = pd.notna(st)
    ok = consent_lookup(t["consent_event"], st, ec["_ts"].to_numpy())
    viol = int((has & ~ok).sum())
    ss = res["stitched_sessions"].set_index("session_id")
    L = lab.set_index("session_id")
    got = ss.stitched_customer_id.reindex(L.index)
    exp = L.expected_stitched_customer_id
    true_c = L.true_customer_id
    wrong = int((got.notna() & (got != true_c)).sum())
    # naive baseline: accept every link, ignore consent & bots
    links = t["identity_link"].copy()
    links["valid_from_ms"] = to_ms(links["valid_from"])
    links["decision"] = "accept"
    links["device_shared"] = False
    nst, nstat, nrule = stitch(ec, links, t["consent_event"], set(), enforce_consent=False)
    nss = stitch_sessions(ec, nst, nstat, nrule).set_index("session_id").stitched_customer_id.reindex(L.index)
    n_ok = consent_lookup(t["consent_event"], nst, ec["_ts"].to_numpy())
    E["identity_stitching"] = dict(
        consent_violations_events=viol,
        sessions_matching_expected=round(float(((got.fillna("") == exp.fillna("")).mean())), 5),
        sessions_stitched=int(got.notna().sum()), sessions_expected_stitched=int(exp.notna().sum()),
        wrong_customer_sessions=wrong,
        missed_stitch_sessions=int((exp.notna() & got.isna()).sum()),
        naive_consent_violations_events=int((pd.notna(nst) & ~n_ok).sum()),
        naive_wrong_customer_sessions=int((nss.notna() & (nss != true_c)).sum()),
        respects_consent=viol == 0)
    # 6 outcomes ------------------------------------------------------------------------
    jo_i = jo.set_index("session_id").reindex(L.index)
    acc = float((jo_i.outcome_type == L.expected_outcome).mean())
    raw = ev.copy()
    raw["_ts"] = to_ms(raw.event_ts)
    naive = outcomes(raw, t["session"]).set_index("session_id").reindex(L.index)
    E["journey_outcome"] = dict(
        accuracy_vs_expected=round(acc, 6), mismatches=int((jo_i.outcome_type != L.expected_outcome).sum()),
        naive_accuracy_without_dedup=round(float((naive.outcome_type == L.expected_outcome).mean()), 6),
        distribution=jo.outcome_type.value_counts().sort_index().to_dict())
    # 7 funnel impact of cleaning ----------------------------------------------------------
    wa = t["session"][t["session"].channel != "support"].session_id
    fm = res["funnel_metrics"]
    ov = fm[(fm.segment_type == "overall")].set_index("stage")
    E["funnel"] = dict(
        naive_conversion_rate=round(raw_purchase / len(wa), 5),
        clean_conversion_rate=float(ov.loc["purchase", "cumulative_conversion"]),
        clean_sessions=int(ov.loc["visit", "sessions_reached"]),
        stage_reach=ov.sessions_reached.to_dict(),
        funnel_metrics_sha256=frame_hash(fm))
    # 8 incidents --------------------------------------------------------------------------
    al = res["incident_alerts"]
    matched_alerts = set()
    inc_rows = []
    for inc in expected["incidents"]:
        sig = inc["event_type"] if inc["kind"] == "broken_step" else f"{inc['step']}_page_load_ms"
        cand = al[(al.channel == inc["channel"]) & (al.signal == sig) & (al.start_date < inc["end"][:10])
                  & (al.end_date > inc["start"][:10])]
        dim = next((k for k in ("app_version", "geo_country", "os") if k in inc), None)
        want = inc.get("app_version") or inc.get("geo_country") or inc.get("os")
        hit = None
        if len(cand):
            matched_alerts |= set(cand.alert_id)
            wants = {str(x) for x in (want if isinstance(want, list) else [want])}
            exact = cand[cand.top_dimension_value.astype(str).isin(wants)] if dim else cand.iloc[0:0]
            hit = (exact.iloc[0] if len(exact) else cand.iloc[0])
        inc_rows.append(dict(incident_id=inc["incident_id"], kind=inc["kind"], detected=hit is not None,
                             alert_id=None if hit is None else hit.alert_id,
                             alert_window=None if hit is None else f"{hit.start_date}..{hit.end_date}",
                             true_window=f"{inc['start'][:10]}..{inc['end'][:10]}",
                             root_cause_dimension_expected=f"{dim}={want}" if dim else None,
                             root_cause_dimension_found=None if hit is None or pd.isna(hit.top_dimension)
                             else f"{hit.top_dimension}={hit.top_dimension_value}",
                             root_cause_match=None if dim is None else bool(
                                 hit is not None and not pd.isna(hit.top_dimension_value)
                                 and str(hit.top_dimension_value) in {str(x) for x in (want if isinstance(want, list) else [want])})))
    E["incidents"] = dict(detected=sum(r["detected"] for r in inc_rows), total=len(inc_rows),
                          unmatched_alerts=int(len(set(al.alert_id) - matched_alerts)), details=inc_rows)
    # 8b cross-channel recovery: observed (needs stitching + consent) vs. true person-level behaviour
    lab_i = lab.set_index("session_id")
    sess = t["session"].set_index("session_id")
    ok_s = jo_i.index[(L.actor_type == "human").to_numpy()]
    tp = pd.DataFrame(dict(person=L.true_customer_id.reindex(ok_s).fillna(pd.Series(sess.anonymous_id.reindex(ok_s)))
                           .fillna(pd.Series("S:" + ok_s.to_series(), index=ok_s)),
                           t=to_ms(sess.session_start_ts.reindex(ok_s)), out=L.expected_outcome.reindex(ok_s)), index=ok_s)
    ab = tp[tp.out == "abandoned_checkout"].reset_index()
    m = ab.merge(tp.reset_index(), on="person", suffixes=("", "_n"))
    m = m[(m.t_n > m.t) & (m.t_n - m.t <= 7 * 86_400_000) & (m.out_n == "converted")]
    obs = res["cross_channel_summary"]
    E["cross_channel_recovery"] = dict(
        true_abandoned_checkout_sessions=int(len(ab)), true_recovered_within_7d=int(m.session_id.nunique()),
        true_recovery_rate=round(m.session_id.nunique() / max(1, len(ab)), 4),
        observed_recovered_within_7d=obs["recovered_within_7d"], observed_recovery_rate=obs["recovered_rate"],
        note="observed < true because cross-device returns are only linkable when identity is stitched with consent")
    # 9 experiments --------------------------------------------------------------------------
    er = res["experiment_readout"].set_index("name")
    rows = []
    for e in expected["experiments"]:
        mult = [v for k, v in e.items() if "->" in k]
        r = er.loc[e["name"]]
        sig = r.p_value is not None and r.p_value == r.p_value and r.p_value < 0.05
        if mult:
            verdict = "detected" if sig and r.abs_lift > 0 else "missed"
        elif r.sessions_control + r.sessions_treatment == 0:
            verdict = "no_traffic_as_expected"
        else:
            verdict = "correct_null" if not sig else "false_positive"
        rows.append(dict(name=e["name"], true_multiplier=mult[0] if mult else 1.0, abs_lift=r.abs_lift, p_value=r.p_value,
                         verdict=verdict))
    E["experiments"] = rows
    return E


def evaluation_md(E: dict) -> str:
    d = E
    L = ["# Evaluation report (pipeline vs. ground truth)", ""]
    L += ["| Area | Metric | Value |", "|---|---|---|"]
    def row(a, m, v):
        L.append(f"| {a} | {m} | {v} |")
    x = d["deduplication"]
    row("Deduplication", "precision / recall", f"{x['precision']} / {x['recall']} ({x['tp']}/{x['true']})")
    row("Deduplication", "raw purchase events → orders → conversions after dedup",
        f"{x['raw_purchase_events']} → {x['orders']} → {x['conversions_after_dedup']} (reconciled={x['reconciled']})")
    x = d["ingestion_order"]
    row("Ingestion order", "inverted sessions flagged P/R", f"{x['precision']} / {x['recall']} ({x['true']} labelled)")
    row("Ingestion order", "share of inverted sessions whose last-3-step path is wrong if ordered by arrival",
        x["naive_last3_steps_wrong_share"])
    x = d["late_arrival"]
    row("Late arrival", "flagged P/R", f"{x['precision']} / {x['recall']}")
    s = d["sessionization"]
    row("Sessionization", "match rate using event_ts", s["event_time"]["match_rate"])
    row("Sessionization", "match rate if (wrongly) using ingestion_ts", s["ingestion_time"]["match_rate"])
    x = d["bot_detection"]
    row("Bots", "precision / recall / F1", f"{x['precision']} / {x['recall']} / {x['f1']}")
    row("Bots", "recall by type", ", ".join(f"{k}={v}" for k, v in x["recall_by_type"].items()))
    row("Bots", "human false-positive rate", x["human_false_positive_rate"])
    x = d["identity_link_review"]
    row("Identity links", "bogus-link rejection P/R", f"{x['precision']} / {x['recall']} ({x['tp']}/{x['true']})")
    x = d["identity_stitching"]
    row("Stitching", "consent violations (events)", f"{x['consent_violations_events']} (naive: {x['naive_consent_violations_events']})")
    row("Stitching", "sessions stitched to wrong customer", f"{x['wrong_customer_sessions']} (naive: {x['naive_wrong_customer_sessions']})")
    row("Stitching", "sessions matching expected identity", x["sessions_matching_expected"])
    x = d["journey_outcome"]
    row("Outcomes", "accuracy vs expected", f"{x['accuracy_vs_expected']} (naive without dedup: {x['naive_accuracy_without_dedup']})")
    x = d["funnel"]
    row("Funnel", "conversion rate naive → clean", f"{x['naive_conversion_rate']} → {x['clean_conversion_rate']}")
    row("Funnel", "funnel_metrics sha256", f"`{x['funnel_metrics_sha256'][:16]}…`")
    x = d["incidents"]
    row("Incidents", "detected", f"{x['detected']}/{x['total']} (unmatched alerts: {x['unmatched_alerts']})")
    for r in x["details"]:
        row("Incidents", r["incident_id"], f"detected={r['detected']} window={r['alert_window']} "
            f"root cause={r['root_cause_dimension_found']} (expected {r['root_cause_dimension_expected']})")
    x = d["cross_channel_recovery"]
    row("Cross-channel", "abandoned-checkout recovery within 7 days (true vs observed)",
        f"{x['true_recovery_rate']} vs {x['observed_recovery_rate']} (identity/consent limited)")
    for r in d["experiments"]:
        row("Experiments", r["name"], f"{r['verdict']} (lift={r['abs_lift']}, p={r['p_value']})")
    return "\n".join(L) + "\n"
