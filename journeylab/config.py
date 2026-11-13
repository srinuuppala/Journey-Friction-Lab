"""Generator configuration, calendar constants and scenario parameters.

Everything that influences the generated data lives here so that a run is fully
described by (generator version, seed, scale).  Scenario parameters that are
*ground truth* (incidents, true experiment effects) are kept in this module and
are only ever written to ``ground_truth/`` - never to the input tables.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, asdict

GENERATOR_VERSION = "1.0.0"
DEFAULT_SEED = 20261022

BASE_SESSIONS = 100_000
BASE_EVENTS_TARGET = 2_000_000
BASE_CUSTOMERS = 20_000

MS = 1_000
SEC = 1_000
MIN = 60 * SEC
HOUR = 60 * MIN
DAY = 24 * HOUR


def ts(s: str) -> int:
    """ISO-8601 UTC string -> epoch milliseconds."""
    d = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return int(d.timestamp() * 1000)


PERIOD_START = ts("2026-01-01T00:00:00Z")
PERIOD_END = ts("2026-11-01T00:00:00Z")       # exclusive
SNAPSHOT_TS = ts("2026-11-10T00:00:00Z")      # "as-of" time for current statuses
INACTIVITY_TIMEOUT_MS = 30 * MIN              # web/app sessionization rule
MAX_SESSION_MS = 4 * HOUR                     # hard cap on a web/app session
DEVICE_SESSION_SPACING_MS = 8 * HOUR          # generator spacing guard per device
LATE_ARRIVAL_THRESHOLD_MS = 1 * HOUR          # watermark used to flag late events


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = DEFAULT_SEED
    scale: float = 1.0
    bot_share: float = 0.06                    # share of sessions that are bots
    customer_device_session_share: float = 0.64
    shared_device_rate: float = 0.02           # customer devices shared by a household
    # labelled edge-case injection rates
    reorder_session_rate: float = 0.03         # of eligible app/web sessions
    late_tail_session_rate: float = 0.015
    duplicate_conversion_rate: float = 0.05    # of orders
    bogus_link_device_rate: float = 0.02       # of devices with sessions
    cookie_replay_bot_share: float = 0.10      # of bot sessions
    sql_insert_max_rows: int = 250_000         # above this, seed.sql uses CSV import

    @property
    def n_sessions(self) -> int:
        return max(200, round(BASE_SESSIONS * self.scale))

    @property
    def n_customers(self) -> int:
        return max(60, round(BASE_CUSTOMERS * self.scale))

    @property
    def n_products(self) -> int:
        return max(120, round(1500 * self.scale ** 0.5))

    @property
    def n_anonymous_devices(self) -> int:
        return max(60, round(1.4 * self.n_customers))

    @property
    def n_agents(self) -> int:
        return max(6, round(40 * self.scale ** 0.5))

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(n_sessions=self.n_sessions, n_customers=self.n_customers,
                 n_products=self.n_products, n_anonymous_devices=self.n_anonymous_devices,
                 n_agents=self.n_agents, generator_version=GENERATOR_VERSION)
        return d


# --------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------
# country: (weight, utc offset hours, tax rate)
COUNTRIES = {
    "IN": (0.38, 5.5, 0.18), "US": (0.20, -5.0, 0.07), "GB": (0.10, 0.0, 0.20),
    "DE": (0.08, 1.0, 0.19), "AE": (0.06, 4.0, 0.05), "SG": (0.06, 8.0, 0.09),
    "AU": (0.06, 10.0, 0.10), "CA": (0.06, -5.0, 0.13),
}

# category: (lognormal median price USD, sigma, popularity weight)
CATEGORIES = {
    "electronics": (120.0, 0.9, 0.18), "home_kitchen": (45.0, 0.7, 0.15),
    "fashion": (38.0, 0.6, 0.20), "beauty": (22.0, 0.5, 0.12),
    "sports": (55.0, 0.7, 0.10), "books": (14.0, 0.4, 0.09),
    "toys": (28.0, 0.6, 0.08), "grocery": (9.0, 0.5, 0.08),
}

HELP_TOPICS = ["payments", "delivery", "returns", "account", "orders"]

APP_RELEASES = [  # (version, release date)
    ("5.0.0", ts("2025-11-20T00:00:00Z")),
    ("5.1.0", ts("2026-03-15T00:00:00Z")),
    ("5.1.3", ts("2026-04-20T00:00:00Z")),
    ("5.2.0", ts("2026-05-10T00:00:00Z")),
    ("5.2.1", ts("2026-06-21T00:00:00Z")),
    ("5.3.0", ts("2026-08-30T00:00:00Z")),
]

# Experiments (input master data).  True effects live in EXPERIMENT_TRUTH.
EXPERIMENTS = [
    dict(name="one_page_checkout", hypothesis="Merging shipping+payment raises checkout completion",
         channel="web", start="2026-02-01T00:00:00Z", end="2026-05-01T00:00:00Z",
         status="completed", target_step="checkout_shipping", allocation_treatment=0.5,
         owner_team="checkout"),
    dict(name="recommendation_carousel", hypothesis="Carousel on PDP increases add-to-cart",
         channel="all", start="2026-03-01T00:00:00Z", end="2026-07-01T00:00:00Z",
         status="completed", target_step="product", allocation_treatment=0.5, owner_team="discovery"),
    dict(name="free_shipping_banner", hypothesis="Free-shipping threshold banner lifts cart->checkout",
         channel="web", start="2026-06-01T00:00:00Z", end="2026-09-01T00:00:00Z",
         status="completed", target_step="cart", allocation_treatment=0.5, owner_team="growth"),
    dict(name="app_onboarding_v2", hypothesis="New onboarding improves browse depth",
         channel="app", start="2026-09-01T00:00:00Z", end="2026-09-22T00:00:00Z",
         status="stopped", target_step="home", allocation_treatment=0.5, owner_team="app"),
    dict(name="search_autocomplete", hypothesis="Autocomplete improves search->product",
         channel="web", start="2026-07-01T00:00:00Z", end="2026-11-01T00:00:00Z",
         status="running", target_step="search", allocation_treatment=0.5, owner_team="discovery"),
    dict(name="guest_checkout_express", hypothesis="Express guest checkout (not launched)",
         channel="web", start="2026-11-15T00:00:00Z", end="2026-12-31T00:00:00Z",
         status="draft", target_step="checkout_shipping", allocation_treatment=0.5, owner_team="checkout"),
]

# Ground-truth only: multiplicative effects applied by the simulator to treatment.
EXPERIMENT_TRUTH = {
    "one_page_checkout": {"shipping->payment": 2.50, "note": "treatment raises shipping->payment weight 2.5x"},
    "recommendation_carousel": {"product->add_to_cart": 1.25, "note": "treatment raises add-to-cart weight 25%"},
    "free_shipping_banner": {"cart->shipping": 1.50, "note": "treatment raises cart->checkout weight 50%"},
    "app_onboarding_v2": {"note": "null effect (A/A-like); stopped early"},
    "search_autocomplete": {"search->product": 1.50, "note": "treatment raises search->product weight 50%"},
    "guest_checkout_express": {"note": "draft, no assignments expected"},
}

# Ground-truth only: injected broken steps / latency incidents.
INCIDENTS = [
    dict(incident_id="INC-2026-001", kind="broken_step", channel="app", step="checkout_payment",
         event_type="payment_error", error_code="PAY_GATEWAY_TIMEOUT", app_version="5.2.0",
         start="2026-05-10T00:00:00Z", end="2026-06-21T00:00:00Z", error_rate=0.45,
         description="App 5.2.0 payment SDK times out at the gateway; fixed by 5.2.1"),
    dict(incident_id="INC-2026-002", kind="broken_step", channel="web", step="checkout_shipping",
         event_type="shipping_validation_error", error_code="ADDR_VALIDATION_FAILED", geo_country=["DE", "GB"],
         start="2026-08-01T00:00:00Z", end="2026-09-05T00:00:00Z", error_rate=0.45,
         description="New address validator rejects German and UK postcodes on web checkout"),
    dict(incident_id="INC-2026-003", kind="latency", channel="web", step="search",
         start="2026-07-05T00:00:00Z", end="2026-07-26T00:00:00Z", latency_multiplier=6.0,
         description="Search service degradation: web search page load x6"),
    dict(incident_id="INC-2026-004", kind="broken_step", channel="app", step="product",
         event_type="add_to_cart_failed", error_code="CART_API_500", os="Android 13", app_version_prefix="5.1.",
         start="2026-03-15T00:00:00Z", end="2026-05-10T00:00:00Z", error_rate=0.50,
         description="Add-to-cart API returns 500 for Android 13 on app 5.1.x"),
]
for _inc in INCIDENTS:
    _inc["start_ms"] = ts(_inc["start"])
    _inc["end_ms"] = ts(_inc["end"])
