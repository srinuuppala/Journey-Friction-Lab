"""Labelled edge-case injection (runs only after the valid baseline exists).

Every injected change produces a row in ``world.anomalies`` (later written to
``ground_truth/anomalies.csv``).  Unrelated rows are never touched.

Edge cases required by the brief:
  * ingestion_order_inversion - events whose collector arrival order differs
                                from occurrence order (offline buffer flush)
  * incorrect_identity_merge  - anonymous / foreign devices wrongly linked to a
                                customer in the identity graph
  * duplicate_conversion      - the same order's purchase event counted twice
                                (SDK retry, page reload, re-fire in later session)
  * bot_traffic               - declared crawlers, disguised scrapers, cart bots
                                and cookie-replay bots that reuse a real
                                customer's device and authenticated cookie
Additional labelled coverage:
  * late_arrival              - tail events ingested > 1 h late (no reordering)
"""
from __future__ import annotations

import math

import numpy as np

from . import config as C
from .config import DAY, HOUR, MIN, SEC, PERIOD_START as P0, PERIOD_END as P1
from .simulate import Simulator, NAN, DEVICE_KINDS
from .taxonomy import EV

BOT_UA = {
    "declared_crawler": "ExampleCrawler/2.1 (+https://crawler.example.invalid/bot)",
}
DC_COUNTRIES = (["US", "SG", "DE", "IN", "GB"], [.40, .20, .20, .10, .10])


def anomaly(world, issue_type, subtype, entity_type, entity_ref, session_idx, expected_decision,
            severity="error", related_ref=None, **detail):
    world.anomalies.append(dict(issue_type=issue_type, subtype=subtype, entity_type=entity_type,
                                entity_ref=entity_ref, session_idx=session_idx, related_ref=related_ref,
                                expected_decision=expected_decision, severity=severity, detail=detail))


# ---------------------------------------------------------------------------
# Bots
# ---------------------------------------------------------------------------
def inject_bots(sim: Simulator):
    R, w, ev, cfg = sim.R, sim.w, sim.ev, sim.cfg
    n_bots = cfg.n_sessions - len(w.sessions)
    n_replay = round(n_bots * cfg.cookie_replay_bot_share)
    rest = n_bots - n_replay
    n_decl = round(rest * .40)
    n_cart = round(rest * .17)
    n_disg = rest - n_decl - n_cart
    n_stealth = round(n_disg * .30)
    n_disg -= n_stealth
    plan = (["declared_crawler"] * n_decl + ["disguised_scraper"] * n_disg + ["stealth_scraper"] * n_stealth
            + ["cart_bot"] * n_cart
            + ["cookie_replay"] * n_replay)
    R.shuffle(plan)
    ip_pool = ["IPH-dc%06x" % R.getrandbits(24) for _ in range(max(8, round(40 * cfg.scale ** .5)))]
    victims = [s for s in w.sessions if s["kind"] == "human" and s["_person"] >= 0 and s["auth_at_start"]]
    for btype in plan:
        if btype == "cookie_replay" and not victims:
            btype = "disguised_scraper"
        if btype == "cookie_replay":
            for _ in range(30):
                v = victims[int(R.random() * len(victims))]
                start = v["start"] + int(HOUR + R.random() * 10 * DAY)
                if start < P1 - 3 * HOUR and sim.device_free(v["device"], start):
                    break
            else:
                btype = "disguised_scraper"
        if btype != "cookie_replay":
            kind = "app_mobile" if (btype == "disguised_scraper" and R.random() < .12) else \
                R.choice(["web_desktop", "web_mobile"]) if btype == "stealth_scraper" else "web_desktop"
            platform, dtype, oses, browsers = DEVICE_KINDS[kind]
            start = sim.sample_time(P0, P1 - 3 * HOUR, "US", flat=True)
            dev = dict(idx=len(w.devices), kind=kind, platform=platform, device_type=dtype, os=R.choice(oses),
                       browser=R.choice(browsers), country=R.choices(*DC_COUNTRIES)[0], first_seen=start,
                       owners=[], activity=0.0, update_lag=0, ip_salt=R.getrandbits(32))
            w.devices.append(dev)
            person = -1
        else:
            dev = w.devices[v["device"]]
            person = v["_person"]
        ctx = sim.build_context(dev, -1, start)
        if btype == "stealth_scraper":      # residential proxy: unique IP, local geo
            ctx["ip_hash"] = sim.ip_hash(dev, start)
            ctx["geo_country"] = R.choices(list(C.COUNTRIES), weights=[v[0] for v in C.COUNTRIES.values()])[0]
        else:
            ctx["ip_hash"] = R.choice(ip_pool)
            ctx["geo_country"] = R.choices(*DC_COUNTRIES)[0]
        ctx["traffic_source"] = "direct" if btype != "declared_crawler" else "organic_search"
        ctx["utm_campaign"] = None
        if btype == "declared_crawler":
            ctx["user_agent"] = BOT_UA["declared_crawler"]
        s = sim.new_session("bot", dev["platform"], dev["idx"], person, start, **ctx)
        s["_bot_type"] = btype
        sim.reserve_device(dev["idx"], start, s["idx"])
        run_bot(sim, s, btype, auth_cust=person if btype == "cookie_replay" else -1)
        anomaly(w, "bot_traffic", btype, "session", s["idx"], s["idx"],
                "exclude from funnel/drop-off metrics; never stitch to a customer", severity="warning",
                user_agent=s["user_agent"])
    return n_bots


def run_bot(sim: Simulator, s, btype, auth_cust=-1):
    R, ev, w = sim.R, sim.ev, sim.w
    si, ch = s["idx"], s["channel"]
    t = s["start"]
    view = EV["screen_view"] if ch == "app" else EV["page_view"]
    cust = auth_cust
    page = sim.page

    def gap():
        if btype == "declared_crawler":
            return int(2 * SEC + R.random() * 2 * SEC)
        if btype == "cookie_replay":
            return int(500 + R.random() * 1500)
        if btype == "stealth_scraper":
            return int(4500 * math.exp(.7 * R.gauss(0, 1)))
        return int(300 + R.random() * 1200)

    land = "category" if btype != "cookie_replay" else "home"
    cat = R.choice(sim.cat_names)
    ev.add(si, EV["session_start"], t, page=page(ch, land, cat), cust=cust)
    if btype == "declared_crawler":
        n = max(10, int(48 * math.exp(.6 * R.gauss(0, 1))))
    elif btype in ("disguised_scraper", "stealth_scraper"):
        n = max(15, int(44 * math.exp(.6 * R.gauss(0, 1))))
    elif btype == "cookie_replay":
        n = max(10, int(30 * math.exp(.5 * R.gauss(0, 1))))
    else:
        n = 8 + int(R.random() * 18)
    cart = None
    bot_lines = {}
    for k in range(n):
        t += gap()
        if btype == "declared_crawler" and R.random() < .25:
            st = R.choice(["category", "home", "help"])
            ev.add(si, view, t, page=page(ch, st, R.choice(sim.cat_names), R.choice(C.HELP_TOPICS)),
                   cust=cust, load=int(300 + R.random() * 400))
            continue
        p = sim.pick_product(t)
        pg = page(ch, "product")
        ev.add(si, view, t, page=pg, cust=cust, load=int(250 + R.random() * 500))
        t += int(50 + R.random() * 200)
        ev.add(si, EV["product_view"], t, page=pg, product=p["idx"], cust=cust)
        if btype == "stealth_scraper" and R.random() < .35:
            t += int(300 + R.random() * 2000)
            ev.add(si, EV["scroll"], t, page=pg, cust=cust)
        if btype == "cart_bot":
            t += int(100 + R.random() * 300)
            if cart is None:
                cart = dict(idx=len(w.carts), session=si, created_at=t, checkout_at=None, order=-1, cust=-1,
                            status="abandoned")
                w.carts.append(cart)
            q = 3 + int(R.random() * 8)
            line = bot_lines.get(p["idx"])
            if line is None:
                line = dict(idx=len(w.cart_items), cart_idx=cart["idx"], product_idx=p["idx"], quantity=0,
                            unit_price=p["list_price"], added_at=t, removed_at=None)
                w.cart_items.append(line)
                bot_lines[p["idx"]] = line
            line["quantity"] += q
            ev.add(si, EV["add_to_cart"], t, page=pg, product=p["idx"], cart=cart["idx"], qty=q,
                   value=round(q * p["list_price"], 2), cust=cust)
        elif btype == "cookie_replay" and R.random() < .1:
            t += gap()
            ev.add(si, view, t, page=page(ch, "login"), cust=cust, load=int(200 + R.random() * 300))
    if cart is not None:
        t += gap()
        ev.add(si, EV["cart_view"], t, page=page(ch, "cart"), cart=cart["idx"], cust=cust)
        t += gap()
        cart["checkout_at"] = t
        ev.add(si, EV["checkout_start"], t, page=page(ch, "cart"), cart=cart["idx"], cust=cust)
        t += gap()
        ev.add(si, view, t, page=page(ch, "shipping"), cust=cust, load=400)
        t += gap()
        ev.add(si, EV["shipping_info_submitted"], t, page=page(ch, "shipping"), cart=cart["idx"], cust=cust)
        sim.history("cart", cart["idx"], None, "open", cart["created_at"])
        sim.history("cart", cart["idx"], "open", "checkout_started", cart["checkout_at"])
        sim.history("cart", cart["idx"], "checkout_started", "abandoned", t + C.INACTIVITY_TIMEOUT_MS)
    s["end_planned"] = t
    s["flags"] = {}


# ---------------------------------------------------------------------------
# Event-level injections operate on numpy views of the event buffer
# ---------------------------------------------------------------------------
def baseline_ingestion(sim: Simulator, rng: np.random.Generator):
    """Collector arrival times for every event; monotone per session (valid baseline)."""
    ev, w = sim.ev, sim.w
    sess = np.array(ev.sess, dtype=np.int64)
    tsv = np.array(ev.ts, dtype=np.int64)
    n = len(tsv)
    order = np.lexsort((np.arange(n), tsv, sess))
    chan = np.array([{"web": 0, "app": 1, "support": 2}[s["channel"]] for s in w.sessions], dtype=np.int8)[sess]
    med = np.array([700.0, 1800.0, 300.0])[chan]
    sig = np.array([.6, 1.0, .4])[chan]
    lat = med * np.exp(sig * rng.standard_normal(n))
    ing = tsv + lat.astype(np.int64)
    # cummax per session along occurrence order -> monotone arrival
    so = sess[order]
    off = so * np.int64(10 ** 13)
    mono = np.maximum.accumulate(ing[order] + off) - off
    ing2 = np.empty(n, dtype=np.int64)
    ing2[order] = mono
    return ing2, order


def inject_event_anomalies(sim: Simulator, ing: np.ndarray, order: np.ndarray):
    """Returns (ingestion array, dup_of dict) after adding reorder / late / duplicate cases."""
    R, w, ev, cfg = sim.R, sim.w, sim.ev, sim.cfg
    sess = np.array(ev.sess, dtype=np.int64)
    so = sess[order]
    bounds = np.flatnonzero(np.diff(so)) + 1
    starts = np.concatenate([[0], bounds])
    ends = np.concatenate([bounds, [len(so)]])
    sess_rows = {int(so[a]): order[a:b] for a, b in zip(starts, ends)}

    # 1) ingestion order inversions ----------------------------------------------
    eligible = [s["idx"] for s in w.sessions if s["kind"] == "human" and len(sess_rows.get(s["idx"], ())) >= 10]
    app_el = [i for i in eligible if w.sessions[i]["channel"] == "app"]
    web_el = [i for i in eligible if w.sessions[i]["channel"] == "web"]
    n_re = round(len(eligible) * cfg.reorder_session_rate)
    n_app = min(len(app_el), round(n_re * .7))
    chosen = R.sample(app_el, n_app) + R.sample(web_el, min(len(web_el), n_re - n_app))
    used = set()
    for si in sorted(chosen):
        rows = sess_rows[si]
        n = len(rows)
        k = 2 + int(R.random() * (n - 6))
        L = min(3 + int(R.random() * 6), n - k - 2)
        delay = int(min(6 * HOUR, 20 * MIN * math.exp(abs(R.gauss(0, 1.0)))))
        block = rows[k:k + L]
        ing[block] += delay
        nxt = rows[k + L]
        if ing[nxt] >= ing[block[-1]]:          # guarantee an observable inversion
            ing[block] += ing[nxt] - ing[block[-1]] + 1000
        used.add(si)
        anomaly(w, "ingestion_order_inversion", "offline_buffer_flush" if w.sessions[si]["channel"] == "app"
                else "beacon_retry", "session", si, si,
                "order by event_ts (not ingestion/event_id) before sessionizing, funnel and path analysis",
                events_delayed=int(L), delay_ms=int(delay), first_delayed_event_ref=int(block[0]))
    # 2) late tail arrivals (no inversion) -------------------------------------------
    pool = [s["idx"] for s in w.sessions if s["kind"] != "bot" and s["idx"] not in used
            and len(sess_rows.get(s["idx"], ())) >= 3]
    for si in sorted(R.sample(pool, round(len(pool) * cfg.late_tail_session_rate))):
        rows = sess_rows[si]
        m = 1 + int(R.random() * 3)
        delay = int(HOUR + R.random() * 11 * HOUR)
        ing[rows[-m:]] += delay
        anomaly(w, "late_arrival", "tail_events_after_watermark", "session", si, si,
                "keep events (use event_ts); flag late beyond 1 h watermark and restate metrics",
                severity="info", events_delayed=int(m), delay_ms=int(delay))
        used.add(si)
    # 3) duplicate conversions ---------------------------------------------------------
    et = np.array(ev.etype, dtype=np.int64)
    purchases = np.flatnonzero(et == EV["purchase"])
    n_dup = round(len(purchases) * cfg.duplicate_conversion_rate)
    dup_of = {}
    new_ing = []
    picks = sorted(R.sample(list(purchases), min(n_dup, len(purchases))))
    tsv = np.array(ev.ts, dtype=np.int64)
    for e in picks:
        e = int(e)
        si = int(ev.sess[e])
        s = w.sessions[si]
        u = R.random()
        subtype = "sdk_retry_same_client_event_id" if u < .45 else "page_reload_new_client_event_id" if u < .85 \
            else "refire_in_later_session"
        target_si, t, cust = si, int(tsv[e]), int(ev.cust[e])
        conf_page = sim.page(s["channel"], "confirmation")
        if subtype == "refire_in_later_session":
            later = sorted((w.sessions[j]["start"], j) for j in sim.device_sessions.get(s["device"], [])
                           if w.sessions[j]["start"] > t and w.sessions[j]["start"] - t < 7 * DAY
                           and w.sessions[j]["kind"] == "human")
            if later:
                target_si = later[0][1]
                t = later[0][0] + int(1 * SEC + R.random() * 19 * SEC)
                rows = sess_rows[target_si]
                cust = int(ev.cust[int(rows[0])])
            else:
                subtype = "page_reload_new_client_event_id"
        if subtype == "sdk_retry_same_client_event_id":
            arr = int(ing[e]) + int(5 * SEC + R.random() * 10 * MIN)
        else:
            if subtype == "page_reload_new_client_event_id":
                t = t + int(3 * SEC + R.random() * 87 * SEC)
            arr = t + int(700 + R.random() * 2000)
        idx = ev.add(target_si, EV["purchase"], t, page=conf_page, cart=int(ev.cart[e]), order=int(ev.order[e]),
                     cust=cust, value=float(ev.value[e]))
        new_ing.append(arr)
        dup_of[idx] = (e, subtype)
        anomaly(w, "duplicate_conversion", subtype, "journey_event", idx, target_si,
                "drop duplicate; count conversion once per order_id (first occurrence)",
                related_ref=e, order_ref=int(ev.order[e]))
    ing = np.concatenate([ing, np.array(new_ing, dtype=np.int64)])
    return ing, dup_of


def inject_bogus_links(sim: Simulator):
    R, w, cfg = sim.R, sim.w, sim.cfg
    linked = {}
    for ln in w.links:
        linked.setdefault(ln["device_idx"], []).append(ln)
    devs_with_sessions = [d for d in sorted(sim.device_sessions) if
                          any(w.sessions[j]["kind"] == "human" for j in sim.device_sessions[d])]
    n = round(len(devs_with_sessions) * cfg.bogus_link_device_rate)
    anon = [d for d in devs_with_sessions if not w.devices[d]["owners"] and d not in linked]
    conflict = [d for d in devs_with_sessions if len(w.devices[d]["owners"]) == 1 and
                any(l["link_method"] == "login" for l in linked.get(d, []))]
    picks = [("anonymous_device_to_customer", d) for d in R.sample(anon, min(len(anon), round(n * .6)))]
    picks += [("conflicting_customer_link", d) for d in R.sample(conflict, min(len(conflict), n - len(picks)))]
    n_c = len(w.customers)
    for subtype, d in sorted(picks, key=lambda x: x[1]):
        owners = w.devices[d]["owners"]
        while True:
            wrong = int(R.random() * n_c)
            if wrong not in owners:
                break
        human_sess = [j for j in sim.device_sessions[d] if w.sessions[j]["kind"] == "human"]
        at = w.sessions[human_sess[int(R.random() * len(human_sess))]]["start"]
        at = max(at, w.customers[wrong]["created_at"])
        method, src = (("probabilistic_match", "identity_graph") if R.random() < .7 else ("cookie_sync", "cdp_sync"))
        w.links.append(dict(device_idx=d, customer_idx=wrong, link_method=method,
                            confidence=round(.55 + R.random() * .40, 3), valid_from=at, valid_to=None,
                            source_system=src, _bogus=True))
        anomaly(w, "incorrect_identity_merge", subtype, "identity_link", len(w.links) - 1, None,
                "reject link; do not stitch device events to this customer", device_ref=d,
                wrong_customer_ref=wrong, true_owner_refs=list(owners))


def inject_all(sim: Simulator):
    rng = np.random.default_rng(sim.cfg.seed + 1)
    inject_bots(sim)
    inject_bogus_links(sim)
    ing, order = baseline_ingestion(sim, rng)
    ing, dup_of = inject_event_anomalies(sim, ing, order)
    return ing, dup_of
