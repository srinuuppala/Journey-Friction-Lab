"""Single source of truth for every table: fields, types, keys, enums, rules.

Used to (1) validate generated data, (2) render docs/data_dictionary.md and
(3) emit SQL DDL with primary/foreign keys.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import COUNTRIES, CATEGORIES, HELP_TOPICS, APP_RELEASES
from .taxonomy import EVENT_NAMES, ERROR_CODES, OUTCOME_TYPES, STAGE_NAME

TS_RULE = "ISO-8601 UTC 'YYYY-MM-DDTHH:MM:SS.mmmZ'"


@dataclass
class F:
    name: str
    type: str                  # string|integer|decimal|boolean|timestamp|json
    required: bool
    desc: str
    allowed: tuple | None = None
    unit: str | None = None
    unique: bool = False
    pattern: str | None = None
    fk: str | None = None      # "table.column"
    rule: str | None = None


@dataclass
class Table:
    name: str
    desc: str
    pk: tuple
    fields: list
    kind: str = "transaction"   # master|transaction|event|bridge|history|reference|derived
    grain: str = ""


COUNTRY = tuple(COUNTRIES)
CHANNEL = ("web", "app", "support")
CART_STATUS = ("open", "checkout_started", "converted", "abandoned")
ORDER_STATUS = ("placed", "paid", "shipped", "delivered", "cancelled", "refunded")
TICKET_STATUS = ("open", "assigned", "escalated", "resolved", "closed")
EXP_STATUS = ("draft", "running", "completed", "stopped")
CONSENT_STATUS = ("granted", "denied", "withdrawn", "expired", "unknown")

LIFECYCLES = {  # entity_type -> allowed (from, to) transitions; None = creation
    "cart": {(None, "open"), ("open", "checkout_started"), ("open", "converted"), ("open", "abandoned"),
             ("checkout_started", "converted"), ("checkout_started", "abandoned")},
    "order": {(None, "placed"), ("placed", "paid"), ("paid", "shipped"), ("paid", "cancelled"),
              ("shipped", "delivered"), ("delivered", "refunded")},
    "ticket": {(None, "open"), ("open", "assigned"), ("assigned", "resolved"), ("assigned", "escalated"),
               ("escalated", "resolved"), ("resolved", "closed")},
    "experiment": {(None, "draft"), ("draft", "running"), ("running", "completed"), ("running", "stopped")},
    "product": {(None, "active"), ("active", "discontinued")},
}

TABLES = [
    Table("customer", "Registered customer (pseudonymous). Current consent fields are derived from consent_event.",
          ("customer_id",), kind="master", grain="one row per customer", fields=[
              F("customer_id", "string", True, "Customer key", unique=True, pattern=r"^CUS-\d{6}$"),
              F("created_at", "timestamp", True, "Account creation time", rule=TS_RULE),
              F("country", "string", True, "Home country (ISO-3166 alpha-2)", allowed=COUNTRY),
              F("segment", "string", True, "Commercial segment", allowed=("new", "regular", "vip")),
              F("signup_channel", "string", True, "Where the account was created", allowed=("web", "app", "store")),
              F("email_hash", "string", True, "Synthetic pseudonymous token (not derived from any real e-mail)",
                unique=True, pattern=r"^sha256:[0-9a-f]{64}$"),
              F("analytics_consent_status", "string", True, "Derived: latest analytics consent action as of snapshot",
                allowed=CONSENT_STATUS, rule="= last consent_event(analytics) <= consent_status_as_of, else unknown"),
              F("marketing_consent_status", "string", True, "Derived: latest marketing consent action as of snapshot",
                allowed=CONSENT_STATUS),
              F("consent_status_as_of", "timestamp", True, "Snapshot time for derived status fields"),
              F("last_authenticated_at", "timestamp", False, "Derived: last event of a session with this customer authenticated"),
              F("lifecycle_status", "string", True, "Derived: active (<=90d since last auth), dormant, registered_no_activity",
                allowed=("active", "dormant", "registered_no_activity")),
          ]),
    Table("consent_event", "Append-only consent history (effective-dated). Never overwritten.",
          ("consent_event_id",), kind="history", grain="one row per consent decision", fields=[
              F("consent_event_id", "string", True, "Key", unique=True, pattern=r"^CNS-\d{7}$"),
              F("customer_id", "string", True, "Customer", fk="customer.customer_id"),
              F("consent_type", "string", True, "Purpose", allowed=("analytics", "marketing")),
              F("action", "string", True, "Decision", allowed=("granted", "denied", "withdrawn", "expired")),
              F("effective_at", "timestamp", True, "When the decision takes effect", rule=">= customer.created_at"),
              F("recorded_at", "timestamp", True, "When the CMP recorded it", rule=">= effective_at"),
              F("source", "string", True, "Capture point", allowed=("signup_form", "app_prompt", "store_form", "cookie_banner",
                                                                      "preference_center", "policy_update")),
              F("policy_version", "string", True, "Privacy policy version", allowed=("v1", "v2")),
          ]),
    Table("device", "Browser or app install. anonymous_id is the cookie/install identifier.",
          ("device_id",), kind="master", grain="one row per device that produced >=1 session", fields=[
              F("device_id", "string", True, "Key", unique=True, pattern=r"^DEV-\d{7}$"),
              F("anonymous_id", "string", True, "Cookie / install id", unique=True, pattern=r"^ANO-[0-9a-f]{10}$"),
              F("platform", "string", True, "web or app", allowed=("web", "app")),
              F("device_type", "string", True, "Form factor", allowed=("desktop", "mobile", "tablet")),
              F("os", "string", True, "Operating system"),
              F("browser", "string", False, "Browser (web only)", rule="null iff platform = app"),
              F("first_seen_at", "timestamp", True, "Derived: first session start"),
              F("last_seen_at", "timestamp", True, "Derived: last session end", rule=">= first_seen_at"),
          ]),
    Table("identity_link", "Bridge Customer N:M Device (identity graph). Effective-dated.",
          ("link_id",), kind="bridge", grain="one row per (device, customer) link", fields=[
              F("link_id", "string", True, "Key", unique=True, pattern=r"^IDL-\d{7}$"),
              F("device_id", "string", True, "Device", fk="device.device_id"),
              F("anonymous_id", "string", True, "Device anonymous id (denormalised)", rule="= device.anonymous_id"),
              F("customer_id", "string", True, "Customer", fk="customer.customer_id"),
              F("link_method", "string", True, "How the link was established",
                allowed=("login", "email_click", "probabilistic_match", "cookie_sync")),
              F("confidence", "decimal", True, "Link confidence", unit="0-1", rule="1.0 for login"),
              F("valid_from", "timestamp", True, "Effective from", rule=">= customer.created_at"),
              F("valid_to", "timestamp", False, "Effective to (null = open)"),
              F("source_system", "string", True, "Producer", allowed=("auth_service", "email_service", "identity_graph", "cdp_sync")),
              F("created_at", "timestamp", True, "Record creation"),
          ]),
    Table("page", "Page / screen template catalogue.", ("page_id",), kind="master", grain="one row per page template", fields=[
        F("page_id", "string", True, "Key", unique=True, pattern=r"^PAG-\d{4}$"),
        F("channel", "string", True, "web or app", allowed=("web", "app")),
        F("page_type", "string", True, "Template type", allowed=("home", "category", "search", "product", "cart",
                                                                "checkout_shipping", "checkout_payment", "confirmation", "help", "login")),
        F("path", "string", True, "URL path or screen name"),
        F("category", "string", False, "Category for category pages", allowed=tuple(CATEGORIES)),
        F("help_topic", "string", False, "Topic for help pages", allowed=tuple(HELP_TOPICS)),
        F("funnel_stage", "integer", True, "Funnel stage the page belongs to (0 = none)", allowed=(0, 1, 2, 3, 4, 5, 6)),
        F("is_active", "boolean", True, "Template live"),
        F("created_at", "timestamp", True, "Template creation"),
    ]),
    Table("product", "Sellable product.", ("product_id",), kind="master", grain="one row per product", fields=[
        F("product_id", "string", True, "Key", unique=True, pattern=r"^PRD-\d{6}$"),
        F("name", "string", True, "Display name (synthetic)"),
        F("brand", "string", True, "Brand (synthetic)"),
        F("category", "string", True, "Category", allowed=tuple(CATEGORIES)),
        F("list_price", "decimal", True, "Price", unit="USD", rule="> 0"),
        F("currency", "string", True, "Currency", allowed=("USD",)),
        F("launched_at", "timestamp", True, "Effective from"),
        F("discontinued_at", "timestamp", False, "Effective to", rule="> launched_at"),
        F("lifecycle_status", "string", True, "Derived as of snapshot", allowed=("active", "discontinued")),
    ]),
    Table("experiment", "A/B experiment definition.", ("experiment_id",), kind="master", grain="one row per experiment", fields=[
        F("experiment_id", "string", True, "Key", unique=True, pattern=r"^EXP-2026-\d{6}$"),
        F("name", "string", True, "Name", unique=True),
        F("hypothesis", "string", True, "Hypothesis"),
        F("channel", "string", True, "Eligible channel", allowed=("web", "app", "all")),
        F("target_step", "string", True, "Funnel step targeted", allowed=("checkout_shipping", "product", "cart", "search", "home")),
        F("status", "string", True, "Lifecycle state", allowed=EXP_STATUS),
        F("allocation_treatment", "decimal", True, "Share to treatment", unit="0-1"),
        F("assignment_unit", "string", True, "Randomisation unit", allowed=("device",)),
        F("owner_team", "string", True, "Owning team"),
        F("created_at", "timestamp", True, "Definition created"),
        F("start_at", "timestamp", True, "Effective from", rule=">= created_at"),
        F("end_at", "timestamp", True, "Effective to (exclusive)", rule="> start_at"),
    ]),
    Table("experiment_assignment", "Bridge Experiment N:M Session (sticky per device).",
          ("experiment_id", "session_id"), kind="bridge", grain="one row per (experiment, session)", fields=[
              F("experiment_id", "string", True, "Experiment", fk="experiment.experiment_id"),
              F("session_id", "string", True, "Session", fk="session.session_id"),
              F("variant", "string", True, "Arm", allowed=("control", "treatment")),
              F("assigned_at", "timestamp", True, "= session start", rule="within [experiment.start_at, end_at)"),
              F("assignment_unit", "string", True, "Unit", allowed=("device",)),
              F("device_id", "string", True, "Device (unit)", fk="device.device_id", rule="same variant for all sessions of a device"),
          ]),
    Table("session", "Collector session. Web/app: 30-min inactivity rule per (device, channel). Support: one CRM contact.",
          ("session_id",), kind="master", grain="one row per session", fields=[
              F("session_id", "string", True, "Key", unique=True, pattern=r"^SES-2026-\d{6}$"),
              F("channel", "string", True, "Channel", allowed=CHANNEL),
              F("device_id", "string", False, "Device (null for phone support)", fk="device.device_id"),
              F("anonymous_id", "string", False, "Device anonymous id", rule="= device.anonymous_id"),
              F("customer_id", "string", False, "Customer authenticated in the session (raw; not consent-filtered)", fk="customer.customer_id"),
              F("session_start_ts", "timestamp", True, "Derived: min(event_ts)"),
              F("session_end_ts", "timestamp", True, "Derived: max(event_ts)", rule=">= session_start_ts"),
              F("duration_s", "decimal", True, "Derived", unit="seconds", rule="= end - start"),
              F("event_count", "integer", True, "Derived: raw events incl. duplicates", rule="= count(journey_event)"),
              F("traffic_source", "string", True, "Acquisition source", allowed=("direct", "organic_search", "paid_search", "social",
                                                                               "referral", "email", "push", "deep_link", "support"),
                rule="email/push only with marketing consent at session start"),
              F("utm_campaign", "string", False, "Campaign code", pattern=r"^CMP-2026\d{2}-[A-Z]+$"),
              F("landing_page_id", "string", False, "Page of the first event (web/app)", fk="page.page_id"),
              F("user_agent", "string", False, "User agent string"),
              F("ip_hash", "string", False, "Salted IP hash (synthetic)"),
              F("geo_country", "string", False, "IP geolocation country", allowed=COUNTRY),
              F("app_version", "string", False, "App version (app only)", allowed=tuple(v for v, _ in APP_RELEASES)),
              F("support_medium", "string", False, "Support only", allowed=("chat", "phone")),
              F("ticket_id", "string", False, "Support only", fk="support_ticket.ticket_id"),
              F("sessionization_rule", "string", True, "Rule version", allowed=("web_app_inactivity_30m_v1", "support_contact_v1")),
          ]),
    Table("journey_event", "Raw cross-channel event stream as delivered by collectors (includes labelled anomalies).",
          ("event_id",), kind="event", grain="one row per collected event", fields=[
              F("event_id", "string", True, "EVT-<session-id>-<arrival counter>", unique=True,
                pattern=r"^EVT-SES-2026-\d{6}-\d{6}$", rule="counter follows ingestion order within the session"),
              F("session_id", "string", True, "Session", fk="session.session_id", rule="event_id prefix = session_id"),
              F("event_type", "string", True, "Taxonomy event", allowed=tuple(EVENT_NAMES), fk="event_taxonomy.event_type"),
              F("event_ts", "timestamp", True, "Occurrence time (client/device clock)"),
              F("ingestion_ts", "timestamp", True, "Collector arrival time", rule=">= event_ts"),
              F("channel", "string", True, "Channel", allowed=CHANNEL, rule="= session.channel"),
              F("source_system", "string", True, "Producer", allowed=("web_sdk", "app_sdk", "support_crm")),
              F("device_id", "string", False, "Device", fk="device.device_id"),
              F("anonymous_id", "string", False, "Device anonymous id"),
              F("customer_id", "string", False, "Authenticated customer at event time (raw)", fk="customer.customer_id"),
              F("auth_state", "string", True, "Auth state", allowed=("anonymous", "authenticated", "agent_verified", "unverified")),
              F("page_id", "string", False, "Page/screen", fk="page.page_id"),
              F("product_id", "string", False, "Product", fk="product.product_id", rule="product active at event_ts"),
              F("cart_id", "string", False, "Cart", fk="cart.cart_id"),
              F("order_id", "string", False, "Order (purchase only)", fk="order.order_id"),
              F("ticket_id", "string", False, "Ticket (support only)", fk="support_ticket.ticket_id"),
              F("client_event_id", "string", True, "SDK idempotency key (dedup key)", pattern=r"^ce-[0-9a-f]{16}$"),
              F("page_load_ms", "integer", False, "Render latency (view events)", unit="ms"),
              F("http_status", "integer", False, "HTTP status for error events"),
              F("error_code", "string", False, "Error code", allowed=tuple(c for c in ERROR_CODES if c)),
              F("quantity", "integer", False, "Units (cart events)", unit="units"),
              F("value", "decimal", False, "Monetary value (cart/purchase, USD) or CSAT score (csat_submitted)",
                rule="purchase value = order.total"),
          ]),
    Table("cart", "Shopping cart (one per session at most).", ("cart_id",), kind="transaction", grain="one row per cart", fields=[
        F("cart_id", "string", True, "Key", unique=True, pattern=r"^CRT-2026-\d{6}$"),
        F("session_id", "string", True, "Session", fk="session.session_id"),
        F("customer_id", "string", False, "Authenticated customer", fk="customer.customer_id"),
        F("anonymous_id", "string", False, "Device anonymous id"),
        F("created_at", "timestamp", True, "First add_to_cart"),
        F("checkout_started_at", "timestamp", False, "First checkout_start", rule=">= created_at"),
        F("status", "string", True, "Current status (= last status_history row)", allowed=CART_STATUS),
        F("status_at", "timestamp", True, "Time of current status"),
        F("item_count", "integer", True, "Derived: sum(quantity) of active items", unit="units"),
        F("subtotal", "decimal", True, "Derived: sum(line_amount) of active items", unit="USD"),
    ]),
    Table("cart_item", "Bridge Cart N:M Product.", ("cart_item_id",), kind="bridge", grain="one row per product line in a cart", fields=[
        F("cart_item_id", "string", True, "Key", unique=True, pattern=r"^CIT-CRT-2026-\d{6}-\d{2}$"),
        F("cart_id", "string", True, "Cart", fk="cart.cart_id"),
        F("product_id", "string", True, "Product", fk="product.product_id"),
        F("quantity", "integer", True, "Units", unit="units", rule="= sum(add_to_cart.quantity) for the line"),
        F("unit_price", "decimal", True, "Price at add time", unit="USD", rule="= product.list_price"),
        F("line_amount", "decimal", True, "Derived quantity*unit_price", unit="USD"),
        F("added_at", "timestamp", True, "First add"),
        F("removed_at", "timestamp", False, "Removal time (null = active)", rule=">= added_at"),
        F("is_active", "boolean", True, "removed_at is null"),
    ]),
    Table("order", "Placed order (1:1 with converted cart). Guest orders have null customer_id.",
          ("order_id",), kind="transaction", grain="one row per order", fields=[
              F("order_id", "string", True, "Key", unique=True, pattern=r"^ORD-2026-\d{6}$"),
              F("cart_id", "string", True, "Cart", fk="cart.cart_id", unique=True),
              F("session_id", "string", True, "Session where placed", fk="session.session_id"),
              F("customer_id", "string", False, "Customer (null = guest)", fk="customer.customer_id"),
              F("order_ts", "timestamp", True, "Placement time"),
              F("status", "string", True, "Current status (= last status_history row)", allowed=ORDER_STATUS),
              F("status_at", "timestamp", True, "Time of current status"),
              F("ship_country", "string", True, "Destination", allowed=COUNTRY),
              F("currency", "string", True, "Currency", allowed=("USD",)),
              F("payment_method", "string", True, "Method", allowed=("card", "wallet", "bnpl", "upi")),
              F("item_count", "integer", True, "Derived sum(order_line.quantity)", unit="units"),
              F("subtotal", "decimal", True, "Derived sum(order_line.line_amount)", unit="USD"),
              F("discount", "decimal", True, "Coupon discount (10% when applied)", unit="USD"),
              F("tax", "decimal", True, "round((subtotal-discount)*country rate, 2)", unit="USD"),
              F("shipping_fee", "decimal", True, "0 if (subtotal-discount)>=50 else 4.99", unit="USD"),
              F("total", "decimal", True, "subtotal-discount+tax+shipping_fee", unit="USD"),
          ]),
    Table("order_line", "Bridge Order N:M Product.", ("order_line_id",), kind="bridge", grain="one row per order line", fields=[
        F("order_line_id", "string", True, "Key", unique=True, pattern=r"^OLN-ORD-2026-\d{6}-\d{2}$"),
        F("order_id", "string", True, "Order", fk="order.order_id"),
        F("line_no", "integer", True, "Line number (1..n)"),
        F("product_id", "string", True, "Product", fk="product.product_id"),
        F("quantity", "integer", True, "Units", unit="units"),
        F("unit_price", "decimal", True, "Price", unit="USD"),
        F("line_amount", "decimal", True, "quantity*unit_price", unit="USD"),
    ]),
    Table("support_ticket", "Support case. Contacts are sessions with channel=support.",
          ("ticket_id",), kind="transaction", grain="one row per ticket", fields=[
              F("ticket_id", "string", True, "Key", unique=True, pattern=r"^TCK-2026-\d{6}$"),
              F("customer_id", "string", False, "Verified customer (null = guest)", fk="customer.customer_id"),
              F("origin_session_id", "string", False, "Web/app session that led to the contact", fk="session.session_id"),
              F("first_contact_session_id", "string", True, "First support session", fk="session.session_id"),
              F("order_id", "string", False, "Related order", fk="order.order_id"),
              F("medium", "string", True, "Contact medium", allowed=("chat", "phone")),
              F("category", "string", True, "Reason", allowed=("payment_issue", "checkout_issue", "technical_issue",
                                                              "product_question", "account_access", "delivery_issue", "refund_request")),
              F("priority", "string", True, "Priority (rule: payment/refund=high)", allowed=("high", "medium", "low")),
              F("status", "string", True, "Current status (= last status_history row)", allowed=TICKET_STATUS),
              F("opened_at", "timestamp", True, "Opened"),
              F("first_response_at", "timestamp", False, "Agent assigned", rule=">= opened_at"),
              F("escalated_at", "timestamp", False, "Escalated", rule=">= first_response_at"),
              F("resolved_at", "timestamp", False, "Resolved", rule=">= first_response_at"),
              F("closed_at", "timestamp", False, "Closed (resolved + 2 days)", rule=">= resolved_at"),
              F("agent_id", "string", False, "Owning agent", fk="support_agent.agent_id"),
              F("csat_score", "integer", False, "1-5 survey score", allowed=(1, 2, 3, 4, 5)),
          ]),
    Table("support_agent", "Support agent reference.", ("agent_id",), kind="reference", grain="one row per agent", fields=[
        F("agent_id", "string", True, "Key", unique=True, pattern=r"^AGT-\d{4}$"),
        F("tier", "integer", True, "Tier", allowed=(1, 2)),
        F("team", "string", True, "Team", allowed=("payments", "orders", "general")),
        F("site", "string", True, "Site"),
        F("hired_at", "timestamp", True, "Hire date"),
    ]),
    Table("status_history", "Append-only lifecycle transitions for cart, order, ticket, experiment, product.",
          ("status_history_id",), kind="history", grain="one row per state change", fields=[
              F("status_history_id", "string", True, "Key", unique=True, pattern=r"^STH-\d{8}$"),
              F("entity_type", "string", True, "Entity", allowed=tuple(LIFECYCLES)),
              F("entity_id", "string", True, "Entity key (polymorphic FK)"),
              F("from_status", "string", False, "Previous state (null = creation)"),
              F("to_status", "string", True, "New state", rule="(from,to) in allowed lifecycle"),
              F("changed_at", "timestamp", True, "Effective time", rule="non-decreasing per entity; <= snapshot"),
              F("changed_by", "string", True, "Actor", allowed=("system", "customer", "support_agent", "carrier", "analyst", "admin")),
          ]),
    Table("event_taxonomy", "Event type contract.", ("event_type",), kind="reference", grain="one row per event type", fields=[
        F("event_type", "string", True, "Key", unique=True, allowed=tuple(EVENT_NAMES)),
        F("category", "string", True, "Category", allowed=("navigation", "engagement", "commerce", "system", "identity", "support")),
        F("funnel_stage", "integer", True, "Funnel stage reached (0 = none)", allowed=(0, 1, 2, 3, 4, 5, 6)),
        F("funnel_stage_name", "string", False, "Stage name", allowed=tuple(v for k, v in STAGE_NAME.items() if k)),
        F("allowed_channels", "string", True, "Pipe-separated channels"),
        F("required_refs", "string", False, "Pipe-separated required reference columns"),
        F("description", "string", True, "Meaning"),
    ]),
    Table("journey_outcome", "Derived per-session outcome (pipeline rules R1-R8 on deduplicated, resequenced events).",
          ("outcome_id",), kind="derived", grain="one row per session", fields=[
              F("outcome_id", "string", True, "OUT-<session-id>", unique=True, pattern=r"^OUT-SES-2026-\d{6}$"),
              F("session_id", "string", True, "Session (1:1)", fk="session.session_id", unique=True),
              F("outcome_type", "string", True, "Outcome", allowed=tuple(OUTCOME_TYPES)),
              F("rule_id", "string", True, "Rule fired", allowed=("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8")),
              F("furthest_stage", "integer", True, "Max funnel stage reached", allowed=(0, 1, 2, 3, 4, 5, 6)),
              F("furthest_stage_name", "string", True, "Stage name"),
              F("drop_off_before_stage", "string", False, "Next stage not reached (null for converted/support)"),
              F("converted", "boolean", True, "outcome_type = converted"),
              F("order_id", "string", False, "First valid purchase order", fk="order.order_id"),
              F("cart_id", "string", False, "Cart touched", fk="cart.cart_id"),
              F("ticket_id", "string", False, "Ticket (support sessions)", fk="support_ticket.ticket_id"),
              F("friction_event_count", "integer", True, "Count of friction events"),
              F("support_contact_flag", "boolean", True, "contact_support_click or support channel"),
              F("valid_event_count", "integer", True, "Events after dedup", rule="<= session.event_count"),
              F("first_event_ts", "timestamp", True, "First valid event"),
              F("last_event_ts", "timestamp", True, "Last valid event"),
              F("duration_s", "decimal", True, "Duration", unit="seconds"),
              F("derivation_version", "string", True, "Rule set version"),
          ]),
]
TABLE = {t.name: t for t in TABLES}
SQL_TYPES = {"string": "TEXT", "integer": "INTEGER", "decimal": "NUMERIC(12,3)", "boolean": "BOOLEAN",
             "timestamp": "TEXT", "json": "TEXT"}


def ddl(dialect: str = "sqlite") -> str:
    out = ["-- Generated from journeylab/schema.py. Timestamps are ISO-8601 UTC text.", ""]
    order = ["customer", "consent_event", "device", "identity_link", "page", "product", "experiment",
             "support_agent", "event_taxonomy", "session", "cart", "order", "cart_item", "order_line",
             "support_ticket", "experiment_assignment", "journey_event", "status_history", "journey_outcome"]
    for name in order:
        t = TABLE[name]
        q = f'"{name}"'
        cols = []
        for f in t.fields:
            c = f'  "{f.name}" {SQL_TYPES[f.type]}' + (" NOT NULL" if f.required else "")
            if f.allowed and f.type == "string":
                vals = ", ".join("'" + str(a) + "'" for a in f.allowed)
                c += f' CHECK ("{f.name}" IN ({vals}))'
            cols.append(c)
        cols.append("  PRIMARY KEY (" + ", ".join(f'"{k}"' for k in t.pk) + ")")
        for f in t.fields:
            if f.fk:
                rt, rc = f.fk.split(".")
                cols.append(f'  FOREIGN KEY ("{f.name}") REFERENCES "{rt}" ("{rc}")' +
                            (" DEFERRABLE INITIALLY DEFERRED" if dialect == "sqlite" else ""))
        out.append(f"CREATE TABLE {q} (\n" + ",\n".join(cols) + "\n);\n")
    return "\n".join(out)


def data_dictionary_md() -> str:
    lines = ["# Data dictionary", "", "Generated from `journeylab/schema.py` (single source of truth). "
             "All timestamps are ISO-8601 UTC (`YYYY-MM-DDTHH:MM:SS.mmmZ`). Money is USD with 2 decimals.", ""]
    lines += ["## Entity overview", "", "| Table | Kind | Grain | Primary key |", "|---|---|---|---|"]
    for t in TABLES:
        lines.append(f"| `{t.name}` | {t.kind} | {t.grain} | `{', '.join(t.pk)}` |")
    lines += ["", "## Relationships and cardinality", ""]
    lines += REL_TABLE
    lines += ["", "## Lifecycle state machines", ""]
    for ent, tr in LIFECYCLES.items():
        lines.append(f"- **{ent}**: " + ", ".join(f"{a or '∅'} → {b}" for a, b in sorted(tr, key=lambda x: (x[0] or '', x[1]))))
    for t in TABLES:
        lines += ["", f"## `{t.name}`", "", t.desc, "", f"Primary key: `{', '.join(t.pk)}`", "",
                  "| Field | Type | Req. | Allowed values | Unit | Unique | Validation rule | Description |",
                  "|---|---|---|---|---|---|---|---|"]
        for f in t.fields:
            allowed = ", ".join(str(a) for a in f.allowed) if f.allowed else ""
            if len(allowed) > 120:
                allowed = allowed[:117] + "…"
            rule = "; ".join(x for x in [f"FK → `{f.fk}`" if f.fk else "", f"regex `{f.pattern}`" if f.pattern else "",
                                         f.rule or ""] if x)
            lines.append(f"| `{f.name}` | {f.type} | {'Y' if f.required else 'N'} | {allowed} | {f.unit or ''} | "
                         f"{'Y' if f.unique else ''} | {rule} | {f.desc} |")
    return "\n".join(lines) + "\n"


REL_TABLE = [
    "| Parent | Child | Cardinality | Optional? | Via |",
    "|---|---|---|---|---|",
    "| customer | consent_event | 1:N | customer may have none (consent unknown) | consent_event.customer_id |",
    "| customer | device | N:M | yes | identity_link (bridge, effective-dated) |",
    "| device | session | 1:N | phone-support sessions have no device | session.device_id |",
    "| customer | session | 1:N | anonymous sessions have none | session.customer_id (authenticated) |",
    "| session | journey_event | 1:N | — | journey_event.session_id |",
    "| session | journey_outcome | 1:1 | — | journey_outcome.session_id |",
    "| session | cart | 1:0..1 | yes | cart.session_id |",
    "| cart | product | N:M | — | cart_item (bridge) |",
    "| cart | order | 1:0..1 | only converted carts | order.cart_id (unique) |",
    "| order | product | N:M | — | order_line (bridge) |",
    "| customer | order | 1:N | guest orders have no customer | order.customer_id |",
    "| support_ticket | session (support contacts) | 1:N | — | session.ticket_id |",
    "| session (web/app) | support_ticket | 1:N | tickets may have no origin | support_ticket.origin_session_id |",
    "| order | support_ticket | 1:N | yes | support_ticket.order_id |",
    "| experiment | session | N:M | — | experiment_assignment (bridge) |",
    "| page / product / cart / order / ticket | journey_event | 1:N | yes (by event type) | journey_event.*_id |",
    "| cart/order/ticket/experiment/product | status_history | 1:N | — | status_history.entity_id (polymorphic) |",
]
