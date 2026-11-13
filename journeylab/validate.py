"""Validation suite (Step 8).

Hard checks must have zero violations.  "Labelled anomaly" checks verify that
every irregularity found in the data is explained by a ground-truth label and
vice-versa (i.e. nothing unlabelled was corrupted).
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from .config import INACTIVITY_TIMEOUT_MS, SNAPSHOT_TS
from .pipeline import to_ms, NAT
from .schema import TABLES, TABLE, LIFECYCLES
from .taxonomy import GROUND_TRUTH_ONLY_COLUMNS, EVENT_TAXONOMY


class Report:
    def __init__(self):
        self.rows = []

    def add(self, category, check, violations, detail="", expected=0, kind="hard"):
        v = int(violations)
        status = "PASS" if v == expected else "FAIL"
        self.rows.append(dict(category=category, check=check, kind=kind, status=status, violations=v,
                              expected=int(expected), detail=str(detail)[:400]))

    def df(self):
        return pd.DataFrame(self.rows)

    @property
    def ok(self):
        return all(r["status"] == "PASS" for r in self.rows)


def _ms(df, col):
    return to_ms(df[col])


def validate(t: dict[str, pd.DataFrame], truth: dict[str, pd.DataFrame] | None = None) -> Report:
    R = Report()
    # ------------------------------------------------------------ schema / enums / PK
    for tb in TABLES:
        df = t.get(tb.name)
        if df is None:
            R.add("schema", f"{tb.name}: table present", 1)
            continue
        missing = [f.name for f in tb.fields if f.name not in df.columns]
        extra = [c for c in df.columns if c not in {f.name for f in tb.fields}]
        R.add("schema", f"{tb.name}: columns match dictionary", len(missing) + len(extra), f"missing={missing} extra={extra}")
        R.add("pk", f"{tb.name}: primary key unique & non-null",
              int(df.duplicated(list(tb.pk)).sum() + df[list(tb.pk)].isna().any(axis=1).sum()), f"pk={tb.pk}")
        for f in tb.fields:
            if f.name not in df.columns:
                continue
            s = df[f.name]
            if f.required:
                R.add("required", f"{tb.name}.{f.name} not null", int(s.isna().sum()))
            nn = s.dropna()
            if f.allowed is not None and len(nn):
                allowed = set(f.allowed)
                if f.type == "integer":
                    bad = (~nn.astype(int).isin(allowed)).sum()
                else:
                    bad = (~nn.astype(str).isin({str(a) for a in allowed})).sum()
                R.add("enum", f"{tb.name}.{f.name} in allowed values", int(bad))
            if f.pattern and len(nn):
                bad = (~nn.astype(str).str.match(f.pattern)).sum()
                R.add("format", f"{tb.name}.{f.name} matches {f.pattern}", int(bad))
            if f.unique and f.name not in tb.pk:
                R.add("unique", f"{tb.name}.{f.name} unique", int(nn.duplicated().sum()))
            if f.type == "timestamp" and len(nn):
                bad = (~nn.astype(str).str.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")).sum()
                R.add("format", f"{tb.name}.{f.name} ISO-8601 UTC", int(bad))
    # ------------------------------------------------------------ FK integrity
    for tb in TABLES:
        df = t[tb.name]
        for f in tb.fields:
            if not f.fk:
                continue
            rt, rc = f.fk.split(".")
            ref = set(t[rt][rc].dropna())
            v = df[f.name].dropna()
            R.add("fk", f"{tb.name}.{f.name} -> {f.fk}", int((~v.isin(ref)).sum()))
    sh = t["status_history"]
    ent_key = {"cart": ("cart", "cart_id"), "order": ("order", "order_id"), "ticket": ("support_ticket", "ticket_id"),
               "experiment": ("experiment", "experiment_id"), "product": ("product", "product_id")}
    bad = 0
    for et, (tbl, col) in ent_key.items():
        x = sh[sh.entity_type == et]
        bad += int((~x.entity_id.isin(set(t[tbl][col]))).sum())
    R.add("fk", "status_history.entity_id -> polymorphic parent", bad)

    ev, ss = t["journey_event"], t["session"]
    e_ts, e_ing = _ms(ev, "event_ts"), _ms(ev, "ingestion_ts")
    # ------------------------------------------------------------ cross-table consistency
    R.add("consistency", "event_id prefix equals session_id",
          int((ev.event_id.str[4:19] != ev.session_id).sum()))
    sch = ss.set_index("session_id")["channel"]
    R.add("consistency", "event.channel = session.channel", int((ev.session_id.map(sch) != ev.channel).sum()))
    sdev = ss.set_index("session_id")["device_id"]
    R.add("consistency", "event.device_id = session.device_id",
          int((ev.session_id.map(sdev).fillna("-") != ev.device_id.fillna("-")).sum()))
    dev_anon = t["device"].set_index("device_id")["anonymous_id"]
    R.add("consistency", "session.anonymous_id = device.anonymous_id",
          int((ss.device_id.map(dev_anon).fillna("-") != ss.anonymous_id.fillna("-")).sum()))
    R.add("consistency", "identity_link.anonymous_id = device.anonymous_id",
          int((t["identity_link"].device_id.map(dev_anon) != t["identity_link"].anonymous_id).sum()))
    req = {e[0]: [c + "_id" if not c.endswith("_id") else c for c in e[4].split("|") if c] for e in EVENT_TAXONOMY}
    miss = 0
    for et_name, cols in req.items():
        sub = ev[ev.event_type == et_name]
        for c in cols:
            miss += int(sub[c].isna().sum())
    R.add("consistency", "event required references present (taxonomy)", miss)
    allowed_ch = {e[0]: set(e[3].split("|")) for e in EVENT_TAXONOMY}
    R.add("consistency", "event type allowed on channel",
          int((~pd.Series([c in allowed_ch[e] for e, c in zip(ev.event_type, ev.channel)])).sum()))
    # ------------------------------------------------------------ date ordering
    R.add("dates", "ingestion_ts >= event_ts", int((e_ing < e_ts).sum()))
    s0, s1 = _ms(ss, "session_start_ts"), _ms(ss, "session_end_ts")
    g = pd.DataFrame(dict(s=ev.session_id, t=e_ts)).groupby("s")["t"].agg(["min", "max", "size"])
    al = g.reindex(ss.session_id)
    R.add("derived", "session start/end = min/max(event_ts)",
          int(((al["min"].to_numpy() != s0) | (al["max"].to_numpy() != s1)).sum()))
    R.add("derived", "session.event_count = count(events)", int((al["size"].to_numpy() != ss.event_count.to_numpy()).sum()))
    R.add("derived", "session.duration_s = end - start", int((np.abs((s1 - s0) / 1000 - ss.duration_s.to_numpy()) > 0.001).sum()))
    cu = t["customer"].set_index("customer_id")
    c_created = pd.Series(_ms(t["customer"], "created_at"), index=t["customer"].customer_id)
    auth = ev[ev.customer_id.notna() & (ev.channel != "support")]
    R.add("dates", "authenticated events after customer.created_at",
          int((e_ts[auth.index] < auth.customer_id.map(c_created).to_numpy()).sum()))
    ce = t["consent_event"]
    R.add("dates", "consent effective_at >= customer.created_at",
          int((_ms(ce, "effective_at") < ce.customer_id.map(c_created).to_numpy()).sum()))
    R.add("dates", "consent recorded_at >= effective_at", int((_ms(ce, "recorded_at") < _ms(ce, "effective_at")).sum()))
    il = t["identity_link"]
    R.add("dates", "identity_link.valid_from >= customer.created_at",
          int((_ms(il, "valid_from") < il.customer_id.map(c_created).to_numpy()).sum()))
    pr = t["product"].set_index("product_id")
    pl, pdisc = pd.Series(_ms(t["product"], "launched_at"), index=pr.index), pd.Series(_ms(t["product"], "discontinued_at"), index=pr.index)
    pv = ev[ev.product_id.notna() & (ev.event_type != "purchase")]
    lt = pv.product_id.map(pl).to_numpy()
    dt = pv.product_id.map(pdisc).to_numpy()
    et = e_ts[pv.index]
    R.add("dates", "product active at event time (launched <= ts < discontinued)",
          int(((et < lt) | ((dt != NAT) & (et >= dt))).sum()))
    R.add("dates", "product discontinued_at > launched_at", int(((pdisc != NAT) & (pdisc <= pl)).sum()))
    ex = t["experiment"]
    R.add("dates", "experiment created <= start < end",
          int(((_ms(ex, "created_at") > _ms(ex, "start_at")) | (_ms(ex, "start_at") >= _ms(ex, "end_at"))).sum()))
    ea = t["experiment_assignment"].merge(ex[["experiment_id", "start_at", "end_at", "channel", "status"]], on="experiment_id")
    at = _ms(ea, "assigned_at")
    R.add("dates", "assignment within experiment window", int(((at < _ms(ea, "start_at")) | (at >= _ms(ea, "end_at"))).sum()))
    R.add("rules", "no assignments for draft experiments", int((ea.status == "draft").sum()))
    ea_ch = ea.session_id.map(sch)
    R.add("rules", "assignment channel eligible", int(((ea.channel != "all") & (ea.channel != ea_ch)).sum()))
    R.add("rules", "variant sticky per (experiment, device)",
          int((ea.groupby(["experiment_id", "device_id"]).variant.nunique() > 1).sum()))
    cart = t["cart"]
    R.add("dates", "cart checkout_started_at >= created_at",
          int(((_ms(cart, "checkout_started_at") != NAT) & (_ms(cart, "checkout_started_at") < _ms(cart, "created_at"))).sum()))
    ci = t["cart_item"]
    R.add("dates", "cart_item removed_at >= added_at",
          int(((_ms(ci, "removed_at") != NAT) & (_ms(ci, "removed_at") < _ms(ci, "added_at"))).sum()))
    od = t["order"]
    oc = od.merge(cart[["cart_id", "created_at", "session_id"]], on="cart_id", suffixes=("", "_cart"))
    R.add("dates", "order_ts >= cart.created_at", int((_ms(oc, "order_ts") < _ms(oc, "created_at")).sum()))
    R.add("consistency", "order.session_id = cart.session_id", int((oc.session_id != oc.session_id_cart).sum()))
    so = od.merge(ss[["session_id", "session_start_ts", "session_end_ts"]], on="session_id")
    ot = _ms(so, "order_ts")
    R.add("dates", "order_ts within its session", int(((ot < _ms(so, "session_start_ts")) | (ot > _ms(so, "session_end_ts"))).sum()))
    tk = t["support_ticket"]
    o_, f_, e_, r_, c_ = (_ms(tk, k) for k in ("opened_at", "first_response_at", "escalated_at", "resolved_at", "closed_at"))
    bad = ((f_ != NAT) & (f_ < o_)) | ((e_ != NAT) & (e_ < f_)) | ((r_ != NAT) & (r_ < f_)) | ((c_ != NAT) & (c_ < r_)) \
        | ((r_ != NAT) & (e_ != NAT) & (r_ < e_))
    R.add("dates", "ticket opened <= first_response <= escalated <= resolved <= closed", int(bad.sum()))
    fs = tk.merge(ss[["session_id", "session_start_ts"]], left_on="first_contact_session_id", right_on="session_id")
    R.add("dates", "ticket opened_at = first contact session start", int((_ms(fs, "opened_at") != _ms(fs, "session_start_ts")).sum()))
    orig = tk[tk.origin_session_id.notna()].merge(ss[["session_id", "session_start_ts"]], left_on="origin_session_id", right_on="session_id")
    R.add("dates", "ticket opened after origin session start", int((_ms(orig, "opened_at") < _ms(orig, "session_start_ts")).sum()))
    R.add("dates", "status_history changed_at <= snapshot", int((_ms(sh, "changed_at") > SNAPSHOT_TS).sum()))
    dv = t["device"]
    R.add("dates", "device last_seen >= first_seen", int((_ms(dv, "last_seen_at") < _ms(dv, "first_seen_at")).sum()))
    # ------------------------------------------------------------ arithmetic reconciliation
    ol = t["order_line"]
    R.add("arithmetic", "order_line.line_amount = quantity*unit_price",
          int((np.abs(ol.quantity * ol.unit_price - ol.line_amount) > 0.005).sum()))
    agg = ol.groupby("order_id").agg(sub=("line_amount", "sum"), q=("quantity", "sum"), n=("line_no", "max"), c=("line_no", "size"))
    a = od.set_index("order_id").join(agg)
    R.add("arithmetic", "order.subtotal = sum(order_line.line_amount)", int((np.abs(a["sub"] - a.subtotal) > 0.005).sum()))
    R.add("arithmetic", "order.item_count = sum(order_line.quantity)", int((a.q != a.item_count).sum()))
    R.add("arithmetic", "order_line.line_no contiguous 1..n", int((a.n != a.c).sum()))
    R.add("arithmetic", "order.total = subtotal - discount + tax + shipping_fee",
          int((np.abs((a.subtotal - a.discount + a.tax + a.shipping_fee).round(2) - a.total) > 0.005).sum()))
    from .config import COUNTRIES
    rate = a.ship_country.map({k: v[2] for k, v in COUNTRIES.items()})
    R.add("arithmetic", "order.tax = round((subtotal-discount)*country_rate, 2)",
          int((np.abs(((a.subtotal - a.discount) * rate).round(2) - a.tax) > 0.011).sum()))
    R.add("arithmetic", "shipping_fee rule (0 if net >= 50 else 4.99)",
          int((np.where((a.subtotal - a.discount) >= 50, 0.0, 4.99) != a.shipping_fee).sum()))
    R.add("arithmetic", "discount is 0 or 10% of subtotal",
          int(((a.discount != 0) & (np.abs((a.subtotal * .10).round(2) - a.discount) > 0.011)).sum()))
    act = ci[ci.is_active]
    cagg = act.groupby("cart_id").agg(sub=("line_amount", "sum"), q=("quantity", "sum"))
    cc = cart.set_index("cart_id").join(cagg).fillna({"sub": 0, "q": 0})
    R.add("arithmetic", "cart.subtotal = sum(active cart_item.line_amount)", int((np.abs(cc["sub"] - cc.subtotal) > 0.005).sum()))
    R.add("arithmetic", "cart.item_count = sum(active quantity)", int((cc.q != cc.item_count).sum()))
    R.add("arithmetic", "cart_item.line_amount = quantity*unit_price",
          int((np.abs(ci.quantity * ci.unit_price - ci.line_amount) > 0.005).sum()))
    R.add("arithmetic", "cart_item.unit_price = product.list_price", int((ci.product_id.map(pr.list_price) != ci.unit_price).sum()))
    R.add("arithmetic", "cart_item.is_active = removed_at is null", int((ci.is_active != ci.removed_at.isna()).sum()))
    atc = ev.loc[ev.event_type == "add_to_cart", ["cart_id", "product_id", "quantity"]].assign(_t=e_ts[(ev.event_type == "add_to_cart").to_numpy()])
    m = ci[["cart_item_id", "cart_id", "product_id"]].assign(_a=_ms(ci, "added_at"), _r=_ms(ci, "removed_at")).merge(atc, on=["cart_id", "product_id"])
    m = m[(m._t >= m._a) & ((m._r == NAT) | (m._t <= m._r))]
    q_ev = m.groupby("cart_item_id").quantity.sum()
    R.add("arithmetic", "cart_item.quantity = sum(add_to_cart.quantity) within the line's lifetime",
          int((q_ev.reindex(ci.cart_item_id).fillna(0).astype(int).to_numpy() != ci.quantity.astype(int).to_numpy()).sum()))
    R.add("unique", "at most one active cart_item per (cart, product)", int(act.duplicated(["cart_id", "product_id"]).sum()))
    li = ol.merge(od[["order_id", "cart_id"]], on="order_id").set_index(["cart_id", "product_id"])
    R.add("arithmetic", "order lines = active cart items (product, qty)",
          int((li.quantity != act.set_index(["cart_id", "product_id"]).quantity.reindex(li.index)).sum()))
    pur = ev[ev.event_type == "purchase"]
    R.add("arithmetic", "purchase.value = order.total",
          int((np.abs(pur.order_id.map(od.set_index("order_id").total) - pur.value) > 0.005).sum()))
    ret = ev[ev.event_type.isin(["add_to_cart", "remove_from_cart"])]
    R.add("arithmetic", "cart event value = quantity*list_price",
          int((np.abs(ret.quantity * ret.product_id.map(pr.list_price) - ret.value) > 0.005).sum()))
    cs = ev[ev.event_type == "csat_submitted"].drop_duplicates("ticket_id").set_index("ticket_id").value
    R.add("arithmetic", "ticket.csat_score = csat_submitted.value",
          int((tk.set_index("ticket_id").csat_score.dropna().astype(float) != cs.reindex(tk.set_index("ticket_id").csat_score.dropna().index)).sum()))
    # ------------------------------------------------------------ lifecycle
    shs = sh.assign(_t=_ms(sh, "changed_at")).sort_values(["entity_type", "entity_id", "_t", "status_history_id"], kind="stable")
    allowed = set()
    for et_, tr in LIFECYCLES.items():
        for a_, b_ in tr:
            allowed.add((et_, a_ or "", b_))
    bad = (~pd.Series([(e, f or "", to) in allowed for e, f, to in
                       zip(shs.entity_type, shs.from_status.fillna(""), shs.to_status)])).sum()
    R.add("lifecycle", "status transitions allowed", int(bad))
    prev_to = shs.groupby(["entity_type", "entity_id"]).to_status.shift(1)
    chain_bad = (shs.from_status.fillna("") != prev_to.fillna("")).sum()
    R.add("lifecycle", "status chain continuous (from = previous to)", int(chain_bad))
    nondec = (shs.groupby(["entity_type", "entity_id"])._t.diff() < 0).sum()
    R.add("lifecycle", "status changes chronological", int(nondec))
    last = shs.groupby(["entity_type", "entity_id"]).tail(1).set_index(["entity_type", "entity_id"]).to_status
    for et_, (tbl, col) in ent_key.items():
        cur = t[tbl].set_index(col)["status" if et_ != "product" else "lifecycle_status"]
        lk = last.xs(et_, level=0).reindex(cur.index)
        R.add("lifecycle", f"{tbl}.status = last status_history", int((lk != cur).sum()))
    R.add("lifecycle", "converted carts have exactly one order",
          int((cart.status == "converted").sum() - cart.cart_id.isin(od.cart_id).sum()))
    # consent derivation
    cev = ce.assign(_t=_ms(ce, "effective_at")).sort_values(["_t", "consent_event_id"], kind="stable")
    lastc = cev.groupby(["customer_id", "consent_type"]).action.last()
    for ctype in ("analytics", "marketing"):
        exp = t["customer"].customer_id.map(lastc.xs(ctype, level=1)).fillna("unknown")
        R.add("derived", f"customer.{ctype}_consent_status derived from consent_event",
              int((exp != t["customer"][f"{ctype}_consent_status"]).sum()))
    # ------------------------------------------------------------ business rules
    if truth is not None:
        from .pipeline import consent_lookup
        mk = ce[ce.consent_type == "marketing"].assign(consent_type="analytics")  # reuse lookup on marketing history
        em = ss[ss.traffic_source.isin(["email", "push"])]
        person = em.session_id.map(truth["session_labels"].set_index("session_id").true_customer_id)
        ok = consent_lookup(mk, person.to_numpy(dtype=object), _ms(em, "session_start_ts"))
        R.add("rules", "email/push traffic only for persons with marketing consent (vs. truth person)", int((~ok).sum()))
    wa = pd.DataFrame(dict(s=ev.session_id.to_numpy(), t=e_ts))[(ev.channel != "support").to_numpy()]
    wa = wa.sort_values(["s", "t"], kind="stable")
    gd = np.diff(wa.t.to_numpy())
    same = wa.s.to_numpy()[1:] == wa.s.to_numpy()[:-1]
    R.add("rules", f"web/app: no within-session gap > {INACTIVITY_TIMEOUT_MS // 60000} min (event_ts)",
          int(len(set(wa.s.to_numpy()[1:][same & (gd > INACTIVITY_TIMEOUT_MS)]))))
    sp = ss[ss.channel != "support"].assign(_s=s0[(ss.channel != "support").to_numpy()], _e=s1[(ss.channel != "support").to_numpy()])
    sp = sp.sort_values(["device_id", "_s"], kind="stable")
    prev_end = sp.groupby("device_id")._e.shift(1)
    R.add("rules", "web/app sessions of a device separated by > 30 min", int(((sp._s - prev_end) <= INACTIVITY_TIMEOUT_MS).sum()))
    R.add("rules", "browser null iff app", int(((dv.platform == "app") != dv.browser.isna()).sum()))
    R.add("rules", "app_version only on app sessions", int(((ss.channel == "app") != ss.app_version.notna()).sum()))
    R.add("rules", "login links have confidence 1.0", int(((il.link_method == "login") & (il.confidence != 1.0)).sum()))
    sup = ss[ss.channel == "support"]
    R.add("rules", "support sessions reference a ticket", int(sup.ticket_id.isna().sum()))
    R.add("rules", "ticket priority rule", int((tk.category.isin(["payment_issue", "refund_request"]) != (tk.priority == "high")).sum()))
    # ------------------------------------------------------------ outcome (derived entity)
    jo = t.get("journey_outcome")
    if jo is not None:
        R.add("derived", "journey_outcome 1:1 with session", int(len(set(ss.session_id) ^ set(jo.session_id))))
        R.add("derived", "outcome_id = 'OUT-' + session_id", int((jo.outcome_id != "OUT-" + jo.session_id).sum()))
        R.add("derived", "converted outcome has an order", int((jo.converted & jo.order_id.isna()).sum()))
        R.add("derived", "valid_event_count <= session.event_count",
              int((jo.valid_event_count.to_numpy() > jo.session_id.map(ss.set_index("session_id").event_count).to_numpy()).sum()))
        n_conv = int(jo.converted.sum())
        R.add("derived", "deduplicated conversions = orders (no double counting)",
              abs(int(jo.order_id.dropna().nunique()) - len(od)) + abs(n_conv - len(od)))
    # ------------------------------------------------------------ labelled anomalies (truth reconciliation)
    if truth is not None:
        an = truth["anomalies"]
        lab_retry = set(an.loc[an.subtype == "sdk_retry_same_client_event_id", "entity_id"])
        x = ev.assign(_i=e_ing).sort_values(["_i", "event_id"], kind="stable")
        found_retry = set(x.loc[x.duplicated("client_event_id", keep="first"), "event_id"])
        R.add("labelled", "duplicate client_event_id rows are all labelled (and vice versa)",
              len(found_retry ^ lab_retry), kind="labelled")
        multi = pur.groupby("order_id").size()
        multi_orders = set(multi[multi > 1].index)
        lab_orders = {json.loads(d)["order_id"] for d in an.loc[an.issue_type == "duplicate_conversion", "detail"]}
        R.add("labelled", "orders with >1 purchase event are all labelled (and vice versa)", len(multi_orders ^ lab_orders),
              kind="labelled")
        arr = ev.event_id.str[-6:].astype(int).to_numpy()
        not_dup = (~ev.event_id.isin(set(an.loc[an.issue_type == "duplicate_conversion", "entity_id"]))).to_numpy()
        tmp = pd.DataFrame(dict(s=ev.session_id.to_numpy(), a=arr, t=e_ts))[not_dup].sort_values(["s", "t", "a"], kind="stable")
        sv = tmp.s.to_numpy()
        inv_s = set(sv[1:][(sv[1:] == sv[:-1]) & (np.diff(tmp.a.to_numpy()) < 0)])
        lab_inv = set(an.loc[an.issue_type == "ingestion_order_inversion", "session_id"])
        R.add("labelled", "sessions with ingestion/occurrence inversion (excl. labelled duplicates) are all labelled (and vice versa)",
              len(inv_s ^ lab_inv), kind="labelled", detail=f"found={len(inv_s)} labelled={len(lab_inv)}")
        R.add("labelled", "every anomaly references an existing entity", int(sum(
            (~an.loc[an.entity_type == k, "entity_id"].isin(set(t[tb][col]))).sum()
            for k, (tb, col) in {"session": ("session", "session_id"), "journey_event": ("journey_event", "event_id"),
                                 "identity_link": ("identity_link", "link_id")}.items())), kind="labelled")
        lab = truth["session_labels"]
        R.add("labelled", "session_labels cover every session exactly once",
              int(len(set(lab.session_id) ^ set(ss.session_id)) + lab.session_id.duplicated().sum()), kind="labelled")
        leaked = [f"{n}.{c}" for n, df in t.items() for c in df.columns if c in GROUND_TRUTH_ONLY_COLUMNS]
        R.add("leakage", "no ground-truth columns in input tables", len(leaked), detail=leaked)
        R.add("leakage", "no is_bot/actor flags in session table", int(any(c in ss.columns for c in ("is_bot", "actor_type"))))
    return R

