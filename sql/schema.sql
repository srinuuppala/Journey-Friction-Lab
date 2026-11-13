-- Generated from journeylab/schema.py. Timestamps are ISO-8601 UTC text.

CREATE TABLE "customer" (
  "customer_id" TEXT NOT NULL,
  "created_at" TEXT NOT NULL,
  "country" TEXT NOT NULL CHECK ("country" IN ('IN', 'US', 'GB', 'DE', 'AE', 'SG', 'AU', 'CA')),
  "segment" TEXT NOT NULL CHECK ("segment" IN ('new', 'regular', 'vip')),
  "signup_channel" TEXT NOT NULL CHECK ("signup_channel" IN ('web', 'app', 'store')),
  "email_hash" TEXT NOT NULL,
  "analytics_consent_status" TEXT NOT NULL CHECK ("analytics_consent_status" IN ('granted', 'denied', 'withdrawn', 'expired', 'unknown')),
  "marketing_consent_status" TEXT NOT NULL CHECK ("marketing_consent_status" IN ('granted', 'denied', 'withdrawn', 'expired', 'unknown')),
  "consent_status_as_of" TEXT NOT NULL,
  "last_authenticated_at" TEXT,
  "lifecycle_status" TEXT NOT NULL CHECK ("lifecycle_status" IN ('active', 'dormant', 'registered_no_activity')),
  PRIMARY KEY ("customer_id")
);

CREATE TABLE "consent_event" (
  "consent_event_id" TEXT NOT NULL,
  "customer_id" TEXT NOT NULL,
  "consent_type" TEXT NOT NULL CHECK ("consent_type" IN ('analytics', 'marketing')),
  "action" TEXT NOT NULL CHECK ("action" IN ('granted', 'denied', 'withdrawn', 'expired')),
  "effective_at" TEXT NOT NULL,
  "recorded_at" TEXT NOT NULL,
  "source" TEXT NOT NULL CHECK ("source" IN ('signup_form', 'app_prompt', 'store_form', 'cookie_banner', 'preference_center', 'policy_update')),
  "policy_version" TEXT NOT NULL CHECK ("policy_version" IN ('v1', 'v2')),
  PRIMARY KEY ("consent_event_id"),
  FOREIGN KEY ("customer_id") REFERENCES "customer" ("customer_id") DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE "device" (
  "device_id" TEXT NOT NULL,
  "anonymous_id" TEXT NOT NULL,
  "platform" TEXT NOT NULL CHECK ("platform" IN ('web', 'app')),
  "device_type" TEXT NOT NULL CHECK ("device_type" IN ('desktop', 'mobile', 'tablet')),
  "os" TEXT NOT NULL,
  "browser" TEXT,
  "first_seen_at" TEXT NOT NULL,
  "last_seen_at" TEXT NOT NULL,
  PRIMARY KEY ("device_id")
);

CREATE TABLE "identity_link" (
  "link_id" TEXT NOT NULL,
  "device_id" TEXT NOT NULL,
  "anonymous_id" TEXT NOT NULL,
  "customer_id" TEXT NOT NULL,
  "link_method" TEXT NOT NULL CHECK ("link_method" IN ('login', 'email_click', 'probabilistic_match', 'cookie_sync')),
  "confidence" NUMERIC(12,3) NOT NULL,
  "valid_from" TEXT NOT NULL,
  "valid_to" TEXT,
  "source_system" TEXT NOT NULL CHECK ("source_system" IN ('auth_service', 'email_service', 'identity_graph', 'cdp_sync')),
  "created_at" TEXT NOT NULL,
  PRIMARY KEY ("link_id"),
  FOREIGN KEY ("device_id") REFERENCES "device" ("device_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("customer_id") REFERENCES "customer" ("customer_id") DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE "page" (
  "page_id" TEXT NOT NULL,
  "channel" TEXT NOT NULL CHECK ("channel" IN ('web', 'app')),
  "page_type" TEXT NOT NULL CHECK ("page_type" IN ('home', 'category', 'search', 'product', 'cart', 'checkout_shipping', 'checkout_payment', 'confirmation', 'help', 'login')),
  "path" TEXT NOT NULL,
  "category" TEXT CHECK ("category" IN ('electronics', 'home_kitchen', 'fashion', 'beauty', 'sports', 'books', 'toys', 'grocery')),
  "help_topic" TEXT CHECK ("help_topic" IN ('payments', 'delivery', 'returns', 'account', 'orders')),
  "funnel_stage" INTEGER NOT NULL,
  "is_active" BOOLEAN NOT NULL,
  "created_at" TEXT NOT NULL,
  PRIMARY KEY ("page_id")
);

CREATE TABLE "product" (
  "product_id" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "brand" TEXT NOT NULL,
  "category" TEXT NOT NULL CHECK ("category" IN ('electronics', 'home_kitchen', 'fashion', 'beauty', 'sports', 'books', 'toys', 'grocery')),
  "list_price" NUMERIC(12,3) NOT NULL,
  "currency" TEXT NOT NULL CHECK ("currency" IN ('USD')),
  "launched_at" TEXT NOT NULL,
  "discontinued_at" TEXT,
  "lifecycle_status" TEXT NOT NULL CHECK ("lifecycle_status" IN ('active', 'discontinued')),
  PRIMARY KEY ("product_id")
);

CREATE TABLE "experiment" (
  "experiment_id" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "hypothesis" TEXT NOT NULL,
  "channel" TEXT NOT NULL CHECK ("channel" IN ('web', 'app', 'all')),
  "target_step" TEXT NOT NULL CHECK ("target_step" IN ('checkout_shipping', 'product', 'cart', 'search', 'home')),
  "status" TEXT NOT NULL CHECK ("status" IN ('draft', 'running', 'completed', 'stopped')),
  "allocation_treatment" NUMERIC(12,3) NOT NULL,
  "assignment_unit" TEXT NOT NULL CHECK ("assignment_unit" IN ('device')),
  "owner_team" TEXT NOT NULL,
  "created_at" TEXT NOT NULL,
  "start_at" TEXT NOT NULL,
  "end_at" TEXT NOT NULL,
  PRIMARY KEY ("experiment_id")
);

CREATE TABLE "support_agent" (
  "agent_id" TEXT NOT NULL,
  "tier" INTEGER NOT NULL,
  "team" TEXT NOT NULL CHECK ("team" IN ('payments', 'orders', 'general')),
  "site" TEXT NOT NULL,
  "hired_at" TEXT NOT NULL,
  PRIMARY KEY ("agent_id")
);

CREATE TABLE "event_taxonomy" (
  "event_type" TEXT NOT NULL CHECK ("event_type" IN ('session_start', 'page_view', 'screen_view', 'scroll', 'click', 'search', 'product_view', 'add_to_cart', 'add_to_cart_failed', 'remove_from_cart', 'cart_view', 'checkout_start', 'shipping_info_submitted', 'shipping_validation_error', 'payment_info_submitted', 'payment_error', 'purchase', 'login', 'login_failed', 'help_view', 'contact_support_click', 'page_error', 'ticket_created', 'agent_assigned', 'message_customer', 'message_agent', 'ticket_escalated', 'ticket_resolved', 'csat_submitted')),
  "category" TEXT NOT NULL CHECK ("category" IN ('navigation', 'engagement', 'commerce', 'system', 'identity', 'support')),
  "funnel_stage" INTEGER NOT NULL,
  "funnel_stage_name" TEXT CHECK ("funnel_stage_name" IN ('visit', 'product_view', 'add_to_cart', 'checkout_start', 'payment_submitted', 'purchase')),
  "allowed_channels" TEXT NOT NULL,
  "required_refs" TEXT,
  "description" TEXT NOT NULL,
  PRIMARY KEY ("event_type")
);

CREATE TABLE "session" (
  "session_id" TEXT NOT NULL,
  "channel" TEXT NOT NULL CHECK ("channel" IN ('web', 'app', 'support')),
  "device_id" TEXT,
  "anonymous_id" TEXT,
  "customer_id" TEXT,
  "session_start_ts" TEXT NOT NULL,
  "session_end_ts" TEXT NOT NULL,
  "duration_s" NUMERIC(12,3) NOT NULL,
  "event_count" INTEGER NOT NULL,
  "traffic_source" TEXT NOT NULL CHECK ("traffic_source" IN ('direct', 'organic_search', 'paid_search', 'social', 'referral', 'email', 'push', 'deep_link', 'support')),
  "utm_campaign" TEXT,
  "landing_page_id" TEXT,
  "user_agent" TEXT,
  "ip_hash" TEXT,
  "geo_country" TEXT CHECK ("geo_country" IN ('IN', 'US', 'GB', 'DE', 'AE', 'SG', 'AU', 'CA')),
  "app_version" TEXT CHECK ("app_version" IN ('5.0.0', '5.1.0', '5.1.3', '5.2.0', '5.2.1', '5.3.0')),
  "support_medium" TEXT CHECK ("support_medium" IN ('chat', 'phone')),
  "ticket_id" TEXT,
  "sessionization_rule" TEXT NOT NULL CHECK ("sessionization_rule" IN ('web_app_inactivity_30m_v1', 'support_contact_v1')),
  PRIMARY KEY ("session_id"),
  FOREIGN KEY ("device_id") REFERENCES "device" ("device_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("customer_id") REFERENCES "customer" ("customer_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("landing_page_id") REFERENCES "page" ("page_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("ticket_id") REFERENCES "support_ticket" ("ticket_id") DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE "cart" (
  "cart_id" TEXT NOT NULL,
  "session_id" TEXT NOT NULL,
  "customer_id" TEXT,
  "anonymous_id" TEXT,
  "created_at" TEXT NOT NULL,
  "checkout_started_at" TEXT,
  "status" TEXT NOT NULL CHECK ("status" IN ('open', 'checkout_started', 'converted', 'abandoned')),
  "status_at" TEXT NOT NULL,
  "item_count" INTEGER NOT NULL,
  "subtotal" NUMERIC(12,3) NOT NULL,
  PRIMARY KEY ("cart_id"),
  FOREIGN KEY ("session_id") REFERENCES "session" ("session_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("customer_id") REFERENCES "customer" ("customer_id") DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE "order" (
  "order_id" TEXT NOT NULL,
  "cart_id" TEXT NOT NULL,
  "session_id" TEXT NOT NULL,
  "customer_id" TEXT,
  "order_ts" TEXT NOT NULL,
  "status" TEXT NOT NULL CHECK ("status" IN ('placed', 'paid', 'shipped', 'delivered', 'cancelled', 'refunded')),
  "status_at" TEXT NOT NULL,
  "ship_country" TEXT NOT NULL CHECK ("ship_country" IN ('IN', 'US', 'GB', 'DE', 'AE', 'SG', 'AU', 'CA')),
  "currency" TEXT NOT NULL CHECK ("currency" IN ('USD')),
  "payment_method" TEXT NOT NULL CHECK ("payment_method" IN ('card', 'wallet', 'bnpl', 'upi')),
  "item_count" INTEGER NOT NULL,
  "subtotal" NUMERIC(12,3) NOT NULL,
  "discount" NUMERIC(12,3) NOT NULL,
  "tax" NUMERIC(12,3) NOT NULL,
  "shipping_fee" NUMERIC(12,3) NOT NULL,
  "total" NUMERIC(12,3) NOT NULL,
  PRIMARY KEY ("order_id"),
  FOREIGN KEY ("cart_id") REFERENCES "cart" ("cart_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("session_id") REFERENCES "session" ("session_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("customer_id") REFERENCES "customer" ("customer_id") DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE "cart_item" (
  "cart_item_id" TEXT NOT NULL,
  "cart_id" TEXT NOT NULL,
  "product_id" TEXT NOT NULL,
  "quantity" INTEGER NOT NULL,
  "unit_price" NUMERIC(12,3) NOT NULL,
  "line_amount" NUMERIC(12,3) NOT NULL,
  "added_at" TEXT NOT NULL,
  "removed_at" TEXT,
  "is_active" BOOLEAN NOT NULL,
  PRIMARY KEY ("cart_item_id"),
  FOREIGN KEY ("cart_id") REFERENCES "cart" ("cart_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("product_id") REFERENCES "product" ("product_id") DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE "order_line" (
  "order_line_id" TEXT NOT NULL,
  "order_id" TEXT NOT NULL,
  "line_no" INTEGER NOT NULL,
  "product_id" TEXT NOT NULL,
  "quantity" INTEGER NOT NULL,
  "unit_price" NUMERIC(12,3) NOT NULL,
  "line_amount" NUMERIC(12,3) NOT NULL,
  PRIMARY KEY ("order_line_id"),
  FOREIGN KEY ("order_id") REFERENCES "order" ("order_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("product_id") REFERENCES "product" ("product_id") DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE "support_ticket" (
  "ticket_id" TEXT NOT NULL,
  "customer_id" TEXT,
  "origin_session_id" TEXT,
  "first_contact_session_id" TEXT NOT NULL,
  "order_id" TEXT,
  "medium" TEXT NOT NULL CHECK ("medium" IN ('chat', 'phone')),
  "category" TEXT NOT NULL CHECK ("category" IN ('payment_issue', 'checkout_issue', 'technical_issue', 'product_question', 'account_access', 'delivery_issue', 'refund_request')),
  "priority" TEXT NOT NULL CHECK ("priority" IN ('high', 'medium', 'low')),
  "status" TEXT NOT NULL CHECK ("status" IN ('open', 'assigned', 'escalated', 'resolved', 'closed')),
  "opened_at" TEXT NOT NULL,
  "first_response_at" TEXT,
  "escalated_at" TEXT,
  "resolved_at" TEXT,
  "closed_at" TEXT,
  "agent_id" TEXT,
  "csat_score" INTEGER,
  PRIMARY KEY ("ticket_id"),
  FOREIGN KEY ("customer_id") REFERENCES "customer" ("customer_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("origin_session_id") REFERENCES "session" ("session_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("first_contact_session_id") REFERENCES "session" ("session_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("order_id") REFERENCES "order" ("order_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("agent_id") REFERENCES "support_agent" ("agent_id") DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE "experiment_assignment" (
  "experiment_id" TEXT NOT NULL,
  "session_id" TEXT NOT NULL,
  "variant" TEXT NOT NULL CHECK ("variant" IN ('control', 'treatment')),
  "assigned_at" TEXT NOT NULL,
  "assignment_unit" TEXT NOT NULL CHECK ("assignment_unit" IN ('device')),
  "device_id" TEXT NOT NULL,
  PRIMARY KEY ("experiment_id", "session_id"),
  FOREIGN KEY ("experiment_id") REFERENCES "experiment" ("experiment_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("session_id") REFERENCES "session" ("session_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("device_id") REFERENCES "device" ("device_id") DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE "journey_event" (
  "event_id" TEXT NOT NULL,
  "session_id" TEXT NOT NULL,
  "event_type" TEXT NOT NULL CHECK ("event_type" IN ('session_start', 'page_view', 'screen_view', 'scroll', 'click', 'search', 'product_view', 'add_to_cart', 'add_to_cart_failed', 'remove_from_cart', 'cart_view', 'checkout_start', 'shipping_info_submitted', 'shipping_validation_error', 'payment_info_submitted', 'payment_error', 'purchase', 'login', 'login_failed', 'help_view', 'contact_support_click', 'page_error', 'ticket_created', 'agent_assigned', 'message_customer', 'message_agent', 'ticket_escalated', 'ticket_resolved', 'csat_submitted')),
  "event_ts" TEXT NOT NULL,
  "ingestion_ts" TEXT NOT NULL,
  "channel" TEXT NOT NULL CHECK ("channel" IN ('web', 'app', 'support')),
  "source_system" TEXT NOT NULL CHECK ("source_system" IN ('web_sdk', 'app_sdk', 'support_crm')),
  "device_id" TEXT,
  "anonymous_id" TEXT,
  "customer_id" TEXT,
  "auth_state" TEXT NOT NULL CHECK ("auth_state" IN ('anonymous', 'authenticated', 'agent_verified', 'unverified')),
  "page_id" TEXT,
  "product_id" TEXT,
  "cart_id" TEXT,
  "order_id" TEXT,
  "ticket_id" TEXT,
  "client_event_id" TEXT NOT NULL,
  "page_load_ms" INTEGER,
  "http_status" INTEGER,
  "error_code" TEXT CHECK ("error_code" IN ('PAY_GATEWAY_TIMEOUT', 'PAY_DECLINED', 'PAY_3DS_FAILED', 'ADDR_VALIDATION_FAILED', 'CART_API_500', 'HTTP_503', 'AUTH_INVALID_CREDENTIALS')),
  "quantity" INTEGER,
  "value" NUMERIC(12,3),
  PRIMARY KEY ("event_id"),
  FOREIGN KEY ("session_id") REFERENCES "session" ("session_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("event_type") REFERENCES "event_taxonomy" ("event_type") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("device_id") REFERENCES "device" ("device_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("customer_id") REFERENCES "customer" ("customer_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("page_id") REFERENCES "page" ("page_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("product_id") REFERENCES "product" ("product_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("cart_id") REFERENCES "cart" ("cart_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("order_id") REFERENCES "order" ("order_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("ticket_id") REFERENCES "support_ticket" ("ticket_id") DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE "status_history" (
  "status_history_id" TEXT NOT NULL,
  "entity_type" TEXT NOT NULL CHECK ("entity_type" IN ('cart', 'order', 'ticket', 'experiment', 'product')),
  "entity_id" TEXT NOT NULL,
  "from_status" TEXT,
  "to_status" TEXT NOT NULL,
  "changed_at" TEXT NOT NULL,
  "changed_by" TEXT NOT NULL CHECK ("changed_by" IN ('system', 'customer', 'support_agent', 'carrier', 'analyst', 'admin')),
  PRIMARY KEY ("status_history_id")
);

CREATE TABLE "journey_outcome" (
  "outcome_id" TEXT NOT NULL,
  "session_id" TEXT NOT NULL,
  "outcome_type" TEXT NOT NULL CHECK ("outcome_type" IN ('converted', 'support_resolved', 'support_unresolved', 'abandoned_checkout', 'abandoned_cart', 'bounced', 'browsed_product', 'browsed_no_product')),
  "rule_id" TEXT NOT NULL CHECK ("rule_id" IN ('R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8')),
  "furthest_stage" INTEGER NOT NULL,
  "furthest_stage_name" TEXT NOT NULL,
  "drop_off_before_stage" TEXT,
  "converted" BOOLEAN NOT NULL,
  "order_id" TEXT,
  "cart_id" TEXT,
  "ticket_id" TEXT,
  "friction_event_count" INTEGER NOT NULL,
  "support_contact_flag" BOOLEAN NOT NULL,
  "valid_event_count" INTEGER NOT NULL,
  "first_event_ts" TEXT NOT NULL,
  "last_event_ts" TEXT NOT NULL,
  "duration_s" NUMERIC(12,3) NOT NULL,
  "derivation_version" TEXT NOT NULL,
  PRIMARY KEY ("outcome_id"),
  FOREIGN KEY ("session_id") REFERENCES "session" ("session_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("order_id") REFERENCES "order" ("order_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("cart_id") REFERENCES "cart" ("cart_id") DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY ("ticket_id") REFERENCES "support_ticket" ("ticket_id") DEFERRABLE INITIALLY DEFERRED
);
