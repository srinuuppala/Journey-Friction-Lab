# Journey Friction Lab

This project connects **web, app, support and purchase events** to find **journey drop-offs and high-friction paths**.
It has two parts:

1. **A seeded synthetic-data generator.** It produces 100,000 sessions and about 2M cross-channel events
   (customers, sessions, events, pages, products, carts, orders, support tickets, experiments, outcomes).
   It injects labelled edge cases and writes a separate ground truth.
2. **An analytics pipeline.** It turns the raw, messy event stream into trustworthy metrics:
   * deduplication and resequencing by event time
   * consent-aware identity stitching
   * bot detection
   * journey outcomes and funnels
   * friction paths and broken-step alerts
   * experiment readouts and cross-channel journeys

   The pipeline is **scored against the ground truth**.

Everything is reproducible from one command and one seed (`20261022`). A **web dashboard** (`web/`) shows the
results. It is a static site that you can host for free on Vercel or GitHub Pages.

> 📘 **New to the project?** Read `docs/Journey_Friction_Lab_Student_Guide.pdf`. It explains every file in simple
> words and walks you through running, pushing to GitHub and hosting online, step by step.

---

## Quick start

```bash
pip install -r requirements.txt            # numpy, pandas, pytest (Python >= 3.10)

python -m pytest -q                        # 28 tests, ~20 s

# starter dataset: 5k sessions / ~100k events, all formats + SQLite FK check (~15 s)
python -m journeylab generate --scale 0.05 --out output/starter --sqlite --force

# full dataset: 100k sessions / ~2.04M events (~3 min, ~1.9 GB with CSV+JSONL+SQL)
python -m journeylab generate --scale 1.0 --out output/full --sqlite --force

# reproducibility: generate twice with the same seed, compare row counts + SHA-256 of every file
python -m journeylab reproduce --scale 1.0 --out output/repro_full

# dashboard (frontend): build its data from a dataset, then open it at http://localhost:8000
python -m journeylab dashboard --data output/full --web web
python -m journeylab serve
```

The repository already includes dashboard data built from the full-scale run (`web/data/`). So
`python -m journeylab serve` works straight after cloning, with no generation needed.

## Frontend (dashboard)

`web/` is a static website: HTML, CSS and JavaScript, with no build step and no libraries. Its pages are:

| Page | Shows |
|---|---|
| Overview | key numbers, how the project works, whether the 4 hidden broken steps were found |
| Funnel | visit → purchase funnel (all / web / app), monthly conversion, conversion by traffic source |
| Friction | which errors cost the most orders, exit rate per page, last steps before abandoning |
| Broken steps | weekly error-rate charts with the hidden incident shaded, plus every alert raised |
| Experiments | A/B test lifts with 95% confidence ranges, checked against the answer key |
| Data quality | duplicates, out-of-order events, consent, bots, identity links, the 438 validation checks |
| Journey explorer | 96 example visits, event by event, with the pipeline's decision next to the answer key |

Python can't run on a free static host, so `journeylab/dashboard.py` pre-computes everything into two small
JSON files: `web/data/dashboard.json` (~50 KB) and `web/data/sessions.json` (~1 MB).

More commands:

| Command | What it does |
|---|---|
| `python -m journeylab validate --data output/full` | re-runs all 438 validation checks **from the exported files** |
| `python -m journeylab analyze --data output/full` | re-runs the pipeline from CSVs and proves the funnel and drop-off metrics are identical |
| `python -m journeylab sqlite --data output/full --db full.sqlite` | loads every CSV into SQLite with `PRAGMA foreign_keys=ON`, then runs `foreign_key_check` and join checks |
| `python -m journeylab dashboard --data output/full --web web` | builds the website's data files from a dataset |
| `python -m journeylab serve` | opens the dashboard at http://localhost:8000 (Ctrl+C to stop) |
| `python -m journeylab docs` | regenerates `docs/data_dictionary.md` and `sql/schema.sql` from `journeylab/schema.py` |
| `make test / starter / full / reproduce / reproduce-full` | shortcuts for the commands above |

Options: `--seed N` (default 20261022), `--scale X` (1.0 = 100k sessions), `--formats csv,json,sql`.
Starter and full datasets come from **the same generator**; only `--scale` changes.

---

## What gets produced

```
<out>/
  data/            19 input tables, as .csv and .jsonl (JSON Lines)
  ground_truth/    anomalies.csv, session_labels.csv, expected_findings.json   <- never used as inputs
  derived/         pipeline outputs: funnel_metrics, friction_steps, friction_paths, friction_impact,
                   incident_alerts, experiment_readout, cross_channel_paths, bot_scores,
                   identity_link_review, stitched_sessions, dedup_decisions, resequenced_sessions, ...
  sql/             schema.sql (PK/FK/CHECK DDL), seed.sql (INSERTs), load_csv_postgres.sql (\copy for big tables)
  reports/         validation_summary.{md,json}, evaluation_report.{md,json}
  manifest.json    seed, scale, generator command, versions, provenance, rows + SHA-256 of every file
```

### Entities (full scale, seed 20261022)

| Table | Rows | Key | Notes |
|---|---:|---|---|
| customer | 20,000 | `CUS-000001` | segment, country, consent status derived from history |
| consent_event | 43,515 | `CNS-0000001` | append-only, effective-dated (granted / denied / withdrawn / expired) |
| device | 46,937 | `DEV-0000001` + `ANO-…` | browser or app install; anonymous_id = cookie/install id |
| identity_link | 10,046 | `IDL-0000001` | bridge Customer N:M Device (login, email_click, probabilistic, cookie_sync) |
| session | 100,000 | `SES-2026-000001` | web 71%, app 27%, support 2% |
| journey_event | 2,039,088 | `EVT-<session-id>-000001` | `event_ts` + `ingestion_ts`, 29 event types |
| page / product | 42 / 1,500 | `PAG-0001` / `PRD-000001` | page templates, products with launch/discontinue dates |
| cart / cart_item | 20,086 / 36,470 | `CRT-2026-000001` | cart_item = bridge Cart N:M Product |
| order / order_line | 4,178 / 4,734 | `ORD-2026-000001` | 1:1 with converted cart; totals derived from lines |
| support_ticket / support_agent | 1,322 / 40 | `TCK-2026-000001` | contacts are `support` sessions |
| experiment / experiment_assignment | 6 / 111,792 | `EXP-2026-000001` | bridge Experiment N:M Session, sticky per device |
| status_history | 70,234 | `STH-00000001` | every cart/order/ticket/experiment/product state change |
| journey_outcome | 100,000 | `OUT-<session-id>` | derived per session by rules R1–R8 |
| event_taxonomy | 29 | event_type | the event contract |

All PKs, FKs, cardinalities (1:1, 1:N, N:M via bridges), optional relationships, effective dates, lifecycle state
machines and per-field type/required/enum/unit/uniqueness/validation rules are in
**[docs/data_dictionary.md](docs/data_dictionary.md)**. Session, funnel, outcome, dedup, identity/consent rules and
the generation logic are in **[docs/methodology.md](docs/methodology.md)**.

---

## Key definitions (summary)

* **Sessionization:** web/app sessions follow a 30-minute inactivity rule per `(device, channel)` on `event_ts`.
  A support session is one CRM contact per ticket.
* **Funnel:** `visit → product_view → add_to_cart → checkout_start → payment_submitted → purchase`. The
  furthest stage is the max stage of deduplicated events.
* **Outcomes:** R1 `converted` → R2/R3 support resolved/unresolved → R4 `abandoned_checkout` →
  R5 `abandoned_cart` → R6 `bounced` → R7 `browsed_product` → R8 `browsed_no_product`.
* **Dedup:**
  * D1: same `client_event_id`, keep the first arrival.
  * D2: one `purchase` per `order_id` across all sessions.
* **Ordering:** `event_id` counters follow *arrival* order. Analysis always orders by `event_ts`.
* **Identity stitching:**
  * R-ID-1: authenticated event.
  * R-ID-2: same-session backfill.
  * R-ID-3: accepted device link.

  Each is applied **only when analytics consent is active at the event's timestamp**. Bots are never stitched.

---

## Labelled edge cases (ground truth: `ground_truth/anomalies.csv`)

| Required edge case | Injected as | Full-scale count |
|---|---|---:|
| Events ordered by ingestion rather than occurrence | blocks of app/web events delivered 20 min–6 h late (offline flush / beacon retry), so arrival order ≠ event order | 1,696 sessions |
| Anonymous IDs incorrectly merged | heuristic identity links from anonymous devices, or other customers' devices, to the wrong customer | 831 links |
| Conversion counted twice | duplicate `purchase` via SDK retry (same key), page reload (new key), re-fire in a later session | 209 events |
| Bot traffic mixed with customer behavior | declared crawlers, disguised and stealth scrapers, cart-hoarding bots, **cookie-replay bots on real customers' devices** | 6,000 sessions |
| (coverage) delayed events | tail events ingested 1–12 h after the watermark | 1,367 sessions |

The baseline also covers:

* **Anonymous journeys:** 69% of web/app sessions.
* **Guest checkouts.**
* **Consent gaps:** no record (`unknown`), denied, withdrawn, and expired at the v2 policy change.
* **Multiple devices per customer and shared household devices.**
* **Broken steps and latency:** four incidents. These are documented in `expected_findings.json` only and never
  appear in the inputs.
* **Six experiments:** one with a null effect, one stopped early, one draft.
* **Return-to-buy journeys:** often on another device or channel, after abandonment or a support contact.

---

## Results at full scale (seed 20261022)

**Validation:** 438 / 438 checks pass. This covers:

* PK uniqueness and FK integrity (also `PRAGMA foreign_key_check` = 0 in SQLite)
* enums and ID formats
* date ordering
* arithmetic reconciliation (lines → order totals, tax/shipping rules, cart totals, purchase value = order total)
* lifecycle transitions and status chains
* consent and email rules
* the 30-minute rule
* labelled-anomaly reconciliation (every irregularity is labelled, and nothing unlabelled was corrupted)
* no ground-truth leakage

**Reproducibility:** two full runs with the same seed produced **64/64 files identical** (row counts and SHA-256).
See `reports/reproducibility_report.md`.

**Pipeline vs ground truth** (`reports/evaluation_report.md`):

| Area | Result |
|---|---|
| Event deduplication | precision 1.00 / recall 1.00 (209/209). 4,387 raw purchase events → 4,178 orders = 4,178 conversions |
| Ingestion-order inversions | 1,696/1,696 flagged and resequenced. Trusting arrival order gets the last 3 steps wrong in 89% of those sessions |
| Sessionization | 100% match with event time. Ordering by ingestion time would break 2.5% of sessions |
| Bot detection | precision 0.986 / recall 0.970. Cookie-replay 1.00, stealth scrapers 0.74. Humans flagged: 0.09% |
| Incorrect identity merges | 92.7% of bad links rejected (precision 0.61: conservative by design) |
| Identity stitching | **0 consent violations** (naive: 232k events). Wrong-customer sessions 85 (naive: 1,390) |
| Journey outcomes | 100% match with rule-derived ground truth |
| Broken steps | **4/4 incidents detected, correct root cause, 0 false alerts** |
| Experiments | 4/4 real effects detected (p < 0.05), null experiment correctly null, draft has no traffic |

**Funnel** (non-bot web+app):

| Stage | Sessions | Step conversion |
|---|---:|---:|
| visit | 92,421 | — |
| product_view | 70,021 | 75.8% |
| add_to_cart | 19,154 | 27.4% |
| checkout_start | 5,314 | 27.7% |
| payment_submitted | 4,299 | 80.9% |
| purchase | 4,178 | 97.2% |

Overall conversion is 4.5%.

**Highest-friction steps** (`derived/friction_impact.csv`):

* App payment-gateway timeouts: about 49 lost orders, a 73 pp conversion gap, and 18% of affected sessions contacted support.
* Web address-validation failures: about 42 lost orders.
* Declined / 3-D Secure failures on web: about 55 lost orders combined.

---

## How the generator works

1. **Master data first:** customers, consent history, devices, products, pages, experiments, agents.
2. **Transactions:** each web/app session runs a state machine over page types. Its dependent records (carts,
   items, orders, lines, tickets) are created by the actions themselves, so every reference uses a valid parent ID.
3. **History, not overwrites:** state changes become rows in `status_history` / `consent_event`. Current statuses
   are derived from them.
4. **Valid baseline first, then labelled injections.** Unrelated rows are never touched.
5. **Derived values** are computed from source records: totals, counts, session start/end, consent status,
   lifecycle status, device first/last seen, outcomes.
6. **Ground truth comes from rules, not random labels.** `expected_outcome` applies rules R1–R8 to the clean
   baseline. `expected_stitched_customer_id` uses only true links, true bot labels and consent history.
7. **Validate, export, record the manifest.** IDs are assigned once, deterministically and chronologically, after
   injection.

Determinism: Python `random.Random(seed)` and `numpy.default_rng(seed + k)`, CRC32 (not Python `hash`) for
experiment bucketing, stable sorts everywhere, and no wall-clock data in checksummed files.

---

## Project layout

```
journeylab/
  config.py      seed, scale, calendar, reference data, experiments, incidents (ground truth)
  taxonomy.py    event taxonomy, funnel stages, page catalogue, outcome rules
  schema.py      single source of truth: fields, types, enums, PK/FK -> validation, dictionary, DDL
  simulate.py    baseline world simulation (master data -> sessions -> events -> carts/orders/tickets)
  inject.py      labelled edge cases (bots, ingestion reordering, late arrivals, duplicates, bad merges)
  finalize.py    deterministic public IDs, derived values, tables, ground-truth label frames
  generate.py    orchestration + rule-derived ground truth
  pipeline.py    P1 dedup … P8 funnel/friction/incident/experiment/cross-channel analytics
  validate.py    438 checks (PK, FK, enums, formats, dates, arithmetic, lifecycle, labels, leakage)
  evaluate.py    pipeline vs ground truth
  export.py      CSV / JSONL / SQL, manifest, loader, SQLite FK check
  dashboard.py   builds web/data/*.json for the website
  cli.py         command line
web/             the dashboard website (index.html, app.js, charts.js, styles.css, data/)
tests/           28 pytest tests (generation + acceptance criteria + dashboard)
docs/            Student Guide (PDF), methodology.md, data_dictionary.md
.github/         GitHub Actions: run tests on every push; optional GitHub Pages deploy
sql/schema.sql   DDL with primary/foreign keys and CHECK constraints
```

## Tests

`python -m pytest -q` (28 tests) builds a 2,000-session dataset with the same generator and checks:

* **Acceptance criteria:**
  * session and funnel definitions are documented
  * event deduplication works (dropped rows = labelled duplicates; conversions = orders)
  * drop-off metrics are reproducible (same seed → identical funnel hash, also when re-computed from exported CSVs; a different seed → different)
  * identity stitching respects consent (0 events stitched without active consent; customers with no consent record and detected bots never stitched; naive approach would violate)
* **Data quality:** ID conventions, PK/FK and join completeness, derived-value reconciliation, append-only
  history, lifecycle validity, presence and labelling of every required edge case, scenario coverage, ground-truth
  separation and no leakage, labels derived from rules, schema/dictionary consistency.
* **Reproducibility and exports:** same-seed checksum equality of all exported files (CSV/JSON/SQL), SQLite FK
  enforcement, manifest provenance.

## Data provenance and lawful use

No external data was used. Everything is produced by the seeded simulator. There is no personal data: customer
IDs, e-mail hashes, IP hashes and anonymous IDs are synthetic tokens. Product names and brands are invented. The
schema is inspired only by generic e-commerce analytics concepts. `manifest.json` records the provenance, an
empty external-source list, the generator command, the seed and library versions. The generated data may be
freely used and redistributed.

## Limitations

* Behaviour is simulated. Effect sizes and incident magnitudes are chosen to be realistic yet detectable at full
  scale. At starter scale (5k sessions), incidents and experiments are too small to detect, which is expected.
* Cross-device recovery is only observable when identity is stitched with consent. The evaluation reports the
  true recovery rate (4.1%) next to the observed one (3.3%).
* Identity-link review is deliberately conservative: it prefers missing a merge over making a wrong one.
