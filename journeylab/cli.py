"""Command-line interface:  python -m journeylab <command> [options]"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from . import config as C


def _reports(D, rep, E, sqlite_res=None):
    from .evaluate import evaluation_md
    vdf = rep.df()
    summary = dict(passed=bool(rep.ok), checks=int(len(vdf)), failed=int((vdf.status != "PASS").sum()),
                   by_category=vdf.groupby("category").status.apply(lambda s: f"{(s == 'PASS').sum()}/{len(s)} pass").to_dict(),
                   checks_detail=vdf.to_dict(orient="records"))
    if sqlite_res:
        summary["sqlite_fk_check"] = sqlite_res
    md = ["# Validation summary", "", f"**Result: {'PASS' if rep.ok else 'FAIL'}** — {summary['checks'] - summary['failed']}"
          f"/{summary['checks']} checks passed.", "",
          "Hard checks must report 0 violations. `labelled` checks prove every irregularity in the data is covered "
          "by a ground-truth label (and nothing unlabelled was corrupted).", "",
          "| Category | Check | Kind | Status | Violations |", "|---|---|---|---|---|"]
    for r in vdf.itertuples():
        md.append(f"| {r.category} | {r.check} | {r.kind} | {r.status} | {r.violations} |")
    if sqlite_res:
        md += ["", "## SQLite load with enforced foreign keys", "",
               f"- FK violations (`PRAGMA foreign_key_check`): **{sqlite_res['foreign_key_violations']}**",
               f"- Join completeness: **{sqlite_res['joins_complete']}** {sqlite_res['join_counts']}"]
    return {"validation_summary.json": summary, "validation_summary.md": "\n".join(md) + "\n",
            "evaluation_report.json": E, "evaluation_report.md": evaluation_md(E)}


def cmd_generate(a):
    from .export import export, sqlite_check
    from .evaluate import evaluate
    from .generate import build
    from .validate import validate
    cfg = C.GeneratorConfig(seed=a.seed, scale=a.scale)
    out = Path(a.out)
    if out.exists() and a.force:
        shutil.rmtree(out)
    t0 = time.time()
    print(f"[journeylab] generating scale={a.scale} seed={a.seed} -> {out}")
    D = build(cfg)
    rep = validate(D.tables, D.truth)
    print(f"  validation: {'PASS' if rep.ok else 'FAIL'} ({len(rep.rows)} checks) ({time.time() - t0:.1f}s)")
    E = evaluate(D.tables, D.truth, D.derived, D.expected_findings)
    D.derived.pop("events_clean", None)          # large intermediate, not exported
    import gc
    gc.collect()
    sq = None
    if a.sqlite:
        out.mkdir(parents=True, exist_ok=True)
        sq = sqlite_check(D.tables, out / "journeylab.sqlite")
        print(f"  sqlite FK violations: {sq['foreign_key_violations']}, joins complete: {sq['joins_complete']}")
    formats = tuple(x.strip() for x in a.formats.split(","))
    man = export(D, out, formats, _reports(D, rep, E, sq))
    run = dict(seconds=round(time.time() - t0, 1), sessions=len(D.tables["session"]),
               events=len(D.tables["journey_event"]))
    (out / "reports" / "run_log.json").write_text(json.dumps(run, indent=2) + "\n")
    if getattr(a, "web", None):
        from .dashboard import build_dashboard
        build_dashboard(out, Path(a.web))
        print(f"  dashboard data written to {a.web}/data/  ->  run: python -m journeylab serve --web {a.web}")
    print(f"  wrote {len(man['files'])} files; sessions={run['sessions']:,} events={run['events']:,} "
          f"in {run['seconds']}s")
    if not rep.ok:
        bad = rep.df()
        print(bad[bad.status != "PASS"].to_string())
        return 1
    return 0


def cmd_validate(a):
    from .export import load_tables, load_truth
    from .validate import validate
    d = Path(a.data)
    t = load_tables(d / "data")
    tr = load_truth(d / "ground_truth") if (d / "ground_truth").exists() else None
    rep = validate(t, tr)
    df = rep.df()
    print(df.groupby(["category", "status"]).size().to_string())
    if not rep.ok:
        print(df[df.status != "PASS"].to_string())
    print("RESULT:", "PASS" if rep.ok else "FAIL")
    return 0 if rep.ok else 1


def cmd_analyze(a):
    """Re-run the pipeline from exported CSVs and prove drop-off metrics are reproducible."""
    import pandas as pd
    from .evaluate import frame_hash
    from .export import load_tables
    from .pipeline import run_pipeline
    d = Path(a.data)
    t = load_tables(d / "data")
    res = run_pipeline(t)
    fm_new = res["funnel_metrics"]
    fm_old = pd.read_csv(d / "derived" / "funnel_metrics.csv")
    fm_new2 = pd.read_csv(pd.io.common.StringIO(fm_new.to_csv(index=False)))
    same = frame_hash(fm_new2) == frame_hash(fm_old)
    jo_old = pd.read_csv(d / "data" / "journey_outcome.csv", dtype=str)
    jo_same = (jo_old.outcome_type.tolist() == res["journey_outcome"].outcome_type.tolist())
    print(f"funnel_metrics identical to exported: {same}")
    print(f"journey_outcome identical to exported: {jo_same}")
    ov = fm_new[fm_new.segment_type == "overall"][["stage", "sessions_reached", "step_conversion", "drop_off_rate"]]
    print(ov.to_string(index=False))
    return 0 if (same and jo_same) else 1


def cmd_reproduce(a):
    from .export import sha256
    base = Path(a.out)
    if base.exists():
        shutil.rmtree(base)
    runs = []
    for tag in ("run_a", "run_b"):
        ns = argparse.Namespace(seed=a.seed, scale=a.scale, out=str(base / tag), formats=a.formats, sqlite=False, force=True,
                                web=None)
        rc = cmd_generate(ns)
        runs.append(json.loads((base / tag / "manifest.json").read_text()))
    fa = {f["path"]: f for f in runs[0]["files"]}
    fb = {f["path"]: f for f in runs[1]["files"]}
    rows = []
    for p in sorted(set(fa) | set(fb)):
        x, y = fa.get(p), fb.get(p)
        rows.append(dict(path=p, rows_a=x and x["rows"], rows_b=y and y["rows"], sha256_a=x and x["sha256"],
                         sha256_b=y and y["sha256"], identical=bool(x and y and x["sha256"] == y["sha256"])))
    ok = all(r["identical"] for r in rows)
    rep = dict(seed=a.seed, scale=a.scale, files_compared=len(rows), all_identical=ok, files=rows)
    (base / "reproducibility_report.json").write_text(json.dumps(rep, indent=2) + "\n")
    md = ["# Reproducibility report", "", f"Two independent runs with seed `{a.seed}` and scale `{a.scale}`.", "",
          f"**All {len(rows)} files identical (row counts and SHA-256): {ok}**", "",
          "| File | Rows (run A) | Rows (run B) | SHA-256 (first 16) | Identical |", "|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['path']} | {r['rows_a']} | {r['rows_b']} | `{(r['sha256_a'] or '')[:16]}` | {r['identical']} |")
    (base / "reproducibility_report.md").write_text("\n".join(md) + "\n")
    print(f"[journeylab] reproducibility: {len(rows)} files compared, all identical = {ok}")
    if not a.keep:
        for tag in ("run_b",):
            shutil.rmtree(base / tag)
    return 0 if ok else 1


def cmd_sqlite(a):
    from .export import load_tables, sqlite_check
    t = load_tables(Path(a.data) / "data")
    res = sqlite_check(t, Path(a.db))
    print(json.dumps(res, indent=2))
    return 0 if res["foreign_key_violations"] == 0 and res["joins_complete"] else 1


def cmd_dashboard(a):
    from .dashboard import build_dashboard
    d = build_dashboard(Path(a.data), Path(a.web))
    print(f"wrote {a.web}/data/dashboard.json and {a.web}/data/sessions.json "
          f"({d['kpis']['sessions']:,} sessions, {d['kpis']['events']:,} events)")
    return 0


def cmd_serve(a):
    import functools
    import http.server
    import socketserver
    import webbrowser
    web = Path(a.web).resolve()
    if not (web / "data" / "dashboard.json").exists():
        print(f"No dashboard data in {web / 'data'}. Run: python -m journeylab dashboard --data <dataset> --web {a.web}")
        return 1
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(web))
    url = f"http://localhost:{a.port}"
    with socketserver.TCPServer(("127.0.0.1", a.port), handler) as httpd:
        print(f"Dashboard running at {url}  (press Ctrl+C to stop)")
        if not a.no_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("stopped")
    return 0


def cmd_docs(a):
    from .schema import data_dictionary_md, ddl
    root = Path(a.root)
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "data_dictionary.md").write_text(data_dictionary_md(), encoding="utf-8")
    (root / "sql").mkdir(exist_ok=True)
    (root / "sql" / "schema.sql").write_text(ddl("sqlite"), encoding="utf-8")
    print("wrote docs/data_dictionary.md and sql/schema.sql")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="journeylab", description="Cross-channel journey friction lab")
    sp = p.add_subparsers(dest="cmd", required=True)
    g = sp.add_parser("generate", help="generate, validate, analyse and export a dataset")
    g.add_argument("--scale", type=float, default=1.0, help="1.0 = 100k sessions / ~2M events")
    g.add_argument("--seed", type=int, default=C.DEFAULT_SEED)
    g.add_argument("--out", default="output/full")
    g.add_argument("--formats", default="csv,json,sql")
    g.add_argument("--sqlite", action="store_true", help="also load into SQLite with FK enforcement")
    g.add_argument("--force", action="store_true", help="overwrite output dir")
    g.add_argument("--web", default=None, help="also build the dashboard data into this web folder (e.g. web)")
    g.set_defaults(fn=cmd_generate)
    v = sp.add_parser("validate", help="re-validate an exported dataset from its files")
    v.add_argument("--data", required=True)
    v.set_defaults(fn=cmd_validate)
    an = sp.add_parser("analyze", help="re-run the analytics pipeline from exported CSVs")
    an.add_argument("--data", required=True)
    an.set_defaults(fn=cmd_analyze)
    r = sp.add_parser("reproduce", help="generate twice with the same seed and compare checksums")
    r.add_argument("--scale", type=float, default=0.05)
    r.add_argument("--seed", type=int, default=C.DEFAULT_SEED)
    r.add_argument("--out", default="output/repro")
    r.add_argument("--formats", default="csv,json,sql")
    r.add_argument("--keep", action="store_true")
    r.set_defaults(fn=cmd_reproduce)
    s = sp.add_parser("sqlite", help="load exported CSVs into SQLite and check FKs/joins")
    s.add_argument("--data", required=True)
    s.add_argument("--db", default="journeylab.sqlite")
    s.set_defaults(fn=cmd_sqlite)
    db = sp.add_parser("dashboard", help="build web/data/*.json for the website from a generated dataset")
    db.add_argument("--data", required=True, help="dataset folder, e.g. output/full")
    db.add_argument("--web", default="web")
    db.set_defaults(fn=cmd_dashboard)
    sv = sp.add_parser("serve", help="open the dashboard website locally (http://localhost:8000)")
    sv.add_argument("--web", default="web")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--no-browser", action="store_true")
    sv.set_defaults(fn=cmd_serve)
    d = sp.add_parser("docs", help="regenerate data dictionary and DDL")
    d.add_argument("--root", default=".")
    d.set_defaults(fn=cmd_docs)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
