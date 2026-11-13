# Reproducibility report

Two independent runs with seed `20261022` and scale `1.0`.

**All 64 files identical (row counts and SHA-256): True**

| File | Rows (run A) | Rows (run B) | SHA-256 (first 16) | Identical |
|---|---|---|---|---|
| data/cart.csv | 20086 | 20086 | `b80cc63b52700d91` | True |
| data/cart.jsonl | 20086 | 20086 | `3420cd666cc44530` | True |
| data/cart_item.csv | 36470 | 36470 | `d3ba6fd25c1e3345` | True |
| data/cart_item.jsonl | 36470 | 36470 | `2cd8ae9e12f84a32` | True |
| data/consent_event.csv | 43515 | 43515 | `42c3c80723d900c2` | True |
| data/consent_event.jsonl | 43515 | 43515 | `3eb2ead5b2946fdf` | True |
| data/customer.csv | 20000 | 20000 | `49f691c79e2cfcdd` | True |
| data/customer.jsonl | 20000 | 20000 | `83fdb49d1d34b3a5` | True |
| data/device.csv | 46937 | 46937 | `c1eaaa364a79836e` | True |
| data/device.jsonl | 46937 | 46937 | `a8d3a20313e48d2e` | True |
| data/event_taxonomy.csv | 29 | 29 | `a2cdc83e2bbbea12` | True |
| data/event_taxonomy.jsonl | 29 | 29 | `c9afa2663ae03bac` | True |
| data/experiment.csv | 6 | 6 | `c80703fc64adc091` | True |
| data/experiment.jsonl | 6 | 6 | `3723a8ecbbb7bc82` | True |
| data/experiment_assignment.csv | 111792 | 111792 | `6d98ad8aaf3179d8` | True |
| data/experiment_assignment.jsonl | 111792 | 111792 | `593538dc47b11922` | True |
| data/identity_link.csv | 10046 | 10046 | `3377bc8de3107dfc` | True |
| data/identity_link.jsonl | 10046 | 10046 | `be3fc742c409d8fa` | True |
| data/journey_event.csv | 2039088 | 2039088 | `d7fb551957558013` | True |
| data/journey_event.jsonl | 2039088 | 2039088 | `3b7c335ea71490d3` | True |
| data/journey_outcome.csv | 100000 | 100000 | `7d31d0c7b43baba2` | True |
| data/journey_outcome.jsonl | 100000 | 100000 | `05515ca76b01a83b` | True |
| data/order.csv | 4178 | 4178 | `ee7c382109e3afc8` | True |
| data/order.jsonl | 4178 | 4178 | `ed49025e0f4707ef` | True |
| data/order_line.csv | 4734 | 4734 | `bb755b5c2b099e60` | True |
| data/order_line.jsonl | 4734 | 4734 | `4ac3bd7c702a36a6` | True |
| data/page.csv | 42 | 42 | `ebe5cca4d4a52c61` | True |
| data/page.jsonl | 42 | 42 | `932a3367ef5e51ea` | True |
| data/product.csv | 1500 | 1500 | `9aa70e1f2735ab6a` | True |
| data/product.jsonl | 1500 | 1500 | `54e517c42fd35532` | True |
| data/session.csv | 100000 | 100000 | `a9f185b5b211bb9a` | True |
| data/session.jsonl | 100000 | 100000 | `45ea07a10deacb24` | True |
| data/status_history.csv | 70234 | 70234 | `7317ebea778b0939` | True |
| data/status_history.jsonl | 70234 | 70234 | `da88a61914d3ccf4` | True |
| data/support_agent.csv | 40 | 40 | `b028cb5843357809` | True |
| data/support_agent.jsonl | 40 | 40 | `b2ed2649cd90a8d9` | True |
| data/support_ticket.csv | 1322 | 1322 | `f2d0dabcdad9b5e8` | True |
| data/support_ticket.jsonl | 1322 | 1322 | `9ec893cba9e44b43` | True |
| derived/bot_scores.csv | 98325 | 98325 | `e056c3ccb5a028e9` | True |
| derived/cross_channel_paths.csv | 60 | 60 | `a5be158181a4a91a` | True |
| derived/cross_channel_summary.json | None | None | `24968935fad5d0a2` | True |
| derived/dedup_decisions.csv | 209 | 209 | `7fc80f8e37526b6c` | True |
| derived/experiment_readout.csv | 6 | 6 | `a19fc34f57a32e9b` | True |
| derived/friction_impact.csv | 12 | 12 | `166e96b01c01e1b0` | True |
| derived/friction_paths.csv | 201 | 201 | `32179003bcaabc90` | True |
| derived/friction_steps.csv | 20 | 20 | `615e0fac7aee1f61` | True |
| derived/funnel_metrics.csv | 246 | 246 | `d9dd5c9ce6eb4c88` | True |
| derived/identity_link_review.csv | 10046 | 10046 | `c6d256c87abcef87` | True |
| derived/incident_alerts.csv | 11 | 11 | `01dba361b0bfda9c` | True |
| derived/resequenced_sessions.csv | 3063 | 3063 | `4ff15968fba7bcde` | True |
| derived/sessionization_check.json | None | None | `e564fe6019ed1474` | True |
| derived/stitched_sessions.csv | 100000 | 100000 | `f93fabfff16435b0` | True |
| ground_truth/anomalies.csv | 10103 | 10103 | `1da6da5c989ea2c9` | True |
| ground_truth/anomalies.jsonl | 10103 | 10103 | `7c0465bb40fdd0ba` | True |
| ground_truth/expected_findings.json | None | None | `eb2f6eb6fb7ac0e6` | True |
| ground_truth/session_labels.csv | 100000 | 100000 | `b33ac369fcb9b1c8` | True |
| ground_truth/session_labels.jsonl | 100000 | 100000 | `ecdc87072bc7b684` | True |
| reports/evaluation_report.json | None | None | `4dd2be9249a6f06f` | True |
| reports/evaluation_report.md | None | None | `3851935b73219548` | True |
| reports/validation_summary.json | None | None | `ed9440362899b7c5` | True |
| reports/validation_summary.md | None | None | `9e2304bec15ebcc9` | True |
| sql/load_csv_postgres.sql | None | None | `60ff18c1de34a8ae` | True |
| sql/schema.sql | None | None | `829322e63c7716e7` | True |
| sql/seed.sql | None | None | `4230adde21b8ea82` | True |
