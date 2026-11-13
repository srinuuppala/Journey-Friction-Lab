# Data dictionary

Generated from `journeylab/schema.py` (single source of truth). All timestamps are ISO-8601 UTC (`YYYY-MM-DDTHH:MM:SS.mmmZ`). Money is USD with 2 decimals.

## Entity overview

| Table | Kind | Grain | Primary key |
|---|---|---|---|
| `customer` | master | one row per customer | `customer_id` |
| `consent_event` | history | one row per consent decision | `consent_event_id` |
| `device` | master | one row per device that produced >=1 session | `device_id` |
| `identity_link` | bridge | one row per (device, customer) link | `link_id` |
| `page` | master | one row per page template | `page_id` |
| `product` | master | one row per product | `product_id` |
| `experiment` | master | one row per experiment | `experiment_id` |
| `experiment_assignment` | bridge | one row per (experiment, session) | `experiment_id, session_id` |
| `session` | master | one row per session | `session_id` |
| `journey_event` | event | one row per collected event | `event_id` |
| `cart` | transaction | one row per cart | `cart_id` |
| `cart_item` | bridge | one row per product line in a cart | `cart_item_id` |
| `order` | transaction | one row per order | `order_id` |
| `order_line` | bridge | one row per order line | `order_line_id` |
| `support_ticket` | transaction | one row per ticket | `ticket_id` |
| `support_agent` | reference | one row per agent | `agent_id` |
| `status_history` | history | one row per state change | `status_history_id` |
| `event_taxonomy` | reference | one row per event type | `event_type` |
| `journey_outcome` | derived | one row per session | `outcome_id` |

## Relationships and cardinality

| Parent | Child | Cardinality | Optional? | Via |
|---|---|---|---|---|
| customer | consent_event | 1:N | customer may have none (consent unknown) | consent_event.customer_id |
| customer | device | N:M | yes | identity_link (bridge, effective-dated) |
| device | session | 1:N | phone-support sessions have no device | session.device_id |
| customer | session | 1:N | anonymous sessions have none | session.customer_id (authenticated) |
| session | journey_event | 1:N | — | journey_event.session_id |
| session | journey_outcome | 1:1 | — | journey_outcome.session_id |
| session | cart | 1:0..1 | yes | cart.session_id |
| cart | product | N:M | — | cart_item (bridge) |
| cart | order | 1:0..1 | only converted carts | order.cart_id (unique) |
| order | product | N:M | — | order_line (bridge) |
| customer | order | 1:N | guest orders have no customer | order.customer_id |
| support_ticket | session (support contacts) | 1:N | — | session.ticket_id |
| session (web/app) | support_ticket | 1:N | tickets may have no origin | support_ticket.origin_session_id |
| order | support_ticket | 1:N | yes | support_ticket.order_id |
| experiment | session | N:M | — | experiment_assignment (bridge) |
| page / product / cart / order / ticket | journey_event | 1:N | yes (by event type) | journey_event.*_id |
| cart/order/ticket/experiment/product | status_history | 1:N | — | status_history.entity_id (polymorphic) |

## Lifecycle state machines

- **cart**: ∅ → open, checkout_started → abandoned, checkout_started → converted, open → abandoned, open → checkout_started, open → converted
- **order**: ∅ → placed, delivered → refunded, paid → cancelled, paid → shipped, placed → paid, shipped → delivered
- **ticket**: ∅ → open, assigned → escalated, assigned → resolved, escalated → resolved, open → assigned, resolved → closed
- **experiment**: ∅ → draft, draft → running, running → completed, running → stopped
- **product**: ∅ → active, active → discontinued

## `customer`

Registered customer (pseudonymous). Current consent fields are derived from consent_event.

Primary key: `customer_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `customer_id` | string | Y |  |  | Y | regex `^CUS-\d{6}$` | Customer key |
| `created_at` | timestamp | Y |  |  |  | ISO-8601 UTC 'YYYY-MM-DDTHH:MM:SS.mmmZ' | Account creation time |
| `country` | string | Y | IN, US, GB, DE, AE, SG, AU, CA |  |  |  | Home country (ISO-3166 alpha-2) |
| `segment` | string | Y | new, regular, vip |  |  |  | Commercial segment |
| `signup_channel` | string | Y | web, app, store |  |  |  | Where the account was created |
| `email_hash` | string | Y |  |  | Y | regex `^sha256:[0-9a-f]{64}$` | Synthetic pseudonymous token (not derived from any real e-mail) |
| `analytics_consent_status` | string | Y | granted, denied, withdrawn, expired, unknown |  |  | = last consent_event(analytics) <= consent_status_as_of, else unknown | Derived: latest analytics consent action as of snapshot |
| `marketing_consent_status` | string | Y | granted, denied, withdrawn, expired, unknown |  |  |  | Derived: latest marketing consent action as of snapshot |
| `consent_status_as_of` | timestamp | Y |  |  |  |  | Snapshot time for derived status fields |
| `last_authenticated_at` | timestamp | N |  |  |  |  | Derived: last event of a session with this customer authenticated |
| `lifecycle_status` | string | Y | active, dormant, registered_no_activity |  |  |  | Derived: active (<=90d since last auth), dormant, registered_no_activity |

## `consent_event`

Append-only consent history (effective-dated). Never overwritten.

Primary key: `consent_event_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `consent_event_id` | string | Y |  |  | Y | regex `^CNS-\d{7}$` | Key |
| `customer_id` | string | Y |  |  |  | FK → `customer.customer_id` | Customer |
| `consent_type` | string | Y | analytics, marketing |  |  |  | Purpose |
| `action` | string | Y | granted, denied, withdrawn, expired |  |  |  | Decision |
| `effective_at` | timestamp | Y |  |  |  | >= customer.created_at | When the decision takes effect |
| `recorded_at` | timestamp | Y |  |  |  | >= effective_at | When the CMP recorded it |
| `source` | string | Y | signup_form, app_prompt, store_form, cookie_banner, preference_center, policy_update |  |  |  | Capture point |
| `policy_version` | string | Y | v1, v2 |  |  |  | Privacy policy version |

## `device`

Browser or app install. anonymous_id is the cookie/install identifier.

Primary key: `device_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `device_id` | string | Y |  |  | Y | regex `^DEV-\d{7}$` | Key |
| `anonymous_id` | string | Y |  |  | Y | regex `^ANO-[0-9a-f]{10}$` | Cookie / install id |
| `platform` | string | Y | web, app |  |  |  | web or app |
| `device_type` | string | Y | desktop, mobile, tablet |  |  |  | Form factor |
| `os` | string | Y |  |  |  |  | Operating system |
| `browser` | string | N |  |  |  | null iff platform = app | Browser (web only) |
| `first_seen_at` | timestamp | Y |  |  |  |  | Derived: first session start |
| `last_seen_at` | timestamp | Y |  |  |  | >= first_seen_at | Derived: last session end |

## `identity_link`

Bridge Customer N:M Device (identity graph). Effective-dated.

Primary key: `link_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `link_id` | string | Y |  |  | Y | regex `^IDL-\d{7}$` | Key |
| `device_id` | string | Y |  |  |  | FK → `device.device_id` | Device |
| `anonymous_id` | string | Y |  |  |  | = device.anonymous_id | Device anonymous id (denormalised) |
| `customer_id` | string | Y |  |  |  | FK → `customer.customer_id` | Customer |
| `link_method` | string | Y | login, email_click, probabilistic_match, cookie_sync |  |  |  | How the link was established |
| `confidence` | decimal | Y |  | 0-1 |  | 1.0 for login | Link confidence |
| `valid_from` | timestamp | Y |  |  |  | >= customer.created_at | Effective from |
| `valid_to` | timestamp | N |  |  |  |  | Effective to (null = open) |
| `source_system` | string | Y | auth_service, email_service, identity_graph, cdp_sync |  |  |  | Producer |
| `created_at` | timestamp | Y |  |  |  |  | Record creation |

## `page`

Page / screen template catalogue.

Primary key: `page_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `page_id` | string | Y |  |  | Y | regex `^PAG-\d{4}$` | Key |
| `channel` | string | Y | web, app |  |  |  | web or app |
| `page_type` | string | Y | home, category, search, product, cart, checkout_shipping, checkout_payment, confirmation, help, login |  |  |  | Template type |
| `path` | string | Y |  |  |  |  | URL path or screen name |
| `category` | string | N | electronics, home_kitchen, fashion, beauty, sports, books, toys, grocery |  |  |  | Category for category pages |
| `help_topic` | string | N | payments, delivery, returns, account, orders |  |  |  | Topic for help pages |
| `funnel_stage` | integer | Y | 0, 1, 2, 3, 4, 5, 6 |  |  |  | Funnel stage the page belongs to (0 = none) |
| `is_active` | boolean | Y |  |  |  |  | Template live |
| `created_at` | timestamp | Y |  |  |  |  | Template creation |

## `product`

Sellable product.

Primary key: `product_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `product_id` | string | Y |  |  | Y | regex `^PRD-\d{6}$` | Key |
| `name` | string | Y |  |  |  |  | Display name (synthetic) |
| `brand` | string | Y |  |  |  |  | Brand (synthetic) |
| `category` | string | Y | electronics, home_kitchen, fashion, beauty, sports, books, toys, grocery |  |  |  | Category |
| `list_price` | decimal | Y |  | USD |  | > 0 | Price |
| `currency` | string | Y | USD |  |  |  | Currency |
| `launched_at` | timestamp | Y |  |  |  |  | Effective from |
| `discontinued_at` | timestamp | N |  |  |  | > launched_at | Effective to |
| `lifecycle_status` | string | Y | active, discontinued |  |  |  | Derived as of snapshot |

## `experiment`

A/B experiment definition.

Primary key: `experiment_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `experiment_id` | string | Y |  |  | Y | regex `^EXP-2026-\d{6}$` | Key |
| `name` | string | Y |  |  | Y |  | Name |
| `hypothesis` | string | Y |  |  |  |  | Hypothesis |
| `channel` | string | Y | web, app, all |  |  |  | Eligible channel |
| `target_step` | string | Y | checkout_shipping, product, cart, search, home |  |  |  | Funnel step targeted |
| `status` | string | Y | draft, running, completed, stopped |  |  |  | Lifecycle state |
| `allocation_treatment` | decimal | Y |  | 0-1 |  |  | Share to treatment |
| `assignment_unit` | string | Y | device |  |  |  | Randomisation unit |
| `owner_team` | string | Y |  |  |  |  | Owning team |
| `created_at` | timestamp | Y |  |  |  |  | Definition created |
| `start_at` | timestamp | Y |  |  |  | >= created_at | Effective from |
| `end_at` | timestamp | Y |  |  |  | > start_at | Effective to (exclusive) |

## `experiment_assignment`

Bridge Experiment N:M Session (sticky per device).

Primary key: `experiment_id, session_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `experiment_id` | string | Y |  |  |  | FK → `experiment.experiment_id` | Experiment |
| `session_id` | string | Y |  |  |  | FK → `session.session_id` | Session |
| `variant` | string | Y | control, treatment |  |  |  | Arm |
| `assigned_at` | timestamp | Y |  |  |  | within [experiment.start_at, end_at) | = session start |
| `assignment_unit` | string | Y | device |  |  |  | Unit |
| `device_id` | string | Y |  |  |  | FK → `device.device_id`; same variant for all sessions of a device | Device (unit) |

## `session`

Collector session. Web/app: 30-min inactivity rule per (device, channel). Support: one CRM contact.

Primary key: `session_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `session_id` | string | Y |  |  | Y | regex `^SES-2026-\d{6}$` | Key |
| `channel` | string | Y | web, app, support |  |  |  | Channel |
| `device_id` | string | N |  |  |  | FK → `device.device_id` | Device (null for phone support) |
| `anonymous_id` | string | N |  |  |  | = device.anonymous_id | Device anonymous id |
| `customer_id` | string | N |  |  |  | FK → `customer.customer_id` | Customer authenticated in the session (raw; not consent-filtered) |
| `session_start_ts` | timestamp | Y |  |  |  |  | Derived: min(event_ts) |
| `session_end_ts` | timestamp | Y |  |  |  | >= session_start_ts | Derived: max(event_ts) |
| `duration_s` | decimal | Y |  | seconds |  | = end - start | Derived |
| `event_count` | integer | Y |  |  |  | = count(journey_event) | Derived: raw events incl. duplicates |
| `traffic_source` | string | Y | direct, organic_search, paid_search, social, referral, email, push, deep_link, support |  |  | email/push only with marketing consent at session start | Acquisition source |
| `utm_campaign` | string | N |  |  |  | regex `^CMP-2026\d{2}-[A-Z]+$` | Campaign code |
| `landing_page_id` | string | N |  |  |  | FK → `page.page_id` | Page of the first event (web/app) |
| `user_agent` | string | N |  |  |  |  | User agent string |
| `ip_hash` | string | N |  |  |  |  | Salted IP hash (synthetic) |
| `geo_country` | string | N | IN, US, GB, DE, AE, SG, AU, CA |  |  |  | IP geolocation country |
| `app_version` | string | N | 5.0.0, 5.1.0, 5.1.3, 5.2.0, 5.2.1, 5.3.0 |  |  |  | App version (app only) |
| `support_medium` | string | N | chat, phone |  |  |  | Support only |
| `ticket_id` | string | N |  |  |  | FK → `support_ticket.ticket_id` | Support only |
| `sessionization_rule` | string | Y | web_app_inactivity_30m_v1, support_contact_v1 |  |  |  | Rule version |

## `journey_event`

Raw cross-channel event stream as delivered by collectors (includes labelled anomalies).

Primary key: `event_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `event_id` | string | Y |  |  | Y | regex `^EVT-SES-2026-\d{6}-\d{6}$`; counter follows ingestion order within the session | EVT-<session-id>-<arrival counter> |
| `session_id` | string | Y |  |  |  | FK → `session.session_id`; event_id prefix = session_id | Session |
| `event_type` | string | Y | session_start, page_view, screen_view, scroll, click, search, product_view, add_to_cart, add_to_cart_failed, remove_f… |  |  | FK → `event_taxonomy.event_type` | Taxonomy event |
| `event_ts` | timestamp | Y |  |  |  |  | Occurrence time (client/device clock) |
| `ingestion_ts` | timestamp | Y |  |  |  | >= event_ts | Collector arrival time |
| `channel` | string | Y | web, app, support |  |  | = session.channel | Channel |
| `source_system` | string | Y | web_sdk, app_sdk, support_crm |  |  |  | Producer |
| `device_id` | string | N |  |  |  | FK → `device.device_id` | Device |
| `anonymous_id` | string | N |  |  |  |  | Device anonymous id |
| `customer_id` | string | N |  |  |  | FK → `customer.customer_id` | Authenticated customer at event time (raw) |
| `auth_state` | string | Y | anonymous, authenticated, agent_verified, unverified |  |  |  | Auth state |
| `page_id` | string | N |  |  |  | FK → `page.page_id` | Page/screen |
| `product_id` | string | N |  |  |  | FK → `product.product_id`; product active at event_ts | Product |
| `cart_id` | string | N |  |  |  | FK → `cart.cart_id` | Cart |
| `order_id` | string | N |  |  |  | FK → `order.order_id` | Order (purchase only) |
| `ticket_id` | string | N |  |  |  | FK → `support_ticket.ticket_id` | Ticket (support only) |
| `client_event_id` | string | Y |  |  |  | regex `^ce-[0-9a-f]{16}$` | SDK idempotency key (dedup key) |
| `page_load_ms` | integer | N |  | ms |  |  | Render latency (view events) |
| `http_status` | integer | N |  |  |  |  | HTTP status for error events |
| `error_code` | string | N | PAY_GATEWAY_TIMEOUT, PAY_DECLINED, PAY_3DS_FAILED, ADDR_VALIDATION_FAILED, CART_API_500, HTTP_503, AUTH_INVALID_CREDE… |  |  |  | Error code |
| `quantity` | integer | N |  | units |  |  | Units (cart events) |
| `value` | decimal | N |  |  |  | purchase value = order.total | Monetary value (cart/purchase, USD) or CSAT score (csat_submitted) |

## `cart`

Shopping cart (one per session at most).

Primary key: `cart_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `cart_id` | string | Y |  |  | Y | regex `^CRT-2026-\d{6}$` | Key |
| `session_id` | string | Y |  |  |  | FK → `session.session_id` | Session |
| `customer_id` | string | N |  |  |  | FK → `customer.customer_id` | Authenticated customer |
| `anonymous_id` | string | N |  |  |  |  | Device anonymous id |
| `created_at` | timestamp | Y |  |  |  |  | First add_to_cart |
| `checkout_started_at` | timestamp | N |  |  |  | >= created_at | First checkout_start |
| `status` | string | Y | open, checkout_started, converted, abandoned |  |  |  | Current status (= last status_history row) |
| `status_at` | timestamp | Y |  |  |  |  | Time of current status |
| `item_count` | integer | Y |  | units |  |  | Derived: sum(quantity) of active items |
| `subtotal` | decimal | Y |  | USD |  |  | Derived: sum(line_amount) of active items |

## `cart_item`

Bridge Cart N:M Product.

Primary key: `cart_item_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `cart_item_id` | string | Y |  |  | Y | regex `^CIT-CRT-2026-\d{6}-\d{2}$` | Key |
| `cart_id` | string | Y |  |  |  | FK → `cart.cart_id` | Cart |
| `product_id` | string | Y |  |  |  | FK → `product.product_id` | Product |
| `quantity` | integer | Y |  | units |  | = sum(add_to_cart.quantity) for the line | Units |
| `unit_price` | decimal | Y |  | USD |  | = product.list_price | Price at add time |
| `line_amount` | decimal | Y |  | USD |  |  | Derived quantity*unit_price |
| `added_at` | timestamp | Y |  |  |  |  | First add |
| `removed_at` | timestamp | N |  |  |  | >= added_at | Removal time (null = active) |
| `is_active` | boolean | Y |  |  |  |  | removed_at is null |

## `order`

Placed order (1:1 with converted cart). Guest orders have null customer_id.

Primary key: `order_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `order_id` | string | Y |  |  | Y | regex `^ORD-2026-\d{6}$` | Key |
| `cart_id` | string | Y |  |  | Y | FK → `cart.cart_id` | Cart |
| `session_id` | string | Y |  |  |  | FK → `session.session_id` | Session where placed |
| `customer_id` | string | N |  |  |  | FK → `customer.customer_id` | Customer (null = guest) |
| `order_ts` | timestamp | Y |  |  |  |  | Placement time |
| `status` | string | Y | placed, paid, shipped, delivered, cancelled, refunded |  |  |  | Current status (= last status_history row) |
| `status_at` | timestamp | Y |  |  |  |  | Time of current status |
| `ship_country` | string | Y | IN, US, GB, DE, AE, SG, AU, CA |  |  |  | Destination |
| `currency` | string | Y | USD |  |  |  | Currency |
| `payment_method` | string | Y | card, wallet, bnpl, upi |  |  |  | Method |
| `item_count` | integer | Y |  | units |  |  | Derived sum(order_line.quantity) |
| `subtotal` | decimal | Y |  | USD |  |  | Derived sum(order_line.line_amount) |
| `discount` | decimal | Y |  | USD |  |  | Coupon discount (10% when applied) |
| `tax` | decimal | Y |  | USD |  |  | round((subtotal-discount)*country rate, 2) |
| `shipping_fee` | decimal | Y |  | USD |  |  | 0 if (subtotal-discount)>=50 else 4.99 |
| `total` | decimal | Y |  | USD |  |  | subtotal-discount+tax+shipping_fee |

## `order_line`

Bridge Order N:M Product.

Primary key: `order_line_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `order_line_id` | string | Y |  |  | Y | regex `^OLN-ORD-2026-\d{6}-\d{2}$` | Key |
| `order_id` | string | Y |  |  |  | FK → `order.order_id` | Order |
| `line_no` | integer | Y |  |  |  |  | Line number (1..n) |
| `product_id` | string | Y |  |  |  | FK → `product.product_id` | Product |
| `quantity` | integer | Y |  | units |  |  | Units |
| `unit_price` | decimal | Y |  | USD |  |  | Price |
| `line_amount` | decimal | Y |  | USD |  |  | quantity*unit_price |

## `support_ticket`

Support case. Contacts are sessions with channel=support.

Primary key: `ticket_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `ticket_id` | string | Y |  |  | Y | regex `^TCK-2026-\d{6}$` | Key |
| `customer_id` | string | N |  |  |  | FK → `customer.customer_id` | Verified customer (null = guest) |
| `origin_session_id` | string | N |  |  |  | FK → `session.session_id` | Web/app session that led to the contact |
| `first_contact_session_id` | string | Y |  |  |  | FK → `session.session_id` | First support session |
| `order_id` | string | N |  |  |  | FK → `order.order_id` | Related order |
| `medium` | string | Y | chat, phone |  |  |  | Contact medium |
| `category` | string | Y | payment_issue, checkout_issue, technical_issue, product_question, account_access, delivery_issue, refund_request |  |  |  | Reason |
| `priority` | string | Y | high, medium, low |  |  |  | Priority (rule: payment/refund=high) |
| `status` | string | Y | open, assigned, escalated, resolved, closed |  |  |  | Current status (= last status_history row) |
| `opened_at` | timestamp | Y |  |  |  |  | Opened |
| `first_response_at` | timestamp | N |  |  |  | >= opened_at | Agent assigned |
| `escalated_at` | timestamp | N |  |  |  | >= first_response_at | Escalated |
| `resolved_at` | timestamp | N |  |  |  | >= first_response_at | Resolved |
| `closed_at` | timestamp | N |  |  |  | >= resolved_at | Closed (resolved + 2 days) |
| `agent_id` | string | N |  |  |  | FK → `support_agent.agent_id` | Owning agent |
| `csat_score` | integer | N | 1, 2, 3, 4, 5 |  |  |  | 1-5 survey score |

## `support_agent`

Support agent reference.

Primary key: `agent_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `agent_id` | string | Y |  |  | Y | regex `^AGT-\d{4}$` | Key |
| `tier` | integer | Y | 1, 2 |  |  |  | Tier |
| `team` | string | Y | payments, orders, general |  |  |  | Team |
| `site` | string | Y |  |  |  |  | Site |
| `hired_at` | timestamp | Y |  |  |  |  | Hire date |

## `status_history`

Append-only lifecycle transitions for cart, order, ticket, experiment, product.

Primary key: `status_history_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `status_history_id` | string | Y |  |  | Y | regex `^STH-\d{8}$` | Key |
| `entity_type` | string | Y | cart, order, ticket, experiment, product |  |  |  | Entity |
| `entity_id` | string | Y |  |  |  |  | Entity key (polymorphic FK) |
| `from_status` | string | N |  |  |  |  | Previous state (null = creation) |
| `to_status` | string | Y |  |  |  | (from,to) in allowed lifecycle | New state |
| `changed_at` | timestamp | Y |  |  |  | non-decreasing per entity; <= snapshot | Effective time |
| `changed_by` | string | Y | system, customer, support_agent, carrier, analyst, admin |  |  |  | Actor |

## `event_taxonomy`

Event type contract.

Primary key: `event_type`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `event_type` | string | Y | session_start, page_view, screen_view, scroll, click, search, product_view, add_to_cart, add_to_cart_failed, remove_f… |  | Y |  | Key |
| `category` | string | Y | navigation, engagement, commerce, system, identity, support |  |  |  | Category |
| `funnel_stage` | integer | Y | 0, 1, 2, 3, 4, 5, 6 |  |  |  | Funnel stage reached (0 = none) |
| `funnel_stage_name` | string | N | visit, product_view, add_to_cart, checkout_start, payment_submitted, purchase |  |  |  | Stage name |
| `allowed_channels` | string | Y |  |  |  |  | Pipe-separated channels |
| `required_refs` | string | N |  |  |  |  | Pipe-separated required reference columns |
| `description` | string | Y |  |  |  |  | Meaning |

## `journey_outcome`

Derived per-session outcome (pipeline rules R1-R8 on deduplicated, resequenced events).

Primary key: `outcome_id`

| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |
|---|---|---|---|---|---|---|---|
| `outcome_id` | string | Y |  |  | Y | regex `^OUT-SES-2026-\d{6}$` | OUT-<session-id> |
| `session_id` | string | Y |  |  | Y | FK → `session.session_id` | Session (1:1) |
| `outcome_type` | string | Y | converted, support_resolved, support_unresolved, abandoned_checkout, abandoned_cart, bounced, browsed_product, browse… |  |  |  | Outcome |
| `rule_id` | string | Y | R1, R2, R3, R4, R5, R6, R7, R8 |  |  |  | Rule fired |
| `furthest_stage` | integer | Y | 0, 1, 2, 3, 4, 5, 6 |  |  |  | Max funnel stage reached |
| `furthest_stage_name` | string | Y |  |  |  |  | Stage name |
| `drop_off_before_stage` | string | N |  |  |  |  | Next stage not reached (null for converted/support) |
| `converted` | boolean | Y |  |  |  |  | outcome_type = converted |
| `order_id` | string | N |  |  |  | FK → `order.order_id` | First valid purchase order |
| `cart_id` | string | N |  |  |  | FK → `cart.cart_id` | Cart touched |
| `ticket_id` | string | N |  |  |  | FK → `support_ticket.ticket_id` | Ticket (support sessions) |
| `friction_event_count` | integer | Y |  |  |  |  | Count of friction events |
| `support_contact_flag` | boolean | Y |  |  |  |  | contact_support_click or support channel |
| `valid_event_count` | integer | Y |  |  |  | <= session.event_count | Events after dedup |
| `first_event_ts` | timestamp | Y |  |  |  |  | First valid event |
| `last_event_ts` | timestamp | Y |  |  |  |  | Last valid event |
| `duration_s` | decimal | Y |  | seconds |  |  | Duration |
| `derivation_version` | string | Y |  |  |  |  | Rule set version |
