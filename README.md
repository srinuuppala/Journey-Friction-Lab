# Journey Friction Lab

An end-to-end analytics project that finds **where customers drop off and which steps cost the most orders**, using messy cross-channel data (web, app, support, purchases).

**The problem:** Real event data is dirty. Events arrive late and out of order, purchases are double-counted, bots look like customers, and identity matching can break privacy rules. If you don't fix these first, funnel numbers are wrong and teams chase the wrong problems.

**What I built:**

1. **A seeded data generator**: 100,000 sessions and ~2M events, with known data-quality problems injected and recorded in a separate answer key (ground truth).
2. **An analytics pipeline** that cleans the data and produces trustworthy funnel, friction and experiment metrics.
3. **An evaluation** that scores the pipeline against the answer key, so every claim is measurable.
4. **A dashboard** (static HTML/CSS/JS, no build step) that shows the results.

Everything is reproducible from one command and one seed (`20261022`). All data is synthetic, so there is no personal data.

---

## Results (full scale)

| Area | Result |
|---|---|
| Duplicate purchases | Precision 1.00 / recall 1.00 (209/209). 4,387 raw purchase events → 4,178 real orders |
| Out-of-order events | 1,696/1,696 sessions detected and re-ordered. Trusting arrival order gets the last 3 steps wrong in 89% of them |
| Bot detection | Precision 0.986 / recall 0.970. Only 0.09% of humans flagged |
| Identity stitching | **0 consent violations** (a naive approach had 232k). Wrong-customer sessions: 85 vs 1,390 naive |
| Bad identity links | 92.7% rejected (deliberately conservative) |
| Broken-step detection | **4/4 hidden incidents found**, correct root cause, 0 false alerts |
| A/B experiments | 4/4 real effects detected, null experiment correctly null |
| Data validation | 438/438 checks pass |
| Reproducibility | Two runs, same seed: 64/64 files identical (SHA-256) |

**Funnel** (non-bot web + app sessions, overall conversion 4.5%):

| Stage | Sessions | Step conversion |
|---|---:|---:|
| visit | 92,421 | n/a |
| product_view | 70,021 | 75.8% |
| add_to_cart | 19,154 | 27.4% |
| checkout_start | 5,314 | 27.7% |
| payment_submitted | 4,299 | 80.9% |
| purchase | 4,178 | 97.2% |

**Biggest friction points found** (lost orders):

* App payment-gateway timeouts: ~49 lost orders, a 73-point conversion gap, and 18% of affected sessions contacted support.
* Web address-validation failures: ~42 lost orders.
* Declined / 3-D Secure failures on web: ~55 lost orders combined.

---

## Quick start

```bash
pip install -r requirements.txt                 # numpy, pandas, pytest (Python >= 3.10)
python -m pytest -q                             # 28 tests, ~20 s

# small dataset (5k sessions), ~15 s
python -m journeylab generate --scale 0.05 --out output/starter --sqlite --force

# full dataset (100k sessions, ~2M events), ~3 min
python -m journeylab generate --scale 1.0 --out output/full --sqlite --force

# dashboard (data for the full run is already included in web/data/)
python -m journeylab serve                      # http://localhost:8000
```

Other useful commands:

| Command | Purpose |
|---|---|
| `python -m journeylab validate --data output/full` | Re-run all 438 checks from the exported files |
| `python -m journeylab reproduce --scale 1.0 --out output/repro_full` | Generate twice and compare SHA-256 of every file |
| `python -m journeylab analyze --data output/full` | Re-run the pipeline from CSVs and prove metrics are identical |

---

## How it works

### 1. Data generator
* Builds master data first (customers, consent history, devices, products, experiments), then simulates sessions as a state machine, so every record has a valid parent ID.
* Creates a clean baseline, then injects **labelled** problems. Unrelated rows are never touched.
* Writes the answer key to `ground_truth/`. It is never used as pipeline input.

**Tables (19):** customers, consent events, devices, identity links, sessions, journey events, pages, products, carts, orders, support tickets, experiments, status history, journey outcomes, and more. Full schema (PK/FK, types, rules) is in [docs/data_dictionary.md](docs/data_dictionary.md).

### 2. Injected data problems

| Problem | How it was injected | Count |
|---|---|---:|
| Events ordered by arrival, not occurrence | Offline/retry blocks delivered 20 min to 6 h late | 1,696 sessions |
| Wrong identity merges | Heuristic links to the wrong customer or device | 831 links |
| Conversion counted twice | SDK retry, page reload, re-fire in a later session | 209 events |
| Bots mixed with customers | Crawlers, disguised scrapers, cart-hoarders, cookie-replay bots | 6,000 sessions |
| Delayed events | Tail events ingested 1 to 12 h late | 1,367 sessions |

It also covers anonymous journeys (69%), guest checkouts, consent gaps, shared devices, four hidden incidents (broken steps / latency), and six experiments (one null, one stopped early, one draft).

### 3. Analytics pipeline (`pipeline.py`)
* **Deduplication:** same `client_event_id` keeps the first arrival. One `purchase` per `order_id`.
* **Re-sequencing:** always orders by event time, not arrival time.
* **Sessionization:** 30-minute inactivity rule per device and channel.
* **Bot detection:** scoring on behaviour and device signals.
* **Identity stitching:** links events to customers only when **analytics consent is active at that event's timestamp**. Bots are never stitched.
* **Outcomes:** each session gets one outcome (converted, abandoned checkout, abandoned cart, bounced, browsed, support resolved/unresolved) by fixed rules.
* **Analytics:** funnels, friction paths and impact, broken-step alerts, experiment readouts with 95% confidence intervals, cross-channel journeys.

### 4. Dashboard (`web/`)
Static site with pages for Overview, Funnel, Friction, Broken steps, Experiments, Data quality and a Journey explorer (96 example visits, event by event, with the pipeline's decision next to the answer key). Python pre-computes two small JSON files, so no server is needed.

---

## Design decisions worth noting

* **Ground truth separate from inputs.** This lets me measure precision and recall instead of just claiming the pipeline works. A test also checks there is no leakage.
* **Consent-first identity stitching.** Privacy rules are enforced in the logic and tested (0 violations), not left as an afterthought.
* **Conservative identity merging.** The pipeline prefers missing a merge over making a wrong one.
* **Determinism.** Seeded RNGs, CRC32 bucketing (not Python `hash`), stable sorts, and no timestamps in checksummed files.
* **Single source of truth for schema.** `schema.py` drives validation, the data dictionary and SQL DDL, so they cannot drift apart.

---

## Testing

28 pytest tests run on a 2,000-session dataset and check:

* Dedup works (dropped rows = labelled duplicates; conversions = orders).
* Same seed gives identical funnel metrics, including when recomputed from exported CSVs.
* Identity stitching never uses events without active consent.
* Data quality: PK/FK integrity, derived totals reconcile, valid status transitions, and all edge cases are present and labelled.
* Exports are byte-identical for the same seed, and SQLite foreign keys pass.

---

## Project layout

```
journeylab/
  config.py      seed, scale, reference data, incidents (ground truth)
  taxonomy.py    event taxonomy, funnel stages, outcome rules
  schema.py      single source of truth for fields, types, keys
  simulate.py    baseline world simulation
  inject.py      labelled edge cases (bots, reordering, duplicates, bad merges)
  finalize.py    IDs, derived values, ground-truth labels
  generate.py    orchestration
  pipeline.py    dedup, resequencing, bots, identity, funnel, friction, experiments
  validate.py    438 validation checks
  evaluate.py    pipeline vs ground truth
  export.py      CSV / JSONL / SQL, manifest, SQLite FK check
  dashboard.py   builds web/data/*.json
web/             dashboard (HTML, CSS, JS)
tests/           28 tests
docs/            methodology.md, data_dictionary.md
```

Full definitions of sessions, funnel, outcomes and dedup rules are in [docs/methodology.md](docs/methodology.md).

---

## Limitations

* Behaviour is simulated. Effect sizes are chosen to be realistic but detectable at full scale. At starter scale (5k sessions), incidents and experiments are too small to detect.
* Cross-device recovery is only visible when identity is stitched with consent (observed 3.3% vs true 4.1%).
* Stealth-scraper bot recall is lower (0.74) than other bot types.
