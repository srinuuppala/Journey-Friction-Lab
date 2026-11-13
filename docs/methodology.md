# Methodology: definitions, rules and generation logic

This document is the contract behind the data. Every rule below is implemented once in code
(`journeylab/taxonomy.py`, `simulate.py`, `inject.py`, `pipeline.py`) and checked by `validate.py` / the tests.

## 1. Event taxonomy

Every event in `journey_event` has an `event_type` from this list (also shipped as the `event_taxonomy` table).
`required refs` must be non-null for that event type (validated).

| event_type | category | funnel stage | channels | required refs | meaning |
|---|---|---|---|---|---|
| `session_start` | navigation | 1 (visit) | web, app | page_id | First event of a web/app session (collector-generated) |
| `page_view` | navigation | — | web | page_id | Web page rendered |
| `screen_view` | navigation | — | app | page_id | App screen rendered |
| `scroll` | engagement | — | web, app | page_id | Scroll depth milestone reached |
| `click` | engagement | — | web, app | page_id | Tracked UI click |
| `search` | navigation | — | web, app | page_id | Search query submitted |
| `product_view` | commerce | 2 (product_view) | web, app | page_id, product_id | Product detail viewed |
| `add_to_cart` | commerce | 3 (add_to_cart) | web, app | page_id, product_id, cart_id | Item added to cart |
| `add_to_cart_failed` | system | — | web, app | page_id, product_id | Add-to-cart API failure |
| `remove_from_cart` | commerce | — | web, app | page_id, product_id, cart_id | Item removed from cart |
| `cart_view` | commerce | — | web, app | page_id, cart_id | Cart opened |
| `checkout_start` | commerce | 4 (checkout_start) | web, app | page_id, cart_id | Checkout initiated from cart |
| `shipping_info_submitted` | commerce | — | web, app | page_id, cart_id | Shipping step submitted OK |
| `shipping_validation_error` | system | — | web, app | page_id, cart_id | Shipping step rejected by validator |
| `payment_info_submitted` | commerce | 5 (payment_submitted) | web, app | page_id, cart_id | Payment details submitted |
| `payment_error` | system | — | web, app | page_id, cart_id | Payment attempt failed |
| `purchase` | commerce | 6 (purchase) | web, app | page_id, cart_id, order_id | Order placed (conversion) |
| `login` | identity | — | web, app | customer_id | Customer authenticated |
| `login_failed` | identity | — | web, app | — | Authentication attempt failed |
| `help_view` | support | — | web, app | page_id | Help article viewed |
| `contact_support_click` | support | — | web, app | page_id | Contact-support CTA clicked |
| `page_error` | system | — | web, app | page_id | Page failed to render (HTTP 5xx) |
| `ticket_created` | support | — | support | ticket_id | Support ticket opened (CRM) |
| `agent_assigned` | support | — | support | ticket_id | Agent picked up the contact |
| `message_customer` | support | — | support | ticket_id | Customer message |
| `message_agent` | support | — | support | ticket_id | Agent message |
| `ticket_escalated` | support | — | support | ticket_id | Escalated to tier-2 |
| `ticket_resolved` | support | — | support | ticket_id | Ticket marked resolved |
| `csat_submitted` | support | — | support | ticket_id | Customer satisfaction survey answered |

**Two timestamps on every event.** `event_ts` is when it happened (device/CRM clock); `ingestion_ts` is when the
collector received it (`ingestion_ts >= event_ts`, validated). The numeric suffix of `event_id`
(`EVT-<session-id>-000001`) is the **arrival counter**, i.e. collector order. **Analysis must order by `event_ts`**,
never by `event_id` or `ingestion_ts`. Late or offline-buffered events make the two orders disagree; that is one
of the labelled edge cases.

**Dedup key.** `client_event_id` is the SDK idempotency key. A retried send keeps the same key.

## 2. Sessionization

| Channel | Rule (`session.sessionization_rule`) |
|---|---|
| web, app | `web_app_inactivity_30m_v1`: a session is a run of events on one `(device_id, channel)` whose consecutive `event_ts` gaps are at most 30 minutes. A 30-minute inactivity gap (or 4 h maximum length) closes the session. |
| support | `support_contact_v1`: one CRM contact (chat or phone) for one ticket. An escalated ticket gets a follow-up contact, which is a new support session with the same `ticket_id`. The inactivity rule does not apply. |

The generator guarantees the rule. No web/app session has an internal gap over 30 minutes, and sessions on the
same device are more than 30 minutes apart (both validated). Boundary cases with 20–30 minute idle gaps are
generated on purpose. Pipeline step **P3** re-derives sessions from raw events and gets a 100% match when it
uses `event_ts`. If it wrongly uses `ingestion_ts`, about 2.5% of sessions split or merge. Those are exactly
the labelled late/out-of-order sessions.

## 3. Funnel stages

A session's **furthest stage** is the maximum stage of any *deduplicated* event in it.

| # | Stage | Reached when the session contains |
|---|---|---|
| 1 | `visit` | `session_start` |
| 2 | `product_view` | `product_view` |
| 3 | `add_to_cart` | `add_to_cart` |
| 4 | `checkout_start` | `checkout_start` |
| 5 | `payment_submitted` | `payment_info_submitted` |
| 6 | `purchase` | `purchase` (unique `order_id`) |

Funnel metrics (`derived/funnel_metrics.csv`) exclude support sessions and **detected** bots. They are cut
by overall, channel, month, traffic source and channel×month. `step_conversion = reached_k / reached_(k-1)`,
`drop_off_rate = 1 - step_conversion`, and `cumulative_conversion = reached_k / visits`.
`drop_off_before_stage` in `journey_outcome` names the first stage a non-converting session did not reach.

## 4. Outcome rules (JourneyOutcome, `OUT-<session-id>`)

Rules are evaluated in priority order on deduplicated, `event_ts`-ordered events. The first match wins.

| Rule | outcome_type | Condition |
|---|---|---|
| R1 | `converted` | at least one valid `purchase` (first occurrence of its `order_id`) |
| R2 | `support_resolved` | support session containing `ticket_resolved` |
| R3 | `support_unresolved` | support session without `ticket_resolved` (escalated or pending) |
| R4 | `abandoned_checkout` | furthest stage ≥ 4 without purchase |
| R5 | `abandoned_cart` | furthest stage = 3 |
| R6 | `bounced` | ≤ 1 page/screen view and duration < 10 s |
| R7 | `browsed_product` | furthest stage = 2 |
| R8 | `browsed_no_product` | anything else |

Ground-truth `expected_outcome` applies the same rules to the **pre-injection** events. The pipeline must
reproduce it from the dirty raw stream, and it does so at 100% accuracy.

## 5. Deduplication (pipeline P1)

* **D1**: rows with the same `client_event_id` keep the earliest arrival (`ingestion_ts`, then `event_id`). This removes SDK retries.
* **D2**: `purchase` events are unique per `order_id` *globally*. The first by `event_ts` is kept. This removes page-reload double fires and re-fires in a later session.
* Every dropped row is listed in `derived/dedup_decisions.csv` with the kept event.
* After dedup, conversions equal the number of orders (validated: *"deduplicated conversions = orders"*).

## 6. Identity and consent

* **Raw identifiers.** `journey_event.customer_id` / `session.customer_id` hold the customer *authenticated* at
  the time (an operational fact, restricted-zone data). They are **not** consent-filtered.
* **Identity graph.** `identity_link` (Customer N:M Device) records how each link was made:
  * `login` (deterministic, confidence 1.0)
  * `email_click` (deterministic token)
  * `probabilistic_match` / `cookie_sync` (heuristic)
* **Link review (P5).** Deterministic links are accepted. A heuristic link is rejected when it:
  * conflicts with a deterministic link to another customer (L1)
  * is one of several heuristic candidates (L2)
  * has confidence < 0.70 (L3)
  * has a device home geography (modal geo of non-bot sessions) that differs from the customer country (L4)

  Devices with deterministic links to two or more customers are **shared** (household) and get no device-level stitching.
* **Stitching (P6), event level, in order:**
  * R-ID-1: authenticated event → its customer.
  * R-ID-2: unauthenticated event in a session with exactly one authenticated customer.
  * R-ID-3: accepted link on an unshared device with `valid_from <= event_ts`.
* **Consent gate.** A candidate is kept only if the customer's latest *analytics* consent action at or before
  `event_ts` is `granted` (`consent_event` is an effective-dated, append-only history). Customers with no
  record are `unknown` and are treated as not consented. Withdrawn, denied and expired (policy v2 re-consent)
  periods block stitching. Detected bot sessions are never stitched.
* **Result.** 0 consent violations (tested). A naive "accept every link, ignore consent" approach would
  attach ~230k events at full scale to people who had not consented.

## 7. Generation logic (what makes the data realistic)

1. **Master data first:** customers (segment, country, signup channel), consent history, devices (1–4 per
   customer, about 2% shared by households, plus anonymous-only devices), products (Zipf popularity,
   category-specific lognormal prices, launch and discontinue dates), pages, experiments, agents.
2. **Sessions:**
   * Start times follow a weekly pattern, a growth trend, three sale peaks and a local-time diurnal curve per country.
   * Each web/app session is a **state machine** over page types (home, category, search, product, cart,
     shipping, payment, confirmation, help, login).
   * Transition weights shift with channel, segment, experiment arm, latency and incidents. Dwell times are lognormal.
   * Scroll and click engagement events are Poisson.
3. **Dependent records** are created by the actions themselves:
   * Carts and cart items come from `add_to_cart`.
   * Orders and lines come from a successful payment. Totals, tax, shipping and discount are computed from the lines.
   * The order lifecycle (`placed → paid → shipped → delivered` | `cancelled` | `refunded`) is written to `status_history`.
   * Support tickets come from a help-page contact, a payment failure or a post-order delivery/refund issue.
     The CRM conversation (ticket created, agent assigned, messages, resolved/escalated, CSAT) is generated
     as a support session.
4. **Cross-channel return journeys:** customers come back after abandonment, and after a resolved support
   contact. Return probability is 30% after an abandoned checkout and 12% after an abandoned cart. The return
   is often on another of the customer's devices or channels and continues the same product.
5. **Broken steps and latency** (ground truth in `expected_findings.json`, never in inputs):

| Incident | What breaks | Scope |
|---|---|---|
| INC-2026-001 | app payment gateway timeouts (45%) | app 5.2.0, 10 May – 21 Jun (fixed in 5.2.1) |
| INC-2026-002 | address validator rejects postcodes (45%) | web, geo DE+GB, 1 Aug – 5 Sep |
| INC-2026-003 | search page load ×6 → latency-driven exits | web, 5 – 26 Jul |
| INC-2026-004 | add-to-cart API 500 (50%) + rage clicks | app 5.1.x on Android 13, 15 Mar – 10 May |

6. **Experiments** are sticky per device (CRC32 hash of seed, device and experiment) and apply true multiplicative effects to
   one transition (also only in ground truth). One experiment is a null effect, one is a draft with no traffic.

## 8. Labelled edge cases (Step 5)

| issue_type | subtypes | How injected | Expected decision |
|---|---|---|---|
| `ingestion_order_inversion` | `offline_buffer_flush` (app), `beacon_retry` (web) | a block of 3–8 events arrives 20 min – 6 h late, so arrival order differs from occurrence order | order by `event_ts` |
| `late_arrival` | `tail_events_after_watermark` | last 1–3 events ingested 1–12 h late (no reordering) | keep; flag as late |
| `duplicate_conversion` | `sdk_retry_same_client_event_id`, `page_reload_new_client_event_id`, `refire_in_later_session` | an extra `purchase` row for an existing order | count once per `order_id` |
| `incorrect_identity_merge` | `anonymous_device_to_customer`, `conflicting_customer_link` | heuristic link from a device to the wrong customer | reject link |
| `bot_traffic` | `declared_crawler`, `disguised_scraper`, `stealth_scraper`, `cart_bot`, `cookie_replay` | bot sessions mixed into the same period. Cookie-replay bots reuse a real customer's device and authenticated cookie. Stealth scrapers use residential IPs and human-like pacing. | exclude from metrics; never stitch |

Every injected row is listed in `ground_truth/anomalies.csv`. Validation proves the reverse direction: every
irregularity found in the data (duplicate keys, multi-purchase orders, order inversions) is labelled.
