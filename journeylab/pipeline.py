"""Analytics pipeline: raw multi-channel events -> trustworthy journey metrics.

Runs only on the *input* tables (never on ground truth).  Each step is a
documented, deterministic rule set:

  P1 dedup_events        D1 same client_event_id -> keep earliest arrival
                         D2 purchase per order_id -> keep first occurrence (global)
  P2 resequence          order by event_ts (tie: event_id); flag sessions whose
                         arrival order differs from occurrence order
  P3 sessionization      re-derive web/app sessions per (device, channel) with a
                         30-min inactivity rule on event_ts; compare to collector
  P4 detect_bots         UA + behavioural + IP-concentration heuristics
  P5 review_links        accept deterministic links; reject conflicting,
                         ambiguous, low-confidence or geo-inconsistent ones
  P6 stitch              consent-aware identity stitching (event level)
  P7 outcomes            JourneyOutcome rules R1..R8 (see taxonomy.OUTCOME_RULES)
  P8 funnel / friction / incidents / experiments / cross-channel journeys
"""
from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

from .config import INACTIVITY_TIMEOUT_MS, LATE_ARRIVAL_THRESHOLD_MS
from .taxonomy import EVENT_STAGE, FRICTION_EVENTS, STAGE_NAME, FUNNEL_STAGES

NAT = np.iinfo(np.int64).min
VIEW_EVENTS = ("page_view", "screen_view")
ENGAGEMENT = ("scroll", "click")
BOT_UA_RE = re.compile(r"bot|crawler|spider|headless", re.I)
PIPELINE_VERSION = "1.0.0"


def to_ms(s: pd.Series) -> np.ndarray:
    v = s.astype(object).where(s.notna(), "NaT").to_numpy(dtype=str)
    v = np.char.rstrip(v, "Z")
    return v.astype("datetime64[ms]").astype(np.int64)


def ms_to_iso(a) -> np.ndarray:
    a = np.asarray(a, dtype=np.int64)
    out = np.full(a.shape, None, dtype=object)
    ok = a != NAT
    out[ok] = np.char.add(np.datetime_as_string(a[ok].astype("datetime64[ms]"), unit="ms").astype(str), "Z")
    return out


def _evseq(event_id: pd.Series) -> np.ndarray:
    return event_id.str[-6:].astype(np.int64).to_numpy()


# --------------------------------------------------------------------------- P1
def dedup_events(ev: pd.DataFrame):
    ev = ev.copy()
    ev["_ts"] = to_ms(ev["event_ts"])
    ev["_ing"] = to_ms(ev["ingestion_ts"])
    ev = ev.sort_values(["_ing", "event_id"], kind="stable")
    d1 = ev.duplicated("client_event_id", keep="first")
    keep_d1 = ev.loc[~d1].drop_duplicates("client_event_id").set_index("client_event_id")["event_id"]
    dec = [pd.DataFrame(dict(event_id=ev.loc[d1, "event_id"].to_numpy(), rule="D1_duplicate_client_event_id",
                             kept_event_id=ev.loc[d1, "client_event_id"].map(keep_d1).to_numpy()))]
    ev = ev.loc[~d1]
    pur = ev[(ev["event_type"] == "purchase") & ev["order_id"].notna()].sort_values(["_ts", "_ing", "event_id"], kind="stable")
    d2 = pur.duplicated("order_id", keep="first")
    first = pur.loc[~d2].set_index("order_id")["event_id"]
    dec.append(pd.DataFrame(dict(event_id=pur.loc[d2, "event_id"].to_numpy(), rule="D2_duplicate_conversion_order_id",
                                 kept_event_id=pur.loc[d2, "order_id"].map(first).to_numpy())))
    ev = ev.drop(index=pur.index[d2])
    decisions = pd.concat(dec, ignore_index=True).sort_values("event_id", kind="stable").reset_index(drop=True)
    return ev, decisions


# --------------------------------------------------------------------------- P2
def resequence(ev: pd.DataFrame):
    ev = ev.sort_values(["session_id", "_ts", "event_id"], kind="stable").reset_index(drop=True)
    ev["occurrence_seq"] = ev.groupby("session_id", sort=False).cumcount() + 1
    arr = _evseq(ev["event_id"])
    prev_max = pd.Series(arr).groupby(ev["session_id"].to_numpy(), sort=False).cummax().shift(1)
    same = ev["session_id"].eq(ev["session_id"].shift(1))
    ev["arrived_out_of_order"] = (same & (pd.Series(arr) < prev_max)).to_numpy()
    lat = ev["_ing"] - ev["_ts"]
    ev["late_arrival"] = (lat > LATE_ARRIVAL_THRESHOLD_MS).to_numpy()
    flagged = (ev.groupby("session_id", sort=False)
               .agg(events_out_of_order=("arrived_out_of_order", "sum"), late_events=("late_arrival", "sum"),
                    max_ingestion_lag_ms=("_ing", "max")).reset_index())
    flagged = flagged[(flagged.events_out_of_order > 0) | (flagged.late_events > 0)].copy()
    flagged["decision"] = np.where(flagged.events_out_of_order > 0, "resequenced_by_event_ts", "late_events_kept")
    return ev, flagged.drop(columns="max_ingestion_lag_ms")


# --------------------------------------------------------------------------- P3
def sessionization_check(ev: pd.DataFrame):
    """Re-derive web/app sessions with the documented 30-min inactivity rule."""
    w = ev[ev["channel"] != "support"][["session_id", "device_id", "channel", "_ts", "_ing", "event_id"]]
    out = {}
    for basis in ("_ts", "_ing"):
        x = w.sort_values(["device_id", "channel", basis, "event_id"], kind="stable")
        new = (x["device_id"].ne(x["device_id"].shift()) | x["channel"].ne(x["channel"].shift())
               | (x[basis].diff() > INACTIVITY_TIMEOUT_MS))
        derived = new.cumsum().to_numpy()
        pairs = pd.DataFrame(dict(s=x["session_id"].to_numpy(), d=derived)).drop_duplicates()
        n_coll = pairs["s"].nunique()
        n_der = pairs["d"].nunique()
        s_multi = pairs.groupby("s")["d"].nunique()
        d_multi = pairs.groupby("d")["s"].nunique()
        bad = set(s_multi[s_multi > 1].index) | set(pairs[pairs["d"].isin(d_multi[d_multi > 1].index)]["s"])
        out["event_time" if basis == "_ts" else "ingestion_time"] = dict(
            collector_sessions=int(n_coll), derived_sessions=int(n_der), mismatched_sessions=int(len(bad)),
            match_rate=round(1 - len(bad) / max(1, n_coll), 6), mismatched_ids=sorted(bad))
    gaps = w.sort_values(["session_id", "_ts"], kind="stable")
    g = gaps.groupby("session_id", sort=False)["_ts"].diff()
    out["max_within_session_gap_min"] = round(float(g.max() / 60000), 3) if len(g) else 0.0
    out["sessions_with_gap_20_to_30_min"] = int(gaps.loc[(g >= 20 * 60000) & (g <= 30 * 60000), "session_id"].nunique())
    return out


# --------------------------------------------------------------------------- P4
def session_features(ev: pd.DataFrame, sessions: pd.DataFrame) -> pd.DataFrame:
    x = ev[["session_id", "event_type", "_ts"]]
    gap = x.groupby("session_id", sort=False)["_ts"].diff()
    x = x.assign(gap=gap, eng=x["event_type"].isin(ENGAGEMENT), view=x["event_type"].isin(VIEW_EVENTS),
                 pv=x["event_type"].eq("product_view"))
    f = x.groupby("session_id", sort=False).agg(n_events=("_ts", "size"), t0=("_ts", "min"), t1=("_ts", "max"),
                                                median_gap_ms=("gap", "median"), mean_gap=("gap", "mean"),
                                                std_gap=("gap", "std"), n_eng=("eng", "sum"), n_views=("view", "sum"),
                                                n_product_views=("pv", "sum"))
    f["duration_s"] = (f.t1 - f.t0) / 1000
    f["events_per_min"] = f.n_events / (f.duration_s / 60 + 1 / 60)
    f["gap_cv"] = (f.std_gap / f.mean_gap).fillna(0)
    f["engagement_share"] = f.n_eng / f.n_events
    s = sessions.set_index("session_id")[["user_agent", "ip_hash", "channel", "device_id", "geo_country"]]
    f = f.join(s, how="left")
    ipc = sessions.groupby("ip_hash")["session_id"].size()
    f["ip_session_count"] = f["ip_hash"].map(ipc).fillna(0).astype(int)
    return f.drop(columns=["t0", "t1", "mean_gap", "std_gap"])


def detect_bots(feat: pd.DataFrame) -> pd.DataFrame:
    f = feat[feat["channel"] != "support"].copy()
    ua = f["user_agent"].fillna("").str.contains(BOT_UA_RE)
    big = f["n_events"] >= 12
    s_ip = f["ip_session_count"] >= 25
    s_fast = big & (f["median_gap_ms"] < 2500)
    s_regular = big & (f["gap_cv"] < 0.6)
    s_noeng = (f["n_views"] >= 8) & (f["engagement_share"] < 0.02)
    s_rate = f["events_per_min"] >= 30
    s_scan = (f["n_product_views"] >= 30) & (f["engagement_share"] < 0.25)      # deep catalogue scan
    score = (ua * 1.0 + s_ip * .30 + s_fast * .25 + s_regular * .20 + s_noeng * .25 + s_rate * .15
             + s_scan * .60).clip(upper=1.0)
    reasons = (np.where(ua, "ua_declared_bot;", "") + np.where(s_ip, "ip_concentration;", "")
               + np.where(s_fast, "fast_cadence;", "") + np.where(s_regular, "regular_cadence;", "")
               + np.where(s_noeng, "no_engagement;", "") + np.where(s_rate, "high_event_rate;", "")
               + np.where(s_scan, "catalogue_scan;", ""))
    out = pd.DataFrame(dict(session_id=f.index, bot_score=np.round(score.to_numpy(), 3),
                            is_bot_detected=(score >= 0.6).to_numpy(), reasons=reasons,
                            n_events=f["n_events"].to_numpy(), median_gap_ms=f["median_gap_ms"].round(1).to_numpy(),
                            gap_cv=f["gap_cv"].round(3).to_numpy(), engagement_share=f["engagement_share"].round(4).to_numpy(),
                            ip_session_count=f["ip_session_count"].to_numpy()))
    return out.sort_values("session_id").reset_index(drop=True)


# --------------------------------------------------------------------------- P5
DETERMINISTIC = ("login", "email_click")


def review_links(links: pd.DataFrame, sessions: pd.DataFrame, customers: pd.DataFrame,
                 bot_sessions: set | None = None) -> pd.DataFrame:
    L = links.copy()
    det = L[L["link_method"].isin(DETERMINISTIC)]
    det_cust = det.groupby("device_id")["customer_id"].agg(set)
    nondet = L[~L["link_method"].isin(DETERMINISTIC)]
    nd_count = nondet.groupby("device_id")["customer_id"].nunique()
    hs = sessions[(sessions["channel"] != "support") & ~sessions["session_id"].isin(bot_sessions or set())]
    gc = (hs.groupby(["device_id", "geo_country"]).size()
          .rename("n").reset_index().sort_values(["device_id", "n", "geo_country"], ascending=[True, False, True]))
    geo = gc.drop_duplicates("device_id").set_index("device_id")["geo_country"]
    ccountry = customers.set_index("customer_id")["country"]
    decision, rule = [], []
    for r in L.itertuples(index=False):
        if r.link_method in DETERMINISTIC:
            decision.append("accept"); rule.append("L0_deterministic")
            continue
        dc = det_cust.get(r.device_id, set())
        if dc and r.customer_id not in dc:
            decision.append("reject"); rule.append("L1_conflicts_with_deterministic_link")
        elif nd_count.get(r.device_id, 0) > 1:
            decision.append("reject"); rule.append("L2_ambiguous_multiple_candidates")
        elif r.confidence < 0.70:
            decision.append("reject"); rule.append("L3_low_confidence")
        elif geo.get(r.device_id) is not None and geo.get(r.device_id) != ccountry.get(r.customer_id):
            decision.append("reject"); rule.append("L4_geo_inconsistent")
        else:
            decision.append("accept"); rule.append("L5_probabilistic_passed_checks")
    shared = det.groupby("device_id")["customer_id"].nunique()
    L["decision"] = decision
    L["rule"] = rule
    L["device_shared"] = L["device_id"].map(shared).fillna(0).astype(int) > 1
    return L[["link_id", "device_id", "customer_id", "link_method", "confidence", "decision", "rule", "device_shared"]]


# --------------------------------------------------------------------------- P6
def consent_lookup(consent: pd.DataFrame, cust: np.ndarray, t: np.ndarray) -> np.ndarray:
    """True where analytics consent is 'granted' at time t for customer cust."""
    c = consent[consent["consent_type"] == "analytics"][["customer_id", "action", "effective_at"]].copy()
    c["_t"] = to_ms(c["effective_at"])
    left = pd.DataFrame(dict(customer_id=cust, _t=t, _i=np.arange(len(t))))
    left = left[left["customer_id"].notna()].sort_values("_t", kind="stable")
    left["customer_id"] = left["customer_id"].astype(object)
    c = c.sort_values("_t", kind="stable")
    c["customer_id"] = c["customer_id"].astype(object)
    m = pd.merge_asof(left, c[["customer_id", "_t", "action"]], on="_t", by="customer_id", direction="backward")
    out = np.zeros(len(t), dtype=bool)
    out[m["_i"].to_numpy()] = (m["action"] == "granted").to_numpy()
    return out


def stitch(ev: pd.DataFrame, links_reviewed: pd.DataFrame, consent: pd.DataFrame, bot_sessions: set,
           enforce_consent: bool = True):
    """Event-level identity stitching that respects analytics consent.

    R-ID-1 authenticated event -> its customer
    R-ID-2 unauthenticated event in a session with exactly one authenticated customer
    R-ID-3 device-level accepted link (valid_from <= event_ts), device not shared
    Then: blocked if analytics consent not active at event_ts; never for bot sessions.
    """
    sid = ev["session_id"].to_numpy()
    cust = ev["customer_id"].to_numpy(dtype=object)
    rule = np.where(pd.notna(cust), "R-ID-1", None).astype(object)
    auth = ev.loc[ev["customer_id"].notna(), ["session_id", "customer_id"]].drop_duplicates()
    one = auth.groupby("session_id")["customer_id"].agg(["nunique", "first"])
    one = one[one["nunique"] == 1]["first"]
    s_c = pd.Series(sid).map(one).to_numpy(dtype=object)
    m2 = pd.isna(cust) & pd.notna(s_c)
    cust = np.where(m2, s_c, cust)
    rule[m2] = "R-ID-2"
    acc = links_reviewed[(links_reviewed["decision"] == "accept") & ~links_reviewed["device_shared"]]
    single = acc.groupby("device_id")["customer_id"].nunique()
    acc = acc[acc["device_id"].isin(single[single == 1].index)]
    dl = acc.groupby("device_id").agg(c=("customer_id", "first"), vf=("valid_from_ms", "min")) if "valid_from_ms" in acc \
        else pd.DataFrame(columns=["c", "vf"])
    dev = ev["device_id"].to_numpy(dtype=object)
    d_c = pd.Series(dev).map(dl["c"]).to_numpy(dtype=object)
    d_vf = pd.Series(dev).map(dl["vf"]).to_numpy(dtype=float)
    m3 = pd.isna(cust) & pd.notna(d_c) & (ev["_ts"].to_numpy() >= np.nan_to_num(d_vf, nan=np.inf))
    cust = np.where(m3, d_c, cust)
    rule[m3] = "R-ID-3"
    cand = cust.copy()
    ok = consent_lookup(consent, cand, ev["_ts"].to_numpy()) if enforce_consent else np.ones(len(cand), dtype=bool)
    is_bot = pd.Series(sid).isin(bot_sessions).to_numpy()
    stitched = np.where(ok & ~is_bot & pd.notna(cand), cand, None)
    status = np.where(pd.isna(cand), "no_identity",
                      np.where(is_bot, "blocked_bot", np.where(ok, "stitched", "blocked_no_consent"))).astype(object)
    return stitched, status, rule


def stitch_sessions(ev, stitched, status, rule) -> pd.DataFrame:
    x = pd.DataFrame(dict(session_id=ev["session_id"].to_numpy(), c=stitched, r=rule,
                          a=status == "stitched", b=status == "blocked_no_consent", k=status == "blocked_bot"))
    g = x.groupby("session_id", sort=True)
    out = pd.DataFrame(dict(events_stitched=g["a"].sum(), events_blocked_no_consent=g["b"].sum(),
                            events_blocked_bot=g["k"].sum()))
    out.insert(0, "stitched_customer_id", x[x.c.notna()].groupby("session_id")["c"].first())
    out["primary_rule"] = x[x.r.notna()].groupby("session_id")["r"].min()
    out = out.astype({"events_stitched": int, "events_blocked_no_consent": int, "events_blocked_bot": int})
    return out.reset_index()


# --------------------------------------------------------------------------- P7
def outcomes(ev: pd.DataFrame, sessions: pd.DataFrame) -> pd.DataFrame:
    """JourneyOutcome per session from deduplicated, occurrence-ordered events."""
    x = ev[["session_id", "event_type", "_ts", "order_id", "cart_id", "ticket_id", "channel"]].copy()
    x["stage"] = x["event_type"].map(EVENT_STAGE).fillna(0).astype(int)
    x["is_view"] = x["event_type"].isin(VIEW_EVENTS)
    x["fr"] = x["event_type"].isin(FRICTION_EVENTS)
    x["contact"] = x["event_type"].eq("contact_support_click")
    x["resolved"] = x["event_type"].eq("ticket_resolved")
    x["purchase"] = x["event_type"].eq("purchase")
    x = x.sort_values(["session_id", "_ts"], kind="stable")
    g = x.groupby("session_id", sort=True)
    o = g.agg(furthest_stage=("stage", "max"), views=("is_view", "sum"), friction_event_count=("fr", "sum"),
              contact=("contact", "any"), resolved=("resolved", "any"), purchases=("purchase", "sum"),
              t0=("_ts", "min"), t1=("_ts", "max"), valid_event_count=("_ts", "size"), channel=("channel", "first"))
    po = x[x["purchase"]].groupby("session_id")["order_id"].first()
    cart = x[x["cart_id"].notna()].groupby("session_id")["cart_id"].first()
    tk = x[x["ticket_id"].notna()].groupby("session_id")["ticket_id"].first()
    o["order_id"] = po
    o["cart_id"] = cart
    o["ticket_id"] = tk
    dur = (o.t1 - o.t0) / 1000
    sup = o.channel.eq("support")
    conds = [o.purchases > 0, sup & o.resolved, sup, o.furthest_stage >= 4, o.furthest_stage == 3,
             (o.views <= 1) & (dur < 10), o.furthest_stage == 2]
    names = ["converted", "support_resolved", "support_unresolved", "abandoned_checkout", "abandoned_cart",
             "bounced", "browsed_product"]
    rules = ["R1", "R2", "R3", "R4", "R5", "R6", "R7"]
    o["outcome_type"] = np.select(conds, names, "browsed_no_product")
    o["rule_id"] = np.select(conds, rules, "R8")
    nxt = (o.furthest_stage + 1).clip(upper=6)
    o["drop_off_before_stage"] = np.where((o.outcome_type == "converted") | sup, None,
                                          nxt.map(STAGE_NAME).to_numpy())
    o["furthest_stage_name"] = o.furthest_stage.map(STAGE_NAME)
    o["converted"] = o.outcome_type.eq("converted")
    o["support_contact_flag"] = o.contact | sup
    o["duration_s"] = dur.round(3)
    o = o.reset_index()
    o["outcome_id"] = "OUT-" + o["session_id"]
    o["first_event_ts"] = ms_to_iso(o.t0)
    o["last_event_ts"] = ms_to_iso(o.t1)
    o["derivation_version"] = f"outcome_rules_v{PIPELINE_VERSION}"
    return o[["outcome_id", "session_id", "outcome_type", "rule_id", "furthest_stage", "furthest_stage_name",
              "drop_off_before_stage", "converted", "order_id", "cart_id", "ticket_id", "friction_event_count",
              "support_contact_flag", "valid_event_count", "first_event_ts", "last_event_ts", "duration_s",
              "derivation_version"]]


# --------------------------------------------------------------------------- P8
def funnel_metrics(out: pd.DataFrame, sessions: pd.DataFrame, exclude: set) -> pd.DataFrame:
    s = sessions[["session_id", "channel", "session_start_ts", "traffic_source"]].merge(
        out[["session_id", "furthest_stage"]], on="session_id")
    s = s[(s.channel != "support") & ~s.session_id.isin(exclude)].copy()
    s["month"] = s["session_start_ts"].str[:7]
    rows = []
    segs = [("overall", "all", s)]
    segs += [("channel", c, d) for c, d in s.groupby("channel")]
    segs += [("month", m, d) for m, d in s.groupby("month")]
    segs += [("traffic_source", t, d) for t, d in s.groupby("traffic_source")]
    segs += [("channel_month", f"{c}|{m}", d) for (c, m), d in s.groupby(["channel", "month"])]
    for st, sv, d in segs:
        n0 = len(d)
        prev = n0
        for n, name, _ in FUNNEL_STAGES:
            reached = int((d.furthest_stage >= n).sum())
            step = reached / prev if prev else 0.0
            rows.append(dict(segment_type=st, segment=sv, stage_no=n, stage=name, sessions_reached=reached,
                             step_conversion=round(step, 6), drop_off_rate=round(1 - step, 6) if n > 1 else 0.0,
                             cumulative_conversion=round(reached / n0, 6) if n0 else 0.0))
            prev = reached
    return pd.DataFrame(rows)


def friction_steps(ev: pd.DataFrame, pages: pd.DataFrame, exclude: set) -> pd.DataFrame:
    x = ev[(ev.channel != "support") & ~ev.session_id.isin(exclude)]
    pt = pages.set_index("page_id")["page_type"]
    x = x.assign(page_type=x["page_id"].map(pt))
    views = x[x.event_type.isin(VIEW_EVENTS)]
    last_view = views.groupby("session_id").tail(1)
    exits = last_view.groupby(["channel", "page_type"]).size()
    vs = views.groupby(["channel", "page_type"]).agg(views=("event_id", "size"), sessions=("session_id", "nunique"),
                                                     p50_load_ms=("page_load_ms", "median"),
                                                     p95_load_ms=("page_load_ms", lambda s: s.quantile(.95)))
    errs = x[x.event_type.isin(FRICTION_EVENTS)].groupby(["channel", "page_type"]).size()
    vs["friction_events"] = errs.reindex(vs.index).fillna(0).astype(int)
    vs["friction_rate_per_view"] = (vs.friction_events / vs.views).round(5)
    vs["exit_sessions"] = exits.reindex(vs.index).fillna(0).astype(int)
    vs["exit_rate"] = (vs.exit_sessions / vs.sessions).round(5)
    vs["p50_load_ms"] = vs.p50_load_ms.astype(float).round(0)
    vs["p95_load_ms"] = vs.p95_load_ms.astype(float).round(0)
    return vs.reset_index().sort_values(["channel", "exit_rate"], ascending=[True, False]).reset_index(drop=True)


def friction_paths(ev: pd.DataFrame, out: pd.DataFrame, pages: pd.DataFrame, exclude: set, k: int = 3) -> pd.DataFrame:
    ab = out[out.outcome_type.isin(["abandoned_cart", "abandoned_checkout"]) & ~out.session_id.isin(exclude)]
    x = ev[ev.session_id.isin(ab.session_id)]
    pt = pages.set_index("page_id")["page_type"]
    keep = x.event_type.isin(VIEW_EVENTS) | x.event_type.isin(FRICTION_EVENTS)
    x = x[keep]
    step = np.where(x.event_type.isin(VIEW_EVENTS), x.page_id.map(pt), x.event_type)
    x = x.assign(step=step)
    x = x[x.step.ne(x.groupby("session_id").step.shift())]           # collapse repeats
    tail = x.groupby("session_id").tail(k)
    paths = tail.groupby("session_id").agg(path=("step", " > ".join), channel=("channel", "first"))
    paths["has_friction"] = paths.path.str.contains("|".join(FRICTION_EVENTS))
    agg = paths.groupby(["channel", "path", "has_friction"]).size().rename("abandoned_sessions").reset_index()
    tot = agg.groupby("channel").abandoned_sessions.transform("sum")
    agg["share_of_channel_abandonment"] = (agg.abandoned_sessions / tot).round(5)
    return agg.sort_values(["abandoned_sessions", "path"], ascending=[False, True]).reset_index(drop=True)


# ---- incident detection (weekly rates with drill-down) ----------------------------
FRICTION_DENOM = {"payment_error": ["payment_info_submitted"],
                  "shipping_validation_error": ["shipping_info_submitted", "shipping_validation_error"],
                  "add_to_cart_failed": ["add_to_cart", "add_to_cart_failed"],
                  "page_error": list(VIEW_EVENTS)}


def incident_alerts(ev: pd.DataFrame, sessions: pd.DataFrame, devices: pd.DataFrame, pages: pd.DataFrame,
                    exclude: set) -> pd.DataFrame:
    x = ev[(ev.channel != "support") & ~ev.session_id.isin(exclude)]
    x = x.assign(week=(x._ts // (7 * 86_400_000)).astype(int))
    s = sessions.set_index("session_id")
    os_ = devices.set_index("device_id")["os"]
    alerts = []
    for et, den in FRICTION_DENOM.items():
        for ch in ("web", "app"):
            y = x[(x.channel == ch) & x.event_type.isin(den + [et])]
            if y.empty:
                continue
            num = y[y.event_type == et].groupby("week").size()
            dn = y[y.event_type.isin(den)].groupby("week").size()
            weeks = dn.index
            num = num.reindex(weeks).fillna(0)
            for a_ in _flag_rate_runs(num, dn, channel=ch, signal=et, drill=lambda wk: _drill(y, et, den, wk, s, os_)):
                alerts.append(dict(a_, segment="all"))
            # segment-level scan: small segments can hide behind a healthy channel-wide rate
            ys = y.assign(app_version=y.session_id.map(s["app_version"]), geo_country=y.session_id.map(s["geo_country"]),
                          os=y.device_id.map(os_))
            for dim in (("app_version", "geo_country", "os") if ch == "app" else ("geo_country", "os")):
                for val, yy in ys.groupby(dim):
                    dnv = yy[yy.event_type.isin(den)].groupby("week").size()
                    if dnv.sum() < 150:
                        continue
                    nv = yy[yy.event_type == et].groupby("week").size().reindex(dnv.index).fillna(0)
                    for a_ in _flag_rate_runs(nv, dnv, channel=ch, signal=et, drill=lambda wk: {}, z_min=4.5):
                        a_.update(top_dimension=dim, top_dimension_value=str(val), top_dimension_share_of_excess=None)
                        alerts.append(dict(a_, segment=f"{dim}={val}"))
    v = x[x.event_type.isin(VIEW_EVENTS)].assign(page_type=lambda d: d.page_id.map(pages.set_index("page_id")["page_type"]))
    for (ch, ptype), y in v.groupby(["channel", "page_type"]):
        med = y.groupby("week")["page_load_ms"].median().astype(float)
        n = y.groupby("week").size()
        alerts += [dict(a_, segment="all") for a_ in
                   _flag_runs(med, n, kind="latency_p50", channel=ch, signal=f"{ptype}_page_load_ms",
                              drill=lambda wk: {}, ratio=2.5, abs_min=1500, min_n=30)]
    df = pd.DataFrame(alerts)
    if df.empty:
        return pd.DataFrame(columns=["alert_id", "kind", "channel", "signal", "segment", "start_date", "end_date", "weeks",
                                     "peak_value", "baseline_value", "min_p_value", "excess_events", "top_dimension", "top_dimension_value",
                                     "top_dimension_share_of_excess"])
    df = df.sort_values(["start_date", "channel", "signal", "segment"]).reset_index(drop=True)
    df.insert(0, "alert_id", [f"ALR-{i:04d}" for i in range(1, len(df) + 1)])
    df = df[["alert_id", "kind", "channel", "signal", "segment"] + [c for c in df.columns
                                                                     if c not in ("alert_id", "kind", "channel", "signal", "segment")]]
    return df


def poisson_sf(k: float, lam: float) -> float:
    """P(X >= k) for X ~ Poisson(lam), computed in log space."""
    k = int(k)
    if k <= 0:
        return 1.0
    if lam <= 0:
        return 0.0
    log_terms = [-lam + i * math.log(lam) - math.lgamma(i + 1) for i in range(k)]
    m = max(log_terms)
    cdf = math.exp(m) * sum(math.exp(x - m) for x in log_terms)
    return max(0.0, 1.0 - cdf) if cdf < 0.999999 else float(sum(math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1))
                                                               for i in range(k, k + 400)))


def _flag_rate_runs(num, dn, channel, signal, drill, z_min=4.0, ratio=2.0, min_events=5):
    """Weekly error-rate alerts (control-chart style).

    Baseline = pooled rate of the last 8 *normal* weeks (p >= 0.01), so an incident cannot inflate its own
    baseline.  A week opens an alert when P(X >= errors | Poisson(n * baseline)) < p_open, the rate is at
    least `ratio` x baseline and there are >= `min_events` errors; it stays open while p < 0.01.
    """
    p_open = 1e-4 if z_min <= 4.0 else 1e-5
    num, dn = num.sort_index().astype(float), dn.sort_index().astype(float)
    pooled = num.sum() / max(1.0, dn.sum())
    floor = max(0.002, pooled * 0.5)
    hist_n, hist_d = [], []
    out, run = [], []
    rec = dict(rate=[], base=[], p=[])
    weeks = list(num.index)
    for i, wk in enumerate(weeks):
        k, n = num.iloc[i], dn.iloc[i]
        base = (sum(hist_n[-8:]) / sum(hist_d[-8:])) if len(hist_d) >= 3 and sum(hist_d[-8:]) > 0 else pooled
        base = max(base, floor)
        if run:
            base = frozen
        rate = k / max(1.0, n)
        p = poisson_sf(k, n * base)
        is_alert = (p < (0.01 if run else p_open)) and rate >= base * ratio and (k >= min_events or run)
        if is_alert:
            if not run:
                frozen = base
            run.append(i)
            rec["rate"].append(rate); rec["p"].append(p)
        elif p >= 0.01:                      # only clearly normal weeks feed the baseline
            hist_n.append(k); hist_d.append(n)
        if run and (not is_alert or i == len(weeks) - 1):
            wks = [weeks[x] for x in run]
            d = drill(wks)
            exc = sum(max(0.0, num.iloc[x] - dn.iloc[x] * frozen) for x in run)
            out.append(dict(kind="error_rate", channel=channel, signal=signal, start_date=_wk(wks[0]),
                            end_date=_wk(wks[-1] + 1), weeks=len(wks), peak_value=round(float(max(rec["rate"])), 4),
                            baseline_value=round(float(frozen), 4), min_p_value=float(f"{min(rec['p']):.3g}"),
                            excess_events=int(round(exc)), top_dimension=d.get("dim"),
                            top_dimension_value=d.get("value"), top_dimension_share_of_excess=d.get("share")))
            run, rec = [], dict(rate=[], base=[], p=[])
    return out


def _flag_runs(series, n, kind, channel, signal, drill, ratio=3.0, abs_min=0.04, min_n=15):
    series = series.sort_index()
    base = series.rolling(8, min_periods=3).median().shift(1)
    glob = series.median()
    base = base.fillna(glob)
    flag = (series > base * ratio) & (series - base > abs_min) & (n.reindex(series.index).fillna(0) >= min_n)
    out, run = [], []
    weeks = list(series.index)
    for i, wk in enumerate(weeks):
        if flag.iloc[i]:
            run.append(wk)
        if run and (not flag.iloc[i] or i == len(weeks) - 1):
            pre = base.loc[run[0]]
            d = drill(run)
            out.append(dict(kind=kind, channel=channel, signal=signal,
                            start_date=_wk(run[0]), end_date=_wk(run[-1] + 1), weeks=len(run),
                            peak_value=round(float(series.loc[run].max()), 4), baseline_value=round(float(pre), 4),
                            min_p_value=None, excess_events=None,
                            top_dimension=d.get("dim"), top_dimension_value=d.get("value"),
                            top_dimension_share_of_excess=d.get("share")))
            run = []
    return out


def _wk(w):
    return str(np.datetime64(int(w) * 7 * 86_400_000, "ms").astype("datetime64[D]"))


def _drill(y, et, den, weeks, s, os_):
    z = y[y.week.isin(weeks)]
    z = z.assign(app_version=z.session_id.map(s["app_version"]), geo_country=z.session_id.map(s["geo_country"]),
                 os=z.device_id.map(os_))
    best = {}
    for dim in ("app_version", "geo_country", "os"):
        dn = z[z.event_type.isin(den)].groupby(dim, dropna=True).size()
        num = z[z.event_type == et].groupby(dim, dropna=True).size().reindex(dn.index).fillna(0)
        if len(dn) == 0 or num.sum() == 0:
            continue
        overall = num.sum() / max(1, dn.sum())
        r = num / dn.clip(lower=1)
        excess = (num - dn * r.min()).clip(lower=0)
        top = excess.idxmax()
        share = float(excess.max() / max(1e-9, excess.sum()))
        lift = float(r.get(top, 0) / max(1e-9, overall))
        cand = dict(dim=dim, value=str(top), share=round(share, 3), lift=lift)
        if not best or cand["lift"] * cand["share"] > best["lift"] * best["share"]:
            best = cand
    return best


# ---- experiments -----------------------------------------------------------------
TARGET_METRIC = {"checkout_shipping": ("payment_submitted | checkout_start", "checkout_start", "payment_info_submitted"),
                 "product": ("add_to_cart | product_view", "product_view", "add_to_cart"),
                 "cart": ("checkout_start | add_to_cart", "add_to_cart", "checkout_start"),
                 "search": ("product_view after search | search", "search", "product_view_after_search"),
                 "home": ("product_view | visit", "session_start", "product_view")}


def session_event_flags(ev: pd.DataFrame) -> pd.DataFrame:
    x = ev[ev.event_type.isin(["session_start", "search", "product_view", "add_to_cart", "checkout_start",
                               "payment_info_submitted"])][["session_id", "event_type", "_ts"]]
    first = x.groupby(["session_id", "event_type"])._ts.min().unstack()
    last_pv = x[x.event_type == "product_view"].groupby("session_id")._ts.max()
    f = first.notna()
    f["product_view_after_search"] = (last_pv.reindex(first.index) > first.get("search")).fillna(False)
    return f


def experiment_readout(assign: pd.DataFrame, experiments: pd.DataFrame, out: pd.DataFrame, exclude: set,
                       ev: pd.DataFrame | None = None) -> pd.DataFrame:
    a = assign[~assign.session_id.isin(exclude)].merge(out[["session_id", "converted"]], on="session_id")
    flags = session_event_flags(ev) if ev is not None else pd.DataFrame()
    rows = []
    for e in experiments.itertuples(index=False):
        d = a[a.experiment_id == e.experiment_id]
        mname, den_col, num_col = TARGET_METRIC[e.target_step]
        res = {}
        for var in ("control", "treatment"):
            v = d[d.variant == var]
            fl = flags.reindex(v.session_id)
            den = fl[den_col].fillna(False).to_numpy(dtype=bool) if den_col in fl else np.zeros(len(v), bool)
            num = fl[num_col].fillna(False).to_numpy(dtype=bool) & den if num_col in fl else np.zeros(len(v), bool)
            res[var] = (len(v), int(den.sum()), int(num.sum()), int(v.converted.sum()))
        (nc, bc, sc, cc), (nt, bt, stt, ct) = res["control"], res["treatment"]
        pc, pt_ = (sc / bc if bc else np.nan), (stt / bt if bt else np.nan)
        se = math.sqrt(pc * (1 - pc) / bc + pt_ * (1 - pt_) / bt) if bc and bt else np.nan
        diff = pt_ - pc if bc and bt else np.nan
        z = diff / se if se and se > 0 else np.nan
        p = math.erfc(abs(z) / math.sqrt(2)) if z == z else np.nan
        rows.append(dict(experiment_id=e.experiment_id, name=e.name, status=e.status, target_metric=mname,
                         sessions_control=nc, sessions_treatment=nt, eligible_control=bc, eligible_treatment=bt,
                         rate_control=round(pc, 5) if pc == pc else None, rate_treatment=round(pt_, 5) if pt_ == pt_ else None,
                         abs_lift=round(diff, 5) if diff == diff else None,
                         rel_lift=round(diff / pc, 4) if (diff == diff and pc) else None,
                         ci95_low=round(diff - 1.96 * se, 5) if se == se else None,
                         ci95_high=round(diff + 1.96 * se, 5) if se == se else None,
                         p_value=round(p, 6) if p == p else None,
                         conversion_control=round(cc / nc, 5) if nc else None,
                         conversion_treatment=round(ct / nt, 5) if nt else None))
    return pd.DataFrame(rows)


# ---- friction impact ---------------------------------------------------------------
FRICTION_STAGE = {"payment_error": 5, "shipping_validation_error": 4, "add_to_cart_failed": 2, "page_error": 1,
                  "login_failed": 1}


def friction_impact(ev: pd.DataFrame, out: pd.DataFrame, tickets: pd.DataFrame, exclude: set) -> pd.DataFrame:
    """Which broken steps cost the most conversions?  Affected sessions are compared with sessions on the
    same channel that reached the same funnel stage without that friction event."""
    o = out[~out.session_id.isin(exclude) & ~out.rule_id.isin(["R2", "R3"])][["session_id", "furthest_stage", "converted"]]
    sch = ev.drop_duplicates("session_id").set_index("session_id").channel
    o = o.assign(channel=o.session_id.map(sch)).set_index("session_id")
    fx = ev[ev.event_type.isin(list(FRICTION_STAGE)) & ev.session_id.isin(o.index)]
    tk_origin = set(tickets.origin_session_id.dropna())
    rows = []
    for (ch, et, code), g in fx.groupby(["channel", "event_type", fx.error_code.fillna("")]):
        aff = g.session_id.unique()
        with_et = set(fx.loc[fx.event_type == et, "session_id"])
        base = o[(o.channel == ch) & (o.furthest_stage >= FRICTION_STAGE[et]) & ~o.index.isin(with_et)]
        ar = float(o.loc[aff].converted.mean())
        br = float(base.converted.mean()) if len(base) else float("nan")
        rows.append(dict(channel=ch, friction_event=et, error_code=code or None, sessions_affected=len(aff),
                         conversion_rate_affected=round(ar, 4), baseline_conversion_same_stage=round(br, 4),
                         conversion_gap_pp=round((br - ar) * 100, 2),
                         est_lost_conversions=round(max(0.0, br - ar) * len(aff), 1),
                         support_contact_rate=round(float(np.isin(aff, list(tk_origin)).mean()), 4)))
    df = pd.DataFrame(rows)
    return df.sort_values(["est_lost_conversions", "sessions_affected", "channel", "friction_event"],
                          ascending=[False, False, True, True]).reset_index(drop=True)


# ---- cross-channel journeys ----------------------------------------------------------
def cross_channel_journeys(out: pd.DataFrame, sessions: pd.DataFrame, stitched_sess: pd.DataFrame, exclude: set,
                           window_days: int = 7):
    s = sessions[["session_id", "channel", "anonymous_id", "session_start_ts"]].merge(
        out[["session_id", "outcome_type"]], on="session_id").merge(
        stitched_sess[["session_id", "stitched_customer_id"]], on="session_id", how="left")
    s = s[~s.session_id.isin(exclude)].copy()
    s["person"] = s.stitched_customer_id.fillna(s.anonymous_id).fillna("S:" + s.session_id)
    s["_t"] = to_ms(s.session_start_ts)
    s = s.sort_values(["person", "_t", "session_id"], kind="stable")
    gap = s.groupby("person")._t.diff()
    s["journey_no"] = (s.person.ne(s.person.shift()) | (gap > window_days * 86_400_000)).cumsum()
    s["step"] = s.channel + ":" + s.outcome_type
    j = s.groupby("journey_no").agg(person=("person", "first"), steps=("step", list), n=("step", "size"),
                                    channels=("channel", lambda c: "+".join(sorted(set(c)))))
    j["path"] = j.steps.map(lambda st: " > ".join(st[:5]) + (" > ..." if len(st) > 5 else ""))
    j["converted"] = j.steps.map(lambda st: any(x.endswith(":converted") for x in st))
    j["has_support"] = j.steps.map(lambda st: any(x.startswith("support:") for x in st))
    j["cross_channel"] = j.channels.str.contains(r"\+")
    top = (j.groupby("path").agg(journeys=("n", "size"), converted_journeys=("converted", "sum"),
                                 cross_channel=("cross_channel", "first"), has_support=("has_support", "first"))
           .reset_index().sort_values(["journeys", "path"], ascending=[False, True]).head(60))
    top["conversion_rate"] = (top.converted_journeys / top.journeys).round(4)
    # recovery after abandoned checkout
    ac = s[s.outcome_type == "abandoned_checkout"][["person", "_t", "session_id"]]
    later = s[["person", "_t", "channel", "outcome_type"]]
    m = ac.merge(later, on="person", suffixes=("", "_n"))
    m = m[(m._t_n > m._t) & (m._t_n - m._t <= window_days * 86_400_000)]
    conv = set(m[m.outcome_type == "converted"].session_id)
    sup = set(m[m.channel == "support"].session_id)
    summary = dict(journeys=int(len(j)), cross_channel_journeys=int(j.cross_channel.sum()),
                   journeys_with_support=int(j.has_support.sum()),
                   abandoned_checkout_sessions=int(len(ac)),
                   recovered_within_7d=int(len(conv)), recovered_rate=round(len(conv) / max(1, len(ac)), 4),
                   support_contact_within_7d=int(len(sup)),
                   recovered_after_support=int(len(conv & sup)))
    return top.reset_index(drop=True), summary


# --------------------------------------------------------------------------- orchestration
def run_pipeline(t: dict[str, pd.DataFrame]) -> dict:
    raw = t["journey_event"]
    ev, dedup = dedup_events(raw)
    ev, reseq = resequence(ev)
    sess_check = sessionization_check(ev)
    feat = session_features(ev, t["session"])
    bots = detect_bots(feat)
    bot_set = set(bots.loc[bots.is_bot_detected, "session_id"])
    links = t["identity_link"].copy()
    links["valid_from_ms"] = to_ms(links["valid_from"])
    rev = review_links(links, t["session"], t["customer"], bot_set)
    rev = rev.merge(links[["link_id", "valid_from_ms"]], on="link_id")
    stitched, status, rule = stitch(ev, rev, t["consent_event"], bot_set)
    ev["stitched_customer_id"] = stitched
    ev["stitch_status"] = status
    st_sess = stitch_sessions(ev, stitched, status, rule)
    out = outcomes(ev, t["session"])
    exclude = bot_set
    res = dict(events_clean=ev, dedup_decisions=dedup, resequenced_sessions=reseq, sessionization=sess_check,
               bot_scores=bots, identity_link_review=rev.drop(columns="valid_from_ms"), stitched_sessions=st_sess,
               journey_outcome=out)
    res["funnel_metrics"] = funnel_metrics(out, t["session"], exclude)
    res["friction_steps"] = friction_steps(ev, t["page"], exclude)
    res["friction_paths"] = friction_paths(ev, out, t["page"], exclude)
    res["incident_alerts"] = incident_alerts(ev, t["session"], t["device"], t["page"], exclude)
    res["experiment_readout"] = experiment_readout(t["experiment_assignment"], t["experiment"], out, exclude, ev)
    res["friction_impact"] = friction_impact(ev, out, t["support_ticket"], exclude)
    res["cross_channel_paths"], res["cross_channel_summary"] = cross_channel_journeys(out, t["session"], st_sess, exclude)
    return res
