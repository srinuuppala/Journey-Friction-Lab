# Evaluation report (pipeline vs. ground truth)

| Area | Metric | Value |
|---|---|---|
| Deduplication | precision / recall | 1.0 / 1.0 (209/209) |
| Deduplication | raw purchase events → orders → conversions after dedup | 4387 → 4178 → 4178 (reconciled=True) |
| Ingestion order | inverted sessions flagged P/R | 1.0 / 1.0 (1696 labelled) |
| Ingestion order | share of inverted sessions whose last-3-step path is wrong if ordered by arrival | 0.8886 |
| Late arrival | flagged P/R | 0.9995 / 1.0 |
| Sessionization | match rate using event_ts | 1.0 |
| Sessionization | match rate if (wrongly) using ingestion_ts | 0.975367 |
| Bots | precision / recall / F1 | 0.9859 / 0.9702 / 0.978 |
| Bots | recall by type | cart_bot=1.0, cookie_replay=1.0, declared_crawler=1.0, disguised_scraper=1.0, stealth_scraper=0.7432 |
| Bots | human false-positive rate | 0.00088 |
| Identity links | bogus-link rejection P/R | 0.6053 / 0.9266 (770/831) |
| Stitching | consent violations (events) | 0 (naive: 232188) |
| Stitching | sessions stitched to wrong customer | 85 (naive: 1390) |
| Stitching | sessions matching expected identity | 0.9968 |
| Outcomes | accuracy vs expected | 1.0 (naive without dedup: 0.99999) |
| Funnel | conversion rate naive → clean | 0.04462 → 0.045206 |
| Funnel | funnel_metrics sha256 | `d9dd5c9ce6eb4c88…` |
| Incidents | detected | 4/4 (unmatched alerts: 0) |
| Incidents | INC-2026-001 | detected=True window=2026-05-14..2026-06-18 root cause=app_version=5.2.0 (expected app_version=5.2.0) |
| Incidents | INC-2026-002 | detected=True window=2026-08-06..2026-09-03 root cause=geo_country=GB (expected geo_country=['DE', 'GB']) |
| Incidents | INC-2026-003 | detected=True window=2026-07-02..2026-07-23 root cause=None (expected None) |
| Incidents | INC-2026-004 | detected=True window=2026-03-19..2026-05-14 root cause=os=Android 13 (expected os=Android 13) |
| Cross-channel | abandoned-checkout recovery within 7 days (true vs observed) | 0.0405 vs 0.0326 (identity/consent limited) |
| Experiments | one_page_checkout | detected (lift=0.06955, p=0.004011) |
| Experiments | recommendation_carousel | detected (lift=0.04076, p=0.0) |
| Experiments | free_shipping_banner | detected (lift=0.03538, p=0.010682) |
| Experiments | app_onboarding_v2 | correct_null (lift=0.02433, p=0.210838) |
| Experiments | search_autocomplete | detected (lift=0.07117, p=0.0) |
| Experiments | guest_checkout_express | no_traffic_as_expected (lift=nan, p=nan) |
