"""Assign immutable public IDs, compute derived values, build tables.

ID rules (counters zero-padded, assigned once, chronological):
  CUS-000001            customer, by created_at
  SES-2026-000001       session, by first event_ts (all sessions are in 2026)
  EVT-<session-id>-000001  event, by collector arrival (ingestion_ts) within session
  EXP-2026-000001       experiment, config order
  OUT-<session-id>      journey outcome (1:1 with session)
  DEV-0000001 / ANO-xxxxxxxxxx  device / its anonymous cookie-or-install id
  PRD-000001, PAG-0001, CRT-2026-000001, CIT-<cart-id>-01, ORD-2026-000001,
  OLN-<order-id>-01, TCK-2026-000001, AGT-0001, IDL-0000001, CNS-0000001,
  STH-00000001, ANM-000001 (ground truth only)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import config as C
from .config import SNAPSHOT_TS
from .simulate import Simulator
from .taxonomy import EVENT_NAMES, ERROR_CODES, EVENT_TAXONOMY, STAGE_NAME, SOURCE_SYSTEM


def iso(ms) -> np.ndarray:
    """epoch-ms (array / list, None/NaN/-1 = null) -> ISO-8601 UTC strings or None."""
    a = np.asarray(pd.array(ms, dtype="Int64").to_numpy(dtype="float64", na_value=np.nan))
    out = np.full(a.shape, None, dtype=object)
    ok = ~np.isnan(a) & (a >= 0)
    if ok.any():
        s = np.datetime_as_string(a[ok].astype("int64").astype("datetime64[ms]"), unit="ms")
        out[ok] = np.char.add(s.astype(str), "Z")
    return out


def _ids(prefix, n, width):
    return [f"{prefix}{i:0{width}d}" for i in range(1, n + 1)]


def _opt(arr, lookup):
    """map int refs (-1 = null) to id strings via lookup array."""
    arr = np.asarray(arr)
    out = np.full(arr.shape, None, dtype=object)
    ok = arr >= 0
    out[ok] = np.asarray(lookup, dtype=object)[arr[ok]]
    return out


class Dataset:
    def __init__(self):
        self.tables: dict[str, pd.DataFrame] = {}
        self.truth: dict[str, pd.DataFrame] = {}
        self.expected_findings: dict = {}
        self.derived: dict[str, pd.DataFrame] = {}
        self.meta: dict = {}


def finalize(sim: Simulator, ing: np.ndarray, dup_of: dict) -> Dataset:
    w, cfg = sim.w, sim.cfg
    ev = w.events
    D = Dataset()
    col = {c: np.array(getattr(ev, c), dtype=np.int64) for c in ev.INT_COLS}
    value = np.array(ev.value, dtype=np.float64)
    n_ev = len(col["ts"])
    sess, tsv = col["sess"], col["ts"]

    # ---------------------------------------------------------------- sessions
    n_s = len(w.sessions)
    first = np.full(n_s, np.iinfo(np.int64).max, dtype=np.int64)
    last = np.zeros(n_s, dtype=np.int64)
    np.minimum.at(first, sess, tsv)
    np.maximum.at(last, sess, tsv)
    cnt = np.bincount(sess, minlength=n_s)
    s_order = np.lexsort((np.arange(n_s), first))
    s_rank = np.empty(n_s, dtype=np.int64)
    s_rank[s_order] = np.arange(n_s)
    sid_sorted = np.array(_ids("SES-2026-", n_s, 6), dtype=object)
    sid = sid_sorted[s_rank]                       # by internal idx

    # ---------------------------------------------------------------- events
    e_order = np.lexsort((np.arange(n_ev), tsv, ing, s_rank[sess]))
    se = s_rank[sess][e_order]
    grp_start = np.r_[0, np.flatnonzero(np.diff(se)) + 1]
    counter = np.arange(n_ev) - np.repeat(grp_start, np.diff(np.r_[grp_start, n_ev])) + 1
    eid_sorted = pd.Series(sid[sess[e_order]]).str.cat(pd.Series(counter).map("{:06d}".format), sep="-")
    eid_sorted = ("EVT-" + eid_sorted).to_numpy(dtype=object)
    eid = np.empty(n_ev, dtype=object)
    eid[e_order] = eid_sorted
    rng = np.random.default_rng(cfg.seed + 7)
    client_raw = rng.integers(0, np.iinfo(np.int64).max, size=n_ev, dtype=np.int64)
    for dup, (orig, subtype) in dup_of.items():
        if subtype == "sdk_retry_same_client_event_id":
            client_raw[dup] = client_raw[orig]
    client_id = np.array(["ce-%016x" % v for v in client_raw.tolist()], dtype=object)

    # ---------------------------------------------------------------- devices
    dev_of_sess = np.array([s["device"] for s in w.sessions], dtype=np.int64)
    n_d = len(w.devices)
    used = dev_of_sess[dev_of_sess >= 0]
    d_first = np.full(n_d, np.iinfo(np.int64).max, dtype=np.int64)
    d_last = np.zeros(n_d, dtype=np.int64)
    np.minimum.at(d_first, used, first[dev_of_sess >= 0])
    np.maximum.at(d_last, used, last[dev_of_sess >= 0])
    keep = np.flatnonzero(d_first < np.iinfo(np.int64).max)
    keep = keep[np.lexsort((keep, d_first[keep]))]
    dev_id = np.full(n_d, None, dtype=object)
    anon_id = np.full(n_d, None, dtype=object)
    for k, d in enumerate(keep.tolist(), 1):
        dev_id[d] = f"DEV-{k:07d}"
        anon_id[d] = "ANO-%010x" % ((k * 0x9E3779B1 + cfg.seed) % (1 << 40))
    D.tables["device"] = pd.DataFrame(dict(
        device_id=dev_id[keep], anonymous_id=anon_id[keep],
        platform=[w.devices[d]["platform"] for d in keep], device_type=[w.devices[d]["device_type"] for d in keep],
        os=[w.devices[d]["os"] for d in keep], browser=[w.devices[d]["browser"] for d in keep],
        first_seen_at=iso(d_first[keep]), last_seen_at=iso(d_last[keep])))

    # ---------------------------------------------------------------- customers
    n_c = len(w.customers)
    cus_id = np.array(_ids("CUS-", n_c, 6), dtype=object)
    cons = sorted(w.consent_events, key=lambda e: (e["effective_at"], e["customer_idx"], e["consent_type"]))
    cur = {}
    for e in cons:
        if e["effective_at"] <= SNAPSHOT_TS:
            cur[(e["customer_idx"], e["consent_type"])] = e["action"]
    # authenticated customer per session (from events)
    has_c = col["cust"] >= 0
    sess_cust = np.full(n_s, -1, dtype=np.int64)
    sess_cust[sess[has_c]] = col["cust"][has_c]
    c_last = np.full(n_c, -1, dtype=np.int64)
    mask = sess_cust >= 0
    np.maximum.at(c_last, sess_cust[mask], last[mask])
    status = np.where(c_last < 0, "registered_no_activity",
                      np.where(SNAPSHOT_TS - c_last <= 90 * C.DAY, "active", "dormant"))
    D.tables["customer"] = pd.DataFrame(dict(
        customer_id=cus_id, created_at=iso([c["created_at"] for c in w.customers]),
        country=[c["country"] for c in w.customers], segment=[c["segment"] for c in w.customers],
        signup_channel=[c["signup_channel"] for c in w.customers],
        email_hash=["sha256:%064x" % (hash_int(cfg.seed, i)) for i in range(n_c)],
        analytics_consent_status=[_cs(cur.get((i, "analytics"))) for i in range(n_c)],
        marketing_consent_status=[_cs(cur.get((i, "marketing"))) for i in range(n_c)],
        consent_status_as_of=iso([SNAPSHOT_TS] * n_c)[0],
        last_authenticated_at=iso(c_last), lifecycle_status=status))
    D.tables["consent_event"] = pd.DataFrame(dict(
        consent_event_id=_ids("CNS-", len(cons), 7), customer_id=cus_id[[e["customer_idx"] for e in cons]],
        consent_type=[e["consent_type"] for e in cons], action=[e["action"] for e in cons],
        effective_at=iso([e["effective_at"] for e in cons]),
        recorded_at=iso([e["effective_at"] + (hash_int(cfg.seed, k) % 5000) for k, e in enumerate(cons)]),
        source=[e["source"] for e in cons], policy_version=[e["policy_version"] for e in cons]))

    # ---------------------------------------------------------------- reference
    prd_id = np.array(_ids("PRD-", len(w.products), 6), dtype=object)
    D.tables["product"] = pd.DataFrame(dict(
        product_id=prd_id, name=[p["name"] for p in w.products], brand=[p["brand"] for p in w.products],
        category=[p["category"] for p in w.products], list_price=[p["list_price"] for p in w.products],
        currency="USD", launched_at=iso([p["launched_at"] for p in w.products]),
        discontinued_at=iso([p["discontinued_at"] if p["discontinued_at"] is not None else -1 for p in w.products]),
        lifecycle_status=["discontinued" if p["discontinued_at"] and p["discontinued_at"] <= SNAPSHOT_TS else "active"
                          for p in w.products]))
    pag_id = np.array(_ids("PAG-", len(w.pages), 4), dtype=object)
    D.tables["page"] = pd.DataFrame(dict(
        page_id=pag_id, channel=[p["channel"] for p in w.pages], page_type=[p["page_type"] for p in w.pages],
        path=[p["path"] for p in w.pages], category=[p["category"] for p in w.pages],
        help_topic=[p["help_topic"] for p in w.pages], funnel_stage=[p["funnel_stage"] for p in w.pages],
        is_active=True, created_at=iso([C.ts("2025-01-01T00:00:00Z")] * len(w.pages))))
    exp_id = np.array(_ids("EXP-2026-", len(w.experiments), 6), dtype=object)
    D.tables["experiment"] = pd.DataFrame(dict(
        experiment_id=exp_id, name=[e["name"] for e in w.experiments],
        hypothesis=[e["hypothesis"] for e in w.experiments], channel=[e["channel"] for e in w.experiments],
        target_step=[e["target_step"] for e in w.experiments], status=[e["status"] for e in w.experiments],
        allocation_treatment=[e["allocation_treatment"] for e in w.experiments],
        assignment_unit="device", owner_team=[e["owner_team"] for e in w.experiments],
        created_at=iso([e["created_ms"] for e in w.experiments]),
        start_at=iso([e["start_ms"] for e in w.experiments]), end_at=iso([e["end_ms"] for e in w.experiments])))
    agt_id = np.array(_ids("AGT-", len(w.agents), 4), dtype=object)
    D.tables["support_agent"] = pd.DataFrame(dict(
        agent_id=agt_id, tier=[a["tier"] for a in w.agents], team=[a["team"] for a in w.agents],
        site=[a["site"] for a in w.agents], hired_at=iso([a["hired_at"] for a in w.agents])))
    D.tables["event_taxonomy"] = pd.DataFrame(
        [dict(event_type=e[0], category=e[1], funnel_stage=e[2], funnel_stage_name=STAGE_NAME[e[2]] if e[2] else None,
              allowed_channels=e[3], required_refs=e[4], description=e[5]) for e in EVENT_TAXONOMY])

    # ---------------------------------------------------------------- carts / orders
    carts = sorted(w.carts, key=lambda c: (c["created_at"], c["idx"]))
    crt_id = np.full(len(w.carts), None, dtype=object)
    for k, c in enumerate(carts, 1):
        crt_id[c["idx"]] = f"CRT-2026-{k:06d}"
    orders = sorted(w.orders, key=lambda o: (o["order_ts"], o["idx"]))
    ord_id = np.full(len(w.orders), None, dtype=object)
    for k, o in enumerate(orders, 1):
        ord_id[o["idx"]] = f"ORD-2026-{k:06d}"
    tickets = sorted(w.tickets, key=lambda t: (t["opened_at"], t["idx"]))
    tck_id = np.full(len(w.tickets), None, dtype=object)
    for k, t in enumerate(tickets, 1):
        tck_id[t["idx"]] = f"TCK-2026-{k:06d}"

    items_by_cart = {}
    for it in w.cart_items:
        items_by_cart.setdefault(it["cart_idx"], []).append(it)
    hist_last = {}
    for h in sorted(w.status_history, key=lambda h: h["changed_at"]):
        hist_last[(h["entity_type"], h["entity_idx"])] = h
    ci_rows = []
    cart_rows = []
    for c in carts:
        its = sorted(items_by_cart.get(c["idx"], []), key=lambda x: (x["added_at"], x["idx"]))
        for n, it in enumerate(its, 1):
            ci_rows.append(dict(cart_item_id=f"CIT-{crt_id[c['idx']]}-{n:02d}", cart_id=crt_id[c["idx"]],
                                product_id=prd_id[it["product_idx"]], quantity=it["quantity"],
                                unit_price=it["unit_price"], line_amount=round(it["quantity"] * it["unit_price"], 2),
                                added_at=it["added_at"], removed_at=it["removed_at"] if it["removed_at"] is not None else -1,
                                is_active=it["removed_at"] is None))
        act = [it for it in its if it["removed_at"] is None]
        s = w.sessions[c["session"]]
        h = hist_last.get(("cart", c["idx"]))
        cart_rows.append(dict(cart_id=crt_id[c["idx"]], session_id=sid[c["session"]],
                              customer_id=cus_id[c["cust"]] if c["cust"] >= 0 else None,
                              anonymous_id=anon_id[s["device"]] if s["device"] >= 0 else None,
                              created_at=c["created_at"], checkout_started_at=c["checkout_at"] or -1,
                              status=h["to_status"] if h else c["status"], status_at=h["changed_at"] if h else -1,
                              item_count=sum(i["quantity"] for i in act),
                              subtotal=round(sum(round(i["quantity"] * i["unit_price"], 2) for i in act), 2)))
    cart_df = pd.DataFrame(cart_rows)
    for k in ("created_at", "checkout_started_at", "status_at"):
        cart_df[k] = iso(cart_df[k])
    D.tables["cart"] = cart_df
    ci_df = pd.DataFrame(ci_rows)
    for k in ("added_at", "removed_at"):
        ci_df[k] = iso(ci_df[k])
    D.tables["cart_item"] = ci_df

    lines_by_order = {}
    for ln in w.order_lines:
        lines_by_order.setdefault(ln["order_idx"], []).append(ln)
    o_rows, ol_rows = [], []
    for o in orders:
        h = hist_last[("order", o["idx"])]
        o_rows.append(dict(order_id=ord_id[o["idx"]], cart_id=crt_id[o["cart_idx"]], session_id=sid[o["session"]],
                           customer_id=cus_id[o["cust"]] if o["cust"] >= 0 else None, order_ts=o["order_ts"],
                           status=h["to_status"], status_at=h["changed_at"], ship_country=o["ship_country"],
                           currency=o["currency"], payment_method=o["payment_method"], item_count=o["item_count"],
                           subtotal=o["subtotal"], discount=o["discount"], tax=o["tax"],
                           shipping_fee=o["shipping"], total=o["total"]))
        for ln in sorted(lines_by_order[o["idx"]], key=lambda x: x["line_no"]):
            ol_rows.append(dict(order_line_id=f"OLN-{ord_id[o['idx']]}-{ln['line_no']:02d}", order_id=ord_id[o["idx"]],
                                line_no=ln["line_no"], product_id=prd_id[ln["product_idx"]], quantity=ln["quantity"],
                                unit_price=ln["unit_price"], line_amount=ln["line_amount"]))
    o_df = pd.DataFrame(o_rows)
    for k in ("order_ts", "status_at"):
        o_df[k] = iso(o_df[k])
    D.tables["order"] = o_df
    D.tables["order_line"] = pd.DataFrame(ol_rows)

    t_rows = []
    for t in tickets:
        t_rows.append(dict(ticket_id=tck_id[t["idx"]], customer_id=cus_id[t["cust"]] if t["cust"] >= 0 else None,
                           origin_session_id=sid[t["origin_session"]] if t["origin_session"] >= 0 else None,
                           first_contact_session_id=sid[t["first_session"]],
                           order_id=ord_id[t["order"]] if t["order"] >= 0 else None, medium=t["medium"],
                           category=t["category"], priority=t["priority"],
                           status=hist_last[("ticket", t["idx"])]["to_status"],
                           opened_at=t["opened_at"], first_response_at=t["first_response_at"] or -1,
                           escalated_at=t["escalated_at"] or -1, resolved_at=t["resolved_at"] or -1,
                           closed_at=t["closed_at"] or -1, agent_id=agt_id[t["agent"]] if t["agent"] >= 0 else None,
                           csat_score=t["csat"]))
    t_df = pd.DataFrame(t_rows)
    for k in ("opened_at", "first_response_at", "escalated_at", "resolved_at", "closed_at"):
        t_df[k] = iso(t_df[k])
    t_df["csat_score"] = t_df["csat_score"].astype("Int64")
    D.tables["support_ticket"] = t_df

    # ---------------------------------------------------------------- sessions table
    landing = np.full(n_s, -1, dtype=np.int64)
    # landing page = page of session_start event (or first occurrence)
    occ = np.lexsort((np.arange(n_ev), tsv, sess))
    occ_start = np.r_[0, np.flatnonzero(np.diff(sess[occ])) + 1]
    landing[sess[occ[occ_start]]] = col["page"][occ[occ_start]]
    S = w.sessions
    rows = dict(
        session_id=sid[s_order], channel=[S[i]["channel"] for i in s_order],
        device_id=_opt(dev_of_sess[s_order], dev_id), anonymous_id=_opt(dev_of_sess[s_order], anon_id),
        customer_id=_opt(sess_cust[s_order], cus_id),
        session_start_ts=iso(first[s_order]), session_end_ts=iso(last[s_order]),
        duration_s=np.round((last[s_order] - first[s_order]) / 1000.0, 3), event_count=cnt[s_order],
        traffic_source=[S[i].get("traffic_source") for i in s_order],
        utm_campaign=[S[i].get("utm_campaign") for i in s_order],
        landing_page_id=_opt(landing[s_order], pag_id),
        user_agent=[S[i].get("user_agent") for i in s_order], ip_hash=[S[i].get("ip_hash") for i in s_order],
        geo_country=[S[i].get("geo_country") for i in s_order], app_version=[S[i].get("app_version") for i in s_order],
        support_medium=[S[i].get("support_medium") for i in s_order],
        ticket_id=_opt(np.array([S[i]["ticket"] for i in s_order]), tck_id),
        sessionization_rule=["support_contact_v1" if S[i]["channel"] == "support" else "web_app_inactivity_30m_v1"
                             for i in s_order],
    )
    D.tables["session"] = pd.DataFrame(rows)
    # experiment assignments (bridge Experiment N:M Session)
    a_rows = []
    for i in s_order:
        for e_idx, var in sorted(S[i].get("variants", {}).items()):
            a_rows.append(dict(experiment_id=exp_id[e_idx], session_id=sid[i], variant=var,
                               assigned_at=first[i], assignment_unit="device",
                               device_id=dev_id[S[i]["device"]]))
    a_df = pd.DataFrame(a_rows, columns=["experiment_id", "session_id", "variant", "assigned_at", "assignment_unit", "device_id"])
    a_df["assigned_at"] = iso(a_df["assigned_at"])
    D.tables["experiment_assignment"] = a_df.sort_values(["experiment_id", "session_id"], kind="stable").reset_index(drop=True)

    # ---------------------------------------------------------------- journey events
    chan_code = np.array([{"web": 0, "app": 1, "support": 2}[s["channel"]] for s in S], dtype=np.int64)[sess]
    chan_names = np.array(["web", "app", "support"], dtype=object)
    src_names = np.array([SOURCE_SYSTEM["web"], SOURCE_SYSTEM["app"], SOURCE_SYSTEM["support"]], dtype=object)
    dev_e = dev_of_sess[sess]
    cust_e = col["cust"]
    auth = np.where(cust_e >= 0, "authenticated", "anonymous").astype(object)
    sup = chan_code == 2
    auth[sup & (cust_e >= 0)] = "agent_verified"
    auth[sup & (cust_e < 0)] = "unverified"
    o = e_order
    err = col["err"][o]
    evdf = pd.DataFrame(dict(
        event_id=eid_sorted, session_id=sid[sess[o]],
        event_type=np.array(EVENT_NAMES, dtype=object)[col["etype"][o]],
        event_ts=iso(tsv[o]), ingestion_ts=iso(ing[o]),
        channel=chan_names[chan_code[o]], source_system=src_names[chan_code[o]],
        device_id=_opt(dev_e[o], dev_id), anonymous_id=_opt(dev_e[o], anon_id),
        customer_id=_opt(cust_e[o], cus_id), auth_state=auth[o],
        page_id=_opt(col["page"][o], pag_id), product_id=_opt(col["product"][o], prd_id),
        cart_id=_opt(col["cart"][o], crt_id), order_id=_opt(col["order"][o], ord_id),
        ticket_id=_opt(col["ticket"][o], tck_id), client_event_id=client_id[o],
        page_load_ms=pd.array(np.where(col["load"][o] >= 0, col["load"][o], 0), dtype="Int64"),
        http_status=pd.array(col["http"][o], dtype="Int64"),
        error_code=np.where(err > 0, np.array(ERROR_CODES, dtype=object)[err], None),
        quantity=pd.array(col["qty"][o], dtype="Int64"),
        value=value[o]))
    evdf.loc[col["load"][o] < 0, "page_load_ms"] = pd.NA
    evdf.loc[col["http"][o] == 0, "http_status"] = pd.NA
    evdf.loc[col["qty"][o] == 0, "quantity"] = pd.NA
    D.tables["journey_event"] = evdf

    # ---------------------------------------------------------------- identity links
    links = sorted(range(len(w.links)), key=lambda i: (w.links[i]["valid_from"], i))
    link_id = np.full(len(w.links), None, dtype=object)
    for k, i in enumerate(links, 1):
        link_id[i] = f"IDL-{k:07d}"
    L = w.links
    D.tables["identity_link"] = pd.DataFrame(dict(
        link_id=link_id[links], device_id=dev_id[[L[i]["device_idx"] for i in links]],
        anonymous_id=anon_id[[L[i]["device_idx"] for i in links]],
        customer_id=cus_id[[L[i]["customer_idx"] for i in links]],
        link_method=[L[i]["link_method"] for i in links], confidence=[L[i]["confidence"] for i in links],
        valid_from=iso([L[i]["valid_from"] for i in links]), valid_to=iso([-1] * len(links)),
        source_system=[L[i]["source_system"] for i in links],
        created_at=iso([L[i]["valid_from"] + 1500 for i in links])))

    # ---------------------------------------------------------------- status history
    ent_ids = {"cart": crt_id, "order": ord_id, "ticket": tck_id, "experiment": exp_id, "product": prd_id}
    hs = sorted(w.status_history, key=lambda h: (h["changed_at"], h["entity_type"], ent_ids[h["entity_type"]][h["entity_idx"]]))
    D.tables["status_history"] = pd.DataFrame(dict(
        status_history_id=_ids("STH-", len(hs), 8), entity_type=[h["entity_type"] for h in hs],
        entity_id=[ent_ids[h["entity_type"]][h["entity_idx"]] for h in hs],
        from_status=[h["from_status"] for h in hs], to_status=[h["to_status"] for h in hs],
        changed_at=iso([h["changed_at"] for h in hs]), changed_by=[h["changed_by"] for h in hs]))

    # ---------------------------------------------------------------- ground truth
    dup_eids = {eid[k] for k in dup_of}
    is_dup = np.zeros(n_ev, dtype=bool)
    is_dup[list(dup_of)] = True
    D.meta["baseline_event_mask"] = ~is_dup[o]     # aligned to journey_event rows
    D.meta["bogus_link_ids"] = {link_id[i] for i, l in enumerate(L) if l["_bogus"]}
    refs = dict(session=sid, journey_event=eid, identity_link=link_id)
    an_rows = []
    for k, a in enumerate(sorted(w.anomalies, key=lambda a: (a["issue_type"], str(refs[a["entity_type"]][a["entity_ref"]]))), 1):
        det = dict(a["detail"])
        for key in list(det):
            if key == "first_delayed_event_ref":
                det["first_delayed_event_id"] = eid[det.pop(key)]
            elif key == "order_ref":
                det["order_id"] = ord_id[det.pop(key)]
            elif key == "device_ref":
                det["device_id"] = dev_id[det.pop(key)]
            elif key == "wrong_customer_ref":
                det["linked_customer_id"] = cus_id[det.pop(key)]
            elif key == "true_owner_refs":
                det["true_owner_customer_ids"] = [cus_id[x] for x in det.pop(key)]
        an_rows.append(dict(anomaly_id=f"ANM-{k:06d}", issue_type=a["issue_type"], subtype=a["subtype"],
                            entity_type=a["entity_type"], entity_id=refs[a["entity_type"]][a["entity_ref"]],
                            session_id=sid[a["session_idx"]] if a["session_idx"] is not None else None,
                            related_id=eid[a["related_ref"]] if a["related_ref"] is not None else None,
                            expected_decision=a["expected_decision"], severity=a["severity"],
                            detail=json.dumps(det, sort_keys=True)))
    D.truth["anomalies"] = pd.DataFrame(an_rows)
    true_person = np.array([s["_person"] for s in S], dtype=np.int64)
    D.truth["session_labels"] = pd.DataFrame(dict(
        session_id=sid[s_order], actor_type=[S[i]["_actor"] for i in s_order],
        bot_type=[S[i]["_bot_type"] for i in s_order],
        true_customer_id=_opt(np.where(np.array([S[i]["_actor"] for i in s_order]) == "bot", -1, true_person[s_order]), cus_id)))
    D.meta["sid"] = sid
    D.meta["config"] = cfg.to_dict()
    return D


def _cs(action):
    return {None: "unknown", "granted": "granted", "denied": "denied", "withdrawn": "withdrawn",
            "expired": "expired"}[action]


def hash_int(seed, i):
    x = (i + 1) * 0x9E3779B97F4A7C15 + seed * 0xBF58476D1CE4E5B9
    x &= (1 << 64) - 1
    x ^= x >> 31
    x = (x * 0x94D049BB133111EB) & ((1 << 64) - 1)
    return (x << 192) | (x << 128) | (x << 64) | x
