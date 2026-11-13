"""Build the data files for the web dashboard (web/data/*.json).

The website is a static page (HTML + JS) so it can be hosted for free (Vercel, GitHub Pages, Netlify).
It cannot run Python, so this module pre-computes everything the page shows from an exported dataset:

    python -m journeylab dashboard --data output/full --web web

Output (kept small so it can be committed to GitHub):
    web/data/dashboard.json   KPIs, funnel, friction, incidents, experiments, data-quality results
    web/data/sessions.json    ~150 example sessions with their events, for the Journey explorer
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .pipeline import to_ms

WEEK = 7 * 86_400_000


def _read(p: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(p, keep_default_na=False, na_values=[""], **kw)


def _records(df: pd.DataFrame) -> list:
    """DataFrame -> JSON-safe list of dicts (NaN -> None)."""
    return json.loads(df.to_json(orient="records"))


def _week_label(w: int) -> str:
    return str(np.datetime64(int(w) * WEEK, "ms").astype("datetime64[D]"))


def build_dashboard(data_root: Path, web_dir: Path, sample_per_group: int = 12) -> dict:
    root = Path(data_root)
    d, der, gt, rep = root / "data", root / "derived", root / "ground_truth", root / "reports"
    out_dir = Path(web_dir) / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    man = json.loads((root / "manifest.json").read_text())
    rows = {f["path"][5:-4]: f["rows"] for f in man["files"] if f["path"].startswith("data/") and f["path"].endswith(".csv")}
    val = json.loads((rep / "validation_summary.json").read_text())
    ev_rep = json.loads((rep / "evaluation_report.json").read_text())
    exp_find = json.loads((gt / "expected_findings.json").read_text())
    repro = None
    for cand in (root.parent / "reproducibility_report.json", root / "reports" / "reproducibility_report.json"):
        if cand.exists():
            r = json.loads(cand.read_text())
            repro = dict(files_compared=r["files_compared"], all_identical=r["all_identical"], seed=r["seed"], scale=r["scale"])
            break

    sess = _read(d / "session.csv")
    orders = _read(d / "order.csv")
    jo = _read(d / "journey_outcome.csv")
    bots = _read(der / "bot_scores.csv")
    fm = _read(der / "funnel_metrics.csv")
    labels = _read(gt / "session_labels.csv")
    an = _read(gt / "anomalies.csv")
    bot_set = set(bots.loc[bots.is_bot_detected.astype(str) == "True", "session_id"])

    # ------------------------------------------------------------------ KPIs
    human = sess[(sess.channel != "support") & ~sess.session_id.isin(bot_set)]
    conv = jo[jo.session_id.isin(human.session_id)].converted.astype(str).eq("True").mean()
    kpis = dict(sessions=int(len(sess)), events=int(rows.get("journey_event", 0)), customers=int(rows.get("customer", 0)),
                orders=int(len(orders)), revenue=round(float(orders.total.sum()), 2), conversion_rate=round(float(conv), 4),
                support_tickets=int(rows.get("support_ticket", 0)), bot_sessions_detected=int(len(bot_set)),
                labelled_anomalies=int(len(an)), channel_mix=sess.channel.value_counts().to_dict(),
                anonymous_share=round(float(human.customer_id.isna().mean()), 4))

    # ------------------------------------------------------------------ funnel
    def stages(seg_type, seg):
        x = fm[(fm.segment_type == seg_type) & (fm.segment == seg)].sort_values("stage_no")
        return _records(x[["stage_no", "stage", "sessions_reached", "step_conversion", "drop_off_rate", "cumulative_conversion"]])
    funnel = {"all": stages("overall", "all"), "web": stages("channel", "web"), "app": stages("channel", "app")}
    months = sorted(fm[fm.segment_type == "month"].segment.unique())
    monthly = []
    for m in months:
        row = dict(month=m)
        for ch in ("web", "app"):
            x = fm[(fm.segment_type == "channel_month") & (fm.segment == f"{ch}|{m}")].set_index("stage")
            if len(x):
                row[f"{ch}_conversion"] = float(x.loc["purchase", "cumulative_conversion"])
                row[f"{ch}_sessions"] = int(x.loc["visit", "sessions_reached"])
        x = fm[(fm.segment_type == "month") & (fm.segment == m)].set_index("stage")
        row["all_conversion"] = float(x.loc["purchase", "cumulative_conversion"])
        monthly.append(row)
    sources = []
    for s in sorted(fm[fm.segment_type == "traffic_source"].segment.unique()):
        x = fm[(fm.segment_type == "traffic_source") & (fm.segment == s)].set_index("stage")
        sources.append(dict(source=s, sessions=int(x.loc["visit", "sessions_reached"]),
                            conversion=float(x.loc["purchase", "cumulative_conversion"])))
    outcomes = jo.outcome_type.value_counts().to_dict()

    # ------------------------------------------------------------------ friction
    fi = _read(der / "friction_impact.csv")
    fs = _read(der / "friction_steps.csv")
    fp = _read(der / "friction_paths.csv")
    fp["has_friction"] = fp.has_friction.astype(str).eq("True")
    friction = dict(impact=_records(fi.head(15)), steps=_records(fs),
                    paths_top=_records(fp.head(15)), paths_with_friction=_records(fp[fp.has_friction].head(15)))

    # ------------------------------------------------------------------ incidents (weekly series)
    alerts = _read(der / "incident_alerts.csv")
    ev = _read(d / "journey_event.csv", usecols=["session_id", "event_type", "event_ts", "channel", "page_id",
                                                 "page_load_ms", "device_id"])
    ev = ev[~ev.session_id.isin(bot_set) & (ev.channel != "support")]
    ev["week"] = to_ms(ev.event_ts) // WEEK
    s_idx = sess.set_index("session_id")
    pages = _read(d / "page.csv").set_index("page_id")
    dev_os = _read(d / "device.csv").set_index("device_id").os
    signals = [("app", "payment_error", ["payment_info_submitted"], "app_version", "5.2.0"),
               ("web", "shipping_validation_error", ["shipping_info_submitted", "shipping_validation_error"], "geo_country", "GB"),
               ("app", "add_to_cart_failed", ["add_to_cart", "add_to_cart_failed"], "os", "Android 13")]
    series = []
    for ch, et, den, dim, seg_val in signals:
        y = ev[(ev.channel == ch) & ev.event_type.isin(den + [et])]
        if dim == "os":
            seg = y.device_id.map(dev_os) == seg_val
        else:
            seg = y.session_id.map(s_idx[dim]).astype(str) == seg_val
        pts = []
        for wk in sorted(y.week.unique()):
            yw = y[y.week == wk]
            n_all = int(yw.event_type.isin(den).sum())
            k_all = int((yw.event_type == et).sum())
            ys = yw[seg.loc[yw.index]]
            n_s = int(ys.event_type.isin(den).sum())
            k_s = int((ys.event_type == et).sum())
            pts.append(dict(week=_week_label(wk), all_rate=round(k_all / n_all, 4) if n_all else None, all_n=n_all,
                            seg_rate=round(k_s / n_s, 4) if n_s else None, seg_n=n_s))
        series.append(dict(channel=ch, signal=et, unit="error rate", segment=f"{dim}={seg_val}", points=pts))
    v = ev[(ev.channel == "web") & ev.event_type.eq("page_view")]
    v = v[v.page_id.map(pages.page_type) == "search"]
    lat = v.groupby("week").page_load_ms.median()
    series.append(dict(channel="web", signal="search_page_load_ms", unit="median page load (ms)", segment=None,
                       points=[dict(week=_week_label(w), all_rate=float(x), all_n=int((v.week == w).sum()))
                               for w, x in lat.items()]))
    incidents = dict(alerts=_records(alerts), series=series, truth=exp_find["incidents"],
                     evaluation=ev_rep["incidents"])

    # ------------------------------------------------------------------ experiments
    er = _read(der / "experiment_readout.csv")
    truth_by = {e["name"]: e for e in exp_find["experiments"]}
    er["true_effect_note"] = er.name.map(lambda n: truth_by.get(n, {}).get("note"))
    verdict = {r["name"]: r["verdict"] for r in ev_rep["experiments"]}
    er["verdict"] = er.name.map(verdict)
    experiments = _records(er)

    # ------------------------------------------------------------------ cross channel
    ccp = _read(der / "cross_channel_paths.csv")
    ccs = json.loads((der / "cross_channel_summary.json").read_text())
    cross = dict(summary=ccs, recovery=ev_rep.get("cross_channel_recovery"),
                 top_paths=_records(ccp[ccp.cross_channel.astype(str) == "True"].head(15)))

    # ------------------------------------------------------------------ quality / evaluation
    quality = dict(validation=dict(passed=val["passed"], checks=val["checks"], failed=val["failed"],
                                   by_category=val["by_category"],
                                   sample_checks=[dict(category=c["category"], check=c["check"], status=c["status"],
                                                       violations=c["violations"])
                                                  for c in val["checks_detail"] if c["category"] in
                                                  ("arithmetic", "dates", "labelled", "lifecycle", "rules", "derived")]),
                   evaluation={k: ev_rep[k] for k in ("deduplication", "ingestion_order", "late_arrival", "sessionization",
                                                      "bot_detection", "identity_link_review", "identity_stitching",
                                                      "journey_outcome", "funnel")},
                   anomalies=an.groupby(["issue_type", "subtype"]).size().rename("count").reset_index().to_dict("records"),
                   reproducibility=repro)

    dash = dict(meta=dict(generator_version=man["generator_version"], seed=man["seed"], scale=man["scale"],
                          generator_command=man["generator_command"], table_rows=rows),
                kpis=kpis, funnel=funnel, monthly=monthly, sources=sources, outcomes=outcomes, friction=friction,
                incidents=incidents, experiments=experiments, cross_channel=cross, quality=quality)
    (out_dir / "dashboard.json").write_text(json.dumps(dash, separators=(",", ":"), default=str))

    # ------------------------------------------------------------------ journey explorer samples
    write_session_samples(root, out_dir, sess, jo, bots, labels, an, sample_per_group)
    return dash


def write_session_samples(root, out_dir, sess, jo, bots, labels, an, k):
    d, der = root / "data", root / "derived"
    lab = labels.set_index("session_id")
    out = jo.set_index("session_id")
    bs = bots.set_index("session_id")
    st = _read(der / "stitched_sessions.csv").set_index("session_id")
    groups = {
        "Converted purchase": lab.index[lab.expected_outcome == "converted"],
        "Abandoned checkout": lab.index[lab.expected_outcome == "abandoned_checkout"],
        "Support contact": lab.index[lab.expected_outcome.isin(["support_resolved", "support_unresolved"])],
        "Events arrived out of order": an.loc[an.issue_type == "ingestion_order_inversion", "session_id"],
        "Purchase counted twice": an.loc[an.issue_type == "duplicate_conversion", "session_id"],
        "Bot: cookie replay (real customer's device)": lab.index[lab.bot_type == "cookie_replay"],
        "Bot: crawler / scraper": lab.index[lab.bot_type.isin(["declared_crawler", "disguised_scraper", "stealth_scraper"])],
        "Bot: cart hoarding": lab.index[lab.bot_type == "cart_bot"],
    }
    rng = np.random.default_rng(7)
    picked = {}
    for g, ids in groups.items():
        ids = sorted(set(ids))
        if not ids:
            continue
        sel = rng.choice(ids, size=min(k, len(ids)), replace=False)
        for s in sorted(sel):
            picked.setdefault(s, g)
    want = set(picked)
    chunks = []
    for c in pd.read_csv(d / "journey_event.csv", chunksize=400_000, keep_default_na=False, na_values=[""]):
        chunks.append(c[c.session_id.isin(want)])
    ev = pd.concat(chunks)
    pages = _read(d / "page.csv").set_index("page_id")
    dup_ids = set(an.loc[an.issue_type == "duplicate_conversion", "entity_id"])
    ev["page_type"] = ev.page_id.map(pages.page_type)
    ev["_t"] = to_ms(ev.event_ts)
    s_idx = sess.set_index("session_id")
    res = []
    for sid in sorted(want):
        e = ev[ev.session_id == sid].sort_values(["_t", "event_id"])
        arrival = e.event_id.str[-6:].astype(int).tolist()
        evs = []
        mx = 0
        for (r, a) in zip(e.itertuples(index=False), arrival):
            evs.append(dict(id=r.event_id, type=r.event_type, ts=r.event_ts, ing=r.ingestion_ts, page=r.page_type
                            if isinstance(r.page_type, str) else None, product=r.product_id if isinstance(r.product_id, str) else None,
                            err=r.error_code if isinstance(r.error_code, str) else None,
                            load=None if pd.isna(r.page_load_ms) else int(r.page_load_ms),
                            value=None if pd.isna(r.value) else float(r.value),
                            dup=r.event_id in dup_ids, late_order=a < mx))
            mx = max(mx, a)
        si = s_idx.loc[sid]
        res.append(dict(session_id=sid, group=picked[sid], channel=si.channel, start=si.session_start_ts,
                        device_id=None if pd.isna(si.device_id) else si.device_id,
                        customer_id=None if pd.isna(si.customer_id) else si.customer_id,
                        traffic_source=si.traffic_source, user_agent=None if pd.isna(si.user_agent) else si.user_agent,
                        geo=None if pd.isna(si.geo_country) else si.geo_country,
                        outcome=out.loc[sid, "outcome_type"], furthest=out.loc[sid, "furthest_stage_name"],
                        bot_score=None if sid not in bs.index else float(bs.loc[sid, "bot_score"]),
                        bot_reasons=None if sid not in bs.index or pd.isna(bs.loc[sid, "reasons"]) else bs.loc[sid, "reasons"],
                        stitched=None if pd.isna(st.loc[sid, "stitched_customer_id"]) else st.loc[sid, "stitched_customer_id"],
                        truth=dict(actor=lab.loc[sid, "actor_type"],
                                   bot_type=None if pd.isna(lab.loc[sid, "bot_type"]) else lab.loc[sid, "bot_type"],
                                   expected_outcome=lab.loc[sid, "expected_outcome"]),
                        events=evs))
    (out_dir / "sessions.json").write_text(json.dumps(res, separators=(",", ":"), default=str))
