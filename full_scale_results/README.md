# Full-scale results (scale 1.0, seed 20261022)

Reports from the full 100,000-session / 2,039,088-event run. Regenerate the full dataset with:

    python -m journeylab generate --scale 1.0 --seed 20261022 --out output/full

Your `output/full/manifest.json` checksums will match `manifest.json` here.

| File | What it shows |
|---|---|
| `reports/validation_summary.md` | 438/438 data-quality checks pass |
| `reports/evaluation_report.md` | pipeline vs. ground truth (dedup, bots, consent, incidents, experiments) |
| `reports/reproducibility_report.md` | two independent runs: 64/64 files identical |
| `reports/sqlite_check_from_csv.json` | 0 foreign-key violations after loading into SQLite |
| `derived/*.csv` | funnel metrics, friction steps/paths/impact, incident alerts, experiment readout, … |
