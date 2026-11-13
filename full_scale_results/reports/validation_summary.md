# Validation summary

**Result: PASS** — 438/438 checks passed.

Hard checks must report 0 violations. `labelled` checks prove every irregularity in the data is covered by a ground-truth label (and nothing unlabelled was corrupted).

| Category | Check | Kind | Status | Violations |
|---|---|---|---|---|
| schema | customer: columns match dictionary | hard | PASS | 0 |
| pk | customer: primary key unique & non-null | hard | PASS | 0 |
| required | customer.customer_id not null | hard | PASS | 0 |
| format | customer.customer_id matches ^CUS-\d{6}$ | hard | PASS | 0 |
| required | customer.created_at not null | hard | PASS | 0 |
| format | customer.created_at ISO-8601 UTC | hard | PASS | 0 |
| required | customer.country not null | hard | PASS | 0 |
| enum | customer.country in allowed values | hard | PASS | 0 |
| required | customer.segment not null | hard | PASS | 0 |
| enum | customer.segment in allowed values | hard | PASS | 0 |
| required | customer.signup_channel not null | hard | PASS | 0 |
| enum | customer.signup_channel in allowed values | hard | PASS | 0 |
| required | customer.email_hash not null | hard | PASS | 0 |
| format | customer.email_hash matches ^sha256:[0-9a-f]{64}$ | hard | PASS | 0 |
| unique | customer.email_hash unique | hard | PASS | 0 |
| required | customer.analytics_consent_status not null | hard | PASS | 0 |
| enum | customer.analytics_consent_status in allowed values | hard | PASS | 0 |
| required | customer.marketing_consent_status not null | hard | PASS | 0 |
| enum | customer.marketing_consent_status in allowed values | hard | PASS | 0 |
| required | customer.consent_status_as_of not null | hard | PASS | 0 |
| format | customer.consent_status_as_of ISO-8601 UTC | hard | PASS | 0 |
| format | customer.last_authenticated_at ISO-8601 UTC | hard | PASS | 0 |
| required | customer.lifecycle_status not null | hard | PASS | 0 |
| enum | customer.lifecycle_status in allowed values | hard | PASS | 0 |
| schema | consent_event: columns match dictionary | hard | PASS | 0 |
| pk | consent_event: primary key unique & non-null | hard | PASS | 0 |
| required | consent_event.consent_event_id not null | hard | PASS | 0 |
| format | consent_event.consent_event_id matches ^CNS-\d{7}$ | hard | PASS | 0 |
| required | consent_event.customer_id not null | hard | PASS | 0 |
| required | consent_event.consent_type not null | hard | PASS | 0 |
| enum | consent_event.consent_type in allowed values | hard | PASS | 0 |
| required | consent_event.action not null | hard | PASS | 0 |
| enum | consent_event.action in allowed values | hard | PASS | 0 |
| required | consent_event.effective_at not null | hard | PASS | 0 |
| format | consent_event.effective_at ISO-8601 UTC | hard | PASS | 0 |
| required | consent_event.recorded_at not null | hard | PASS | 0 |
| format | consent_event.recorded_at ISO-8601 UTC | hard | PASS | 0 |
| required | consent_event.source not null | hard | PASS | 0 |
| enum | consent_event.source in allowed values | hard | PASS | 0 |
| required | consent_event.policy_version not null | hard | PASS | 0 |
| enum | consent_event.policy_version in allowed values | hard | PASS | 0 |
| schema | device: columns match dictionary | hard | PASS | 0 |
| pk | device: primary key unique & non-null | hard | PASS | 0 |
| required | device.device_id not null | hard | PASS | 0 |
| format | device.device_id matches ^DEV-\d{7}$ | hard | PASS | 0 |
| required | device.anonymous_id not null | hard | PASS | 0 |
| format | device.anonymous_id matches ^ANO-[0-9a-f]{10}$ | hard | PASS | 0 |
| unique | device.anonymous_id unique | hard | PASS | 0 |
| required | device.platform not null | hard | PASS | 0 |
| enum | device.platform in allowed values | hard | PASS | 0 |
| required | device.device_type not null | hard | PASS | 0 |
| enum | device.device_type in allowed values | hard | PASS | 0 |
| required | device.os not null | hard | PASS | 0 |
| required | device.first_seen_at not null | hard | PASS | 0 |
| format | device.first_seen_at ISO-8601 UTC | hard | PASS | 0 |
| required | device.last_seen_at not null | hard | PASS | 0 |
| format | device.last_seen_at ISO-8601 UTC | hard | PASS | 0 |
| schema | identity_link: columns match dictionary | hard | PASS | 0 |
| pk | identity_link: primary key unique & non-null | hard | PASS | 0 |
| required | identity_link.link_id not null | hard | PASS | 0 |
| format | identity_link.link_id matches ^IDL-\d{7}$ | hard | PASS | 0 |
| required | identity_link.device_id not null | hard | PASS | 0 |
| required | identity_link.anonymous_id not null | hard | PASS | 0 |
| required | identity_link.customer_id not null | hard | PASS | 0 |
| required | identity_link.link_method not null | hard | PASS | 0 |
| enum | identity_link.link_method in allowed values | hard | PASS | 0 |
| required | identity_link.confidence not null | hard | PASS | 0 |
| required | identity_link.valid_from not null | hard | PASS | 0 |
| format | identity_link.valid_from ISO-8601 UTC | hard | PASS | 0 |
| required | identity_link.source_system not null | hard | PASS | 0 |
| enum | identity_link.source_system in allowed values | hard | PASS | 0 |
| required | identity_link.created_at not null | hard | PASS | 0 |
| format | identity_link.created_at ISO-8601 UTC | hard | PASS | 0 |
| schema | page: columns match dictionary | hard | PASS | 0 |
| pk | page: primary key unique & non-null | hard | PASS | 0 |
| required | page.page_id not null | hard | PASS | 0 |
| format | page.page_id matches ^PAG-\d{4}$ | hard | PASS | 0 |
| required | page.channel not null | hard | PASS | 0 |
| enum | page.channel in allowed values | hard | PASS | 0 |
| required | page.page_type not null | hard | PASS | 0 |
| enum | page.page_type in allowed values | hard | PASS | 0 |
| required | page.path not null | hard | PASS | 0 |
| enum | page.category in allowed values | hard | PASS | 0 |
| enum | page.help_topic in allowed values | hard | PASS | 0 |
| required | page.funnel_stage not null | hard | PASS | 0 |
| enum | page.funnel_stage in allowed values | hard | PASS | 0 |
| required | page.is_active not null | hard | PASS | 0 |
| required | page.created_at not null | hard | PASS | 0 |
| format | page.created_at ISO-8601 UTC | hard | PASS | 0 |
| schema | product: columns match dictionary | hard | PASS | 0 |
| pk | product: primary key unique & non-null | hard | PASS | 0 |
| required | product.product_id not null | hard | PASS | 0 |
| format | product.product_id matches ^PRD-\d{6}$ | hard | PASS | 0 |
| required | product.name not null | hard | PASS | 0 |
| required | product.brand not null | hard | PASS | 0 |
| required | product.category not null | hard | PASS | 0 |
| enum | product.category in allowed values | hard | PASS | 0 |
| required | product.list_price not null | hard | PASS | 0 |
| required | product.currency not null | hard | PASS | 0 |
| enum | product.currency in allowed values | hard | PASS | 0 |
| required | product.launched_at not null | hard | PASS | 0 |
| format | product.launched_at ISO-8601 UTC | hard | PASS | 0 |
| format | product.discontinued_at ISO-8601 UTC | hard | PASS | 0 |
| required | product.lifecycle_status not null | hard | PASS | 0 |
| enum | product.lifecycle_status in allowed values | hard | PASS | 0 |
| schema | experiment: columns match dictionary | hard | PASS | 0 |
| pk | experiment: primary key unique & non-null | hard | PASS | 0 |
| required | experiment.experiment_id not null | hard | PASS | 0 |
| format | experiment.experiment_id matches ^EXP-2026-\d{6}$ | hard | PASS | 0 |
| required | experiment.name not null | hard | PASS | 0 |
| unique | experiment.name unique | hard | PASS | 0 |
| required | experiment.hypothesis not null | hard | PASS | 0 |
| required | experiment.channel not null | hard | PASS | 0 |
| enum | experiment.channel in allowed values | hard | PASS | 0 |
| required | experiment.target_step not null | hard | PASS | 0 |
| enum | experiment.target_step in allowed values | hard | PASS | 0 |
| required | experiment.status not null | hard | PASS | 0 |
| enum | experiment.status in allowed values | hard | PASS | 0 |
| required | experiment.allocation_treatment not null | hard | PASS | 0 |
| required | experiment.assignment_unit not null | hard | PASS | 0 |
| enum | experiment.assignment_unit in allowed values | hard | PASS | 0 |
| required | experiment.owner_team not null | hard | PASS | 0 |
| required | experiment.created_at not null | hard | PASS | 0 |
| format | experiment.created_at ISO-8601 UTC | hard | PASS | 0 |
| required | experiment.start_at not null | hard | PASS | 0 |
| format | experiment.start_at ISO-8601 UTC | hard | PASS | 0 |
| required | experiment.end_at not null | hard | PASS | 0 |
| format | experiment.end_at ISO-8601 UTC | hard | PASS | 0 |
| schema | experiment_assignment: columns match dictionary | hard | PASS | 0 |
| pk | experiment_assignment: primary key unique & non-null | hard | PASS | 0 |
| required | experiment_assignment.experiment_id not null | hard | PASS | 0 |
| required | experiment_assignment.session_id not null | hard | PASS | 0 |
| required | experiment_assignment.variant not null | hard | PASS | 0 |
| enum | experiment_assignment.variant in allowed values | hard | PASS | 0 |
| required | experiment_assignment.assigned_at not null | hard | PASS | 0 |
| format | experiment_assignment.assigned_at ISO-8601 UTC | hard | PASS | 0 |
| required | experiment_assignment.assignment_unit not null | hard | PASS | 0 |
| enum | experiment_assignment.assignment_unit in allowed values | hard | PASS | 0 |
| required | experiment_assignment.device_id not null | hard | PASS | 0 |
| schema | session: columns match dictionary | hard | PASS | 0 |
| pk | session: primary key unique & non-null | hard | PASS | 0 |
| required | session.session_id not null | hard | PASS | 0 |
| format | session.session_id matches ^SES-2026-\d{6}$ | hard | PASS | 0 |
| required | session.channel not null | hard | PASS | 0 |
| enum | session.channel in allowed values | hard | PASS | 0 |
| required | session.session_start_ts not null | hard | PASS | 0 |
| format | session.session_start_ts ISO-8601 UTC | hard | PASS | 0 |
| required | session.session_end_ts not null | hard | PASS | 0 |
| format | session.session_end_ts ISO-8601 UTC | hard | PASS | 0 |
| required | session.duration_s not null | hard | PASS | 0 |
| required | session.event_count not null | hard | PASS | 0 |
| required | session.traffic_source not null | hard | PASS | 0 |
| enum | session.traffic_source in allowed values | hard | PASS | 0 |
| format | session.utm_campaign matches ^CMP-2026\d{2}-[A-Z]+$ | hard | PASS | 0 |
| enum | session.geo_country in allowed values | hard | PASS | 0 |
| enum | session.app_version in allowed values | hard | PASS | 0 |
| enum | session.support_medium in allowed values | hard | PASS | 0 |
| required | session.sessionization_rule not null | hard | PASS | 0 |
| enum | session.sessionization_rule in allowed values | hard | PASS | 0 |
| schema | journey_event: columns match dictionary | hard | PASS | 0 |
| pk | journey_event: primary key unique & non-null | hard | PASS | 0 |
| required | journey_event.event_id not null | hard | PASS | 0 |
| format | journey_event.event_id matches ^EVT-SES-2026-\d{6}-\d{6}$ | hard | PASS | 0 |
| required | journey_event.session_id not null | hard | PASS | 0 |
| required | journey_event.event_type not null | hard | PASS | 0 |
| enum | journey_event.event_type in allowed values | hard | PASS | 0 |
| required | journey_event.event_ts not null | hard | PASS | 0 |
| format | journey_event.event_ts ISO-8601 UTC | hard | PASS | 0 |
| required | journey_event.ingestion_ts not null | hard | PASS | 0 |
| format | journey_event.ingestion_ts ISO-8601 UTC | hard | PASS | 0 |
| required | journey_event.channel not null | hard | PASS | 0 |
| enum | journey_event.channel in allowed values | hard | PASS | 0 |
| required | journey_event.source_system not null | hard | PASS | 0 |
| enum | journey_event.source_system in allowed values | hard | PASS | 0 |
| required | journey_event.auth_state not null | hard | PASS | 0 |
| enum | journey_event.auth_state in allowed values | hard | PASS | 0 |
| required | journey_event.client_event_id not null | hard | PASS | 0 |
| format | journey_event.client_event_id matches ^ce-[0-9a-f]{16}$ | hard | PASS | 0 |
| enum | journey_event.error_code in allowed values | hard | PASS | 0 |
| schema | cart: columns match dictionary | hard | PASS | 0 |
| pk | cart: primary key unique & non-null | hard | PASS | 0 |
| required | cart.cart_id not null | hard | PASS | 0 |
| format | cart.cart_id matches ^CRT-2026-\d{6}$ | hard | PASS | 0 |
| required | cart.session_id not null | hard | PASS | 0 |
| required | cart.created_at not null | hard | PASS | 0 |
| format | cart.created_at ISO-8601 UTC | hard | PASS | 0 |
| format | cart.checkout_started_at ISO-8601 UTC | hard | PASS | 0 |
| required | cart.status not null | hard | PASS | 0 |
| enum | cart.status in allowed values | hard | PASS | 0 |
| required | cart.status_at not null | hard | PASS | 0 |
| format | cart.status_at ISO-8601 UTC | hard | PASS | 0 |
| required | cart.item_count not null | hard | PASS | 0 |
| required | cart.subtotal not null | hard | PASS | 0 |
| schema | cart_item: columns match dictionary | hard | PASS | 0 |
| pk | cart_item: primary key unique & non-null | hard | PASS | 0 |
| required | cart_item.cart_item_id not null | hard | PASS | 0 |
| format | cart_item.cart_item_id matches ^CIT-CRT-2026-\d{6}-\d{2}$ | hard | PASS | 0 |
| required | cart_item.cart_id not null | hard | PASS | 0 |
| required | cart_item.product_id not null | hard | PASS | 0 |
| required | cart_item.quantity not null | hard | PASS | 0 |
| required | cart_item.unit_price not null | hard | PASS | 0 |
| required | cart_item.line_amount not null | hard | PASS | 0 |
| required | cart_item.added_at not null | hard | PASS | 0 |
| format | cart_item.added_at ISO-8601 UTC | hard | PASS | 0 |
| format | cart_item.removed_at ISO-8601 UTC | hard | PASS | 0 |
| required | cart_item.is_active not null | hard | PASS | 0 |
| schema | order: columns match dictionary | hard | PASS | 0 |
| pk | order: primary key unique & non-null | hard | PASS | 0 |
| required | order.order_id not null | hard | PASS | 0 |
| format | order.order_id matches ^ORD-2026-\d{6}$ | hard | PASS | 0 |
| required | order.cart_id not null | hard | PASS | 0 |
| unique | order.cart_id unique | hard | PASS | 0 |
| required | order.session_id not null | hard | PASS | 0 |
| required | order.order_ts not null | hard | PASS | 0 |
| format | order.order_ts ISO-8601 UTC | hard | PASS | 0 |
| required | order.status not null | hard | PASS | 0 |
| enum | order.status in allowed values | hard | PASS | 0 |
| required | order.status_at not null | hard | PASS | 0 |
| format | order.status_at ISO-8601 UTC | hard | PASS | 0 |
| required | order.ship_country not null | hard | PASS | 0 |
| enum | order.ship_country in allowed values | hard | PASS | 0 |
| required | order.currency not null | hard | PASS | 0 |
| enum | order.currency in allowed values | hard | PASS | 0 |
| required | order.payment_method not null | hard | PASS | 0 |
| enum | order.payment_method in allowed values | hard | PASS | 0 |
| required | order.item_count not null | hard | PASS | 0 |
| required | order.subtotal not null | hard | PASS | 0 |
| required | order.discount not null | hard | PASS | 0 |
| required | order.tax not null | hard | PASS | 0 |
| required | order.shipping_fee not null | hard | PASS | 0 |
| required | order.total not null | hard | PASS | 0 |
| schema | order_line: columns match dictionary | hard | PASS | 0 |
| pk | order_line: primary key unique & non-null | hard | PASS | 0 |
| required | order_line.order_line_id not null | hard | PASS | 0 |
| format | order_line.order_line_id matches ^OLN-ORD-2026-\d{6}-\d{2}$ | hard | PASS | 0 |
| required | order_line.order_id not null | hard | PASS | 0 |
| required | order_line.line_no not null | hard | PASS | 0 |
| required | order_line.product_id not null | hard | PASS | 0 |
| required | order_line.quantity not null | hard | PASS | 0 |
| required | order_line.unit_price not null | hard | PASS | 0 |
| required | order_line.line_amount not null | hard | PASS | 0 |
| schema | support_ticket: columns match dictionary | hard | PASS | 0 |
| pk | support_ticket: primary key unique & non-null | hard | PASS | 0 |
| required | support_ticket.ticket_id not null | hard | PASS | 0 |
| format | support_ticket.ticket_id matches ^TCK-2026-\d{6}$ | hard | PASS | 0 |
| required | support_ticket.first_contact_session_id not null | hard | PASS | 0 |
| required | support_ticket.medium not null | hard | PASS | 0 |
| enum | support_ticket.medium in allowed values | hard | PASS | 0 |
| required | support_ticket.category not null | hard | PASS | 0 |
| enum | support_ticket.category in allowed values | hard | PASS | 0 |
| required | support_ticket.priority not null | hard | PASS | 0 |
| enum | support_ticket.priority in allowed values | hard | PASS | 0 |
| required | support_ticket.status not null | hard | PASS | 0 |
| enum | support_ticket.status in allowed values | hard | PASS | 0 |
| required | support_ticket.opened_at not null | hard | PASS | 0 |
| format | support_ticket.opened_at ISO-8601 UTC | hard | PASS | 0 |
| format | support_ticket.first_response_at ISO-8601 UTC | hard | PASS | 0 |
| format | support_ticket.escalated_at ISO-8601 UTC | hard | PASS | 0 |
| format | support_ticket.resolved_at ISO-8601 UTC | hard | PASS | 0 |
| format | support_ticket.closed_at ISO-8601 UTC | hard | PASS | 0 |
| enum | support_ticket.csat_score in allowed values | hard | PASS | 0 |
| schema | support_agent: columns match dictionary | hard | PASS | 0 |
| pk | support_agent: primary key unique & non-null | hard | PASS | 0 |
| required | support_agent.agent_id not null | hard | PASS | 0 |
| format | support_agent.agent_id matches ^AGT-\d{4}$ | hard | PASS | 0 |
| required | support_agent.tier not null | hard | PASS | 0 |
| enum | support_agent.tier in allowed values | hard | PASS | 0 |
| required | support_agent.team not null | hard | PASS | 0 |
| enum | support_agent.team in allowed values | hard | PASS | 0 |
| required | support_agent.site not null | hard | PASS | 0 |
| required | support_agent.hired_at not null | hard | PASS | 0 |
| format | support_agent.hired_at ISO-8601 UTC | hard | PASS | 0 |
| schema | status_history: columns match dictionary | hard | PASS | 0 |
| pk | status_history: primary key unique & non-null | hard | PASS | 0 |
| required | status_history.status_history_id not null | hard | PASS | 0 |
| format | status_history.status_history_id matches ^STH-\d{8}$ | hard | PASS | 0 |
| required | status_history.entity_type not null | hard | PASS | 0 |
| enum | status_history.entity_type in allowed values | hard | PASS | 0 |
| required | status_history.entity_id not null | hard | PASS | 0 |
| required | status_history.to_status not null | hard | PASS | 0 |
| required | status_history.changed_at not null | hard | PASS | 0 |
| format | status_history.changed_at ISO-8601 UTC | hard | PASS | 0 |
| required | status_history.changed_by not null | hard | PASS | 0 |
| enum | status_history.changed_by in allowed values | hard | PASS | 0 |
| schema | event_taxonomy: columns match dictionary | hard | PASS | 0 |
| pk | event_taxonomy: primary key unique & non-null | hard | PASS | 0 |
| required | event_taxonomy.event_type not null | hard | PASS | 0 |
| enum | event_taxonomy.event_type in allowed values | hard | PASS | 0 |
| required | event_taxonomy.category not null | hard | PASS | 0 |
| enum | event_taxonomy.category in allowed values | hard | PASS | 0 |
| required | event_taxonomy.funnel_stage not null | hard | PASS | 0 |
| enum | event_taxonomy.funnel_stage in allowed values | hard | PASS | 0 |
| enum | event_taxonomy.funnel_stage_name in allowed values | hard | PASS | 0 |
| required | event_taxonomy.allowed_channels not null | hard | PASS | 0 |
| required | event_taxonomy.description not null | hard | PASS | 0 |
| schema | journey_outcome: columns match dictionary | hard | PASS | 0 |
| pk | journey_outcome: primary key unique & non-null | hard | PASS | 0 |
| required | journey_outcome.outcome_id not null | hard | PASS | 0 |
| format | journey_outcome.outcome_id matches ^OUT-SES-2026-\d{6}$ | hard | PASS | 0 |
| required | journey_outcome.session_id not null | hard | PASS | 0 |
| unique | journey_outcome.session_id unique | hard | PASS | 0 |
| required | journey_outcome.outcome_type not null | hard | PASS | 0 |
| enum | journey_outcome.outcome_type in allowed values | hard | PASS | 0 |
| required | journey_outcome.rule_id not null | hard | PASS | 0 |
| enum | journey_outcome.rule_id in allowed values | hard | PASS | 0 |
| required | journey_outcome.furthest_stage not null | hard | PASS | 0 |
| enum | journey_outcome.furthest_stage in allowed values | hard | PASS | 0 |
| required | journey_outcome.furthest_stage_name not null | hard | PASS | 0 |
| required | journey_outcome.converted not null | hard | PASS | 0 |
| required | journey_outcome.friction_event_count not null | hard | PASS | 0 |
| required | journey_outcome.support_contact_flag not null | hard | PASS | 0 |
| required | journey_outcome.valid_event_count not null | hard | PASS | 0 |
| required | journey_outcome.first_event_ts not null | hard | PASS | 0 |
| format | journey_outcome.first_event_ts ISO-8601 UTC | hard | PASS | 0 |
| required | journey_outcome.last_event_ts not null | hard | PASS | 0 |
| format | journey_outcome.last_event_ts ISO-8601 UTC | hard | PASS | 0 |
| required | journey_outcome.duration_s not null | hard | PASS | 0 |
| required | journey_outcome.derivation_version not null | hard | PASS | 0 |
| fk | consent_event.customer_id -> customer.customer_id | hard | PASS | 0 |
| fk | identity_link.device_id -> device.device_id | hard | PASS | 0 |
| fk | identity_link.customer_id -> customer.customer_id | hard | PASS | 0 |
| fk | experiment_assignment.experiment_id -> experiment.experiment_id | hard | PASS | 0 |
| fk | experiment_assignment.session_id -> session.session_id | hard | PASS | 0 |
| fk | experiment_assignment.device_id -> device.device_id | hard | PASS | 0 |
| fk | session.device_id -> device.device_id | hard | PASS | 0 |
| fk | session.customer_id -> customer.customer_id | hard | PASS | 0 |
| fk | session.landing_page_id -> page.page_id | hard | PASS | 0 |
| fk | session.ticket_id -> support_ticket.ticket_id | hard | PASS | 0 |
| fk | journey_event.session_id -> session.session_id | hard | PASS | 0 |
| fk | journey_event.event_type -> event_taxonomy.event_type | hard | PASS | 0 |
| fk | journey_event.device_id -> device.device_id | hard | PASS | 0 |
| fk | journey_event.customer_id -> customer.customer_id | hard | PASS | 0 |
| fk | journey_event.page_id -> page.page_id | hard | PASS | 0 |
| fk | journey_event.product_id -> product.product_id | hard | PASS | 0 |
| fk | journey_event.cart_id -> cart.cart_id | hard | PASS | 0 |
| fk | journey_event.order_id -> order.order_id | hard | PASS | 0 |
| fk | journey_event.ticket_id -> support_ticket.ticket_id | hard | PASS | 0 |
| fk | cart.session_id -> session.session_id | hard | PASS | 0 |
| fk | cart.customer_id -> customer.customer_id | hard | PASS | 0 |
| fk | cart_item.cart_id -> cart.cart_id | hard | PASS | 0 |
| fk | cart_item.product_id -> product.product_id | hard | PASS | 0 |
| fk | order.cart_id -> cart.cart_id | hard | PASS | 0 |
| fk | order.session_id -> session.session_id | hard | PASS | 0 |
| fk | order.customer_id -> customer.customer_id | hard | PASS | 0 |
| fk | order_line.order_id -> order.order_id | hard | PASS | 0 |
| fk | order_line.product_id -> product.product_id | hard | PASS | 0 |
| fk | support_ticket.customer_id -> customer.customer_id | hard | PASS | 0 |
| fk | support_ticket.origin_session_id -> session.session_id | hard | PASS | 0 |
| fk | support_ticket.first_contact_session_id -> session.session_id | hard | PASS | 0 |
| fk | support_ticket.order_id -> order.order_id | hard | PASS | 0 |
| fk | support_ticket.agent_id -> support_agent.agent_id | hard | PASS | 0 |
| fk | journey_outcome.session_id -> session.session_id | hard | PASS | 0 |
| fk | journey_outcome.order_id -> order.order_id | hard | PASS | 0 |
| fk | journey_outcome.cart_id -> cart.cart_id | hard | PASS | 0 |
| fk | journey_outcome.ticket_id -> support_ticket.ticket_id | hard | PASS | 0 |
| fk | status_history.entity_id -> polymorphic parent | hard | PASS | 0 |
| consistency | event_id prefix equals session_id | hard | PASS | 0 |
| consistency | event.channel = session.channel | hard | PASS | 0 |
| consistency | event.device_id = session.device_id | hard | PASS | 0 |
| consistency | session.anonymous_id = device.anonymous_id | hard | PASS | 0 |
| consistency | identity_link.anonymous_id = device.anonymous_id | hard | PASS | 0 |
| consistency | event required references present (taxonomy) | hard | PASS | 0 |
| consistency | event type allowed on channel | hard | PASS | 0 |
| dates | ingestion_ts >= event_ts | hard | PASS | 0 |
| derived | session start/end = min/max(event_ts) | hard | PASS | 0 |
| derived | session.event_count = count(events) | hard | PASS | 0 |
| derived | session.duration_s = end - start | hard | PASS | 0 |
| dates | authenticated events after customer.created_at | hard | PASS | 0 |
| dates | consent effective_at >= customer.created_at | hard | PASS | 0 |
| dates | consent recorded_at >= effective_at | hard | PASS | 0 |
| dates | identity_link.valid_from >= customer.created_at | hard | PASS | 0 |
| dates | product active at event time (launched <= ts < discontinued) | hard | PASS | 0 |
| dates | product discontinued_at > launched_at | hard | PASS | 0 |
| dates | experiment created <= start < end | hard | PASS | 0 |
| dates | assignment within experiment window | hard | PASS | 0 |
| rules | no assignments for draft experiments | hard | PASS | 0 |
| rules | assignment channel eligible | hard | PASS | 0 |
| rules | variant sticky per (experiment, device) | hard | PASS | 0 |
| dates | cart checkout_started_at >= created_at | hard | PASS | 0 |
| dates | cart_item removed_at >= added_at | hard | PASS | 0 |
| dates | order_ts >= cart.created_at | hard | PASS | 0 |
| consistency | order.session_id = cart.session_id | hard | PASS | 0 |
| dates | order_ts within its session | hard | PASS | 0 |
| dates | ticket opened <= first_response <= escalated <= resolved <= closed | hard | PASS | 0 |
| dates | ticket opened_at = first contact session start | hard | PASS | 0 |
| dates | ticket opened after origin session start | hard | PASS | 0 |
| dates | status_history changed_at <= snapshot | hard | PASS | 0 |
| dates | device last_seen >= first_seen | hard | PASS | 0 |
| arithmetic | order_line.line_amount = quantity*unit_price | hard | PASS | 0 |
| arithmetic | order.subtotal = sum(order_line.line_amount) | hard | PASS | 0 |
| arithmetic | order.item_count = sum(order_line.quantity) | hard | PASS | 0 |
| arithmetic | order_line.line_no contiguous 1..n | hard | PASS | 0 |
| arithmetic | order.total = subtotal - discount + tax + shipping_fee | hard | PASS | 0 |
| arithmetic | order.tax = round((subtotal-discount)*country_rate, 2) | hard | PASS | 0 |
| arithmetic | shipping_fee rule (0 if net >= 50 else 4.99) | hard | PASS | 0 |
| arithmetic | discount is 0 or 10% of subtotal | hard | PASS | 0 |
| arithmetic | cart.subtotal = sum(active cart_item.line_amount) | hard | PASS | 0 |
| arithmetic | cart.item_count = sum(active quantity) | hard | PASS | 0 |
| arithmetic | cart_item.line_amount = quantity*unit_price | hard | PASS | 0 |
| arithmetic | cart_item.unit_price = product.list_price | hard | PASS | 0 |
| arithmetic | cart_item.is_active = removed_at is null | hard | PASS | 0 |
| arithmetic | cart_item.quantity = sum(add_to_cart.quantity) within the line's lifetime | hard | PASS | 0 |
| unique | at most one active cart_item per (cart, product) | hard | PASS | 0 |
| arithmetic | order lines = active cart items (product, qty) | hard | PASS | 0 |
| arithmetic | purchase.value = order.total | hard | PASS | 0 |
| arithmetic | cart event value = quantity*list_price | hard | PASS | 0 |
| arithmetic | ticket.csat_score = csat_submitted.value | hard | PASS | 0 |
| lifecycle | status transitions allowed | hard | PASS | 0 |
| lifecycle | status chain continuous (from = previous to) | hard | PASS | 0 |
| lifecycle | status changes chronological | hard | PASS | 0 |
| lifecycle | cart.status = last status_history | hard | PASS | 0 |
| lifecycle | order.status = last status_history | hard | PASS | 0 |
| lifecycle | support_ticket.status = last status_history | hard | PASS | 0 |
| lifecycle | experiment.status = last status_history | hard | PASS | 0 |
| lifecycle | product.status = last status_history | hard | PASS | 0 |
| lifecycle | converted carts have exactly one order | hard | PASS | 0 |
| derived | customer.analytics_consent_status derived from consent_event | hard | PASS | 0 |
| derived | customer.marketing_consent_status derived from consent_event | hard | PASS | 0 |
| rules | email/push traffic only for persons with marketing consent (vs. truth person) | hard | PASS | 0 |
| rules | web/app: no within-session gap > 30 min (event_ts) | hard | PASS | 0 |
| rules | web/app sessions of a device separated by > 30 min | hard | PASS | 0 |
| rules | browser null iff app | hard | PASS | 0 |
| rules | app_version only on app sessions | hard | PASS | 0 |
| rules | login links have confidence 1.0 | hard | PASS | 0 |
| rules | support sessions reference a ticket | hard | PASS | 0 |
| rules | ticket priority rule | hard | PASS | 0 |
| derived | journey_outcome 1:1 with session | hard | PASS | 0 |
| derived | outcome_id = 'OUT-' + session_id | hard | PASS | 0 |
| derived | converted outcome has an order | hard | PASS | 0 |
| derived | valid_event_count <= session.event_count | hard | PASS | 0 |
| derived | deduplicated conversions = orders (no double counting) | hard | PASS | 0 |
| labelled | duplicate client_event_id rows are all labelled (and vice versa) | labelled | PASS | 0 |
| labelled | orders with >1 purchase event are all labelled (and vice versa) | labelled | PASS | 0 |
| labelled | sessions with ingestion/occurrence inversion (excl. labelled duplicates) are all labelled (and vice versa) | labelled | PASS | 0 |
| labelled | every anomaly references an existing entity | labelled | PASS | 0 |
| labelled | session_labels cover every session exactly once | labelled | PASS | 0 |
| leakage | no ground-truth columns in input tables | hard | PASS | 0 |
| leakage | no is_bot/actor flags in session table | hard | PASS | 0 |
