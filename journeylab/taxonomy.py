"""Event taxonomy, funnel definition, page catalogue and outcome rules.

This module is the documented contract for *what an event means*.  The
simulator emits only event types listed here and the pipeline interprets them
using the same definitions.
"""
from __future__ import annotations

from .config import CATEGORIES, HELP_TOPICS

# --------------------------------------------------------------------------
# Funnel stages (ordered).  A session's furthest stage is the max stage of any
# (deduplicated) event it contains.
# --------------------------------------------------------------------------
FUNNEL_STAGES = [
    (1, "visit", "session_start"),
    (2, "product_view", "product_view"),
    (3, "add_to_cart", "add_to_cart"),
    (4, "checkout_start", "checkout_start"),
    (5, "payment_submitted", "payment_info_submitted"),
    (6, "purchase", "purchase"),
]
STAGE_NAME = {n: name for n, name, _ in FUNNEL_STAGES}
STAGE_NAME[0] = "none"

# --------------------------------------------------------------------------
# Event taxonomy: name -> (category, funnel_stage, channels, required_refs, description)
# --------------------------------------------------------------------------
EVENT_TAXONOMY = [
    ("session_start", "navigation", 1, "web|app", "page_id", "First event of a web/app session (collector-generated)"),
    ("page_view", "navigation", 0, "web", "page_id", "Web page rendered"),
    ("screen_view", "navigation", 0, "app", "page_id", "App screen rendered"),
    ("scroll", "engagement", 0, "web|app", "page_id", "Scroll depth milestone reached"),
    ("click", "engagement", 0, "web|app", "page_id", "Tracked UI click"),
    ("search", "navigation", 0, "web|app", "page_id", "Search query submitted"),
    ("product_view", "commerce", 2, "web|app", "page_id|product_id", "Product detail viewed"),
    ("add_to_cart", "commerce", 3, "web|app", "page_id|product_id|cart_id", "Item added to cart"),
    ("add_to_cart_failed", "system", 0, "web|app", "page_id|product_id", "Add-to-cart API failure"),
    ("remove_from_cart", "commerce", 0, "web|app", "page_id|product_id|cart_id", "Item removed from cart"),
    ("cart_view", "commerce", 0, "web|app", "page_id|cart_id", "Cart opened"),
    ("checkout_start", "commerce", 4, "web|app", "page_id|cart_id", "Checkout initiated from cart"),
    ("shipping_info_submitted", "commerce", 0, "web|app", "page_id|cart_id", "Shipping step submitted OK"),
    ("shipping_validation_error", "system", 0, "web|app", "page_id|cart_id", "Shipping step rejected by validator"),
    ("payment_info_submitted", "commerce", 5, "web|app", "page_id|cart_id", "Payment details submitted"),
    ("payment_error", "system", 0, "web|app", "page_id|cart_id", "Payment attempt failed"),
    ("purchase", "commerce", 6, "web|app", "page_id|cart_id|order_id", "Order placed (conversion)"),
    ("login", "identity", 0, "web|app", "customer_id", "Customer authenticated"),
    ("login_failed", "identity", 0, "web|app", "", "Authentication attempt failed"),
    ("help_view", "support", 0, "web|app", "page_id", "Help article viewed"),
    ("contact_support_click", "support", 0, "web|app", "page_id", "Contact-support CTA clicked"),
    ("page_error", "system", 0, "web|app", "page_id", "Page failed to render (HTTP 5xx)"),
    ("ticket_created", "support", 0, "support", "ticket_id", "Support ticket opened (CRM)"),
    ("agent_assigned", "support", 0, "support", "ticket_id", "Agent picked up the contact"),
    ("message_customer", "support", 0, "support", "ticket_id", "Customer message"),
    ("message_agent", "support", 0, "support", "ticket_id", "Agent message"),
    ("ticket_escalated", "support", 0, "support", "ticket_id", "Escalated to tier-2"),
    ("ticket_resolved", "support", 0, "support", "ticket_id", "Ticket marked resolved"),
    ("csat_submitted", "support", 0, "support", "ticket_id", "Customer satisfaction survey answered"),
]
EVENT_NAMES = [e[0] for e in EVENT_TAXONOMY]
EV = {name: i for i, name in enumerate(EVENT_NAMES)}          # name -> int code
EVENT_STAGE = {e[0]: e[2] for e in EVENT_TAXONOMY}
FRICTION_EVENTS = {"payment_error", "shipping_validation_error", "add_to_cart_failed", "page_error", "login_failed"}

ERROR_CODES = ["", "PAY_GATEWAY_TIMEOUT", "PAY_DECLINED", "PAY_3DS_FAILED", "ADDR_VALIDATION_FAILED",
               "CART_API_500", "HTTP_503", "AUTH_INVALID_CREDENTIALS"]
ERR = {c: i for i, c in enumerate(ERROR_CODES)}

SOURCE_SYSTEM = {"web": "web_sdk", "app": "app_sdk", "support": "support_crm"}

# --------------------------------------------------------------------------
# Page catalogue (master data).  Product pages are templates; the product is
# carried on the event (product_id).
# --------------------------------------------------------------------------
PAGE_TYPE_STAGE = {"home": 1, "category": 1, "search": 1, "product": 2, "cart": 3,
                   "checkout_shipping": 4, "checkout_payment": 5, "confirmation": 6,
                   "help": 0, "login": 0}


def build_pages():
    """Return list of page dicts in deterministic order."""
    pages = []
    for channel in ("web", "app"):
        def add(ptype, path, category=None, topic=None):
            pages.append(dict(channel=channel, page_type=ptype,
                              path=path if channel == "web" else _screen(ptype, category, topic),
                              category=category, help_topic=topic,
                              funnel_stage=PAGE_TYPE_STAGE[ptype]))
        add("home", "/")
        for c in CATEGORIES:
            add("category", f"/c/{c}", category=c)
        add("search", "/search")
        add("product", "/p/{product_id}")
        add("cart", "/cart")
        add("checkout_shipping", "/checkout/shipping")
        add("checkout_payment", "/checkout/payment")
        add("confirmation", "/checkout/confirmation")
        for t in HELP_TOPICS:
            add("help", f"/help/{t}", topic=t)
        add("login", "/account/login")
    return pages


def _screen(ptype, category, topic):
    base = "".join(p.capitalize() for p in ptype.split("_")) + "Screen"
    if category:
        return f"{base}:{category}"
    if topic:
        return f"{base}:{topic}"
    return base


# --------------------------------------------------------------------------
# Outcome rules (JourneyOutcome).  Evaluated in priority order on the
# deduplicated, occurrence-ordered events of one session.
# --------------------------------------------------------------------------
OUTCOME_RULES = [
    ("R1", "converted", "session contains >=1 valid purchase (unique order_id, first occurrence)"),
    ("R2", "support_resolved", "support session containing ticket_resolved"),
    ("R3", "support_unresolved", "support session without ticket_resolved (escalated/pending)"),
    ("R4", "abandoned_checkout", "reached checkout_start (stage>=4) without purchase"),
    ("R5", "abandoned_cart", "reached add_to_cart (stage 3) without checkout_start"),
    ("R6", "bounced", "web/app session with <=1 view event and duration < 10 s"),
    ("R7", "browsed_product", "reached product_view (stage 2) without add_to_cart"),
    ("R8", "browsed_no_product", "any other web/app session"),
]
OUTCOME_TYPES = [r[1] for r in OUTCOME_RULES]

GROUND_TRUTH_ONLY_COLUMNS = {"is_bot", "actor_type", "bot_type", "true_customer_id", "issue_type",
                             "ground_truth", "is_injected", "expected_outcome", "incident_id",
                             "true_effect", "expected_stitched_customer_id", "is_bogus"}
