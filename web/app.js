/* Journey Friction Lab dashboard. Reads data/dashboard.json + data/sessions.json (built by
   `python -m journeylab dashboard`) and renders each section with plain DOM + SVG. */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const app = $("#app");
  const C = window.Charts;
  let D = null, S = null;

  // ---------------------------------------------------------------- formatting
  const int = v => v == null ? "—" : Math.round(v).toLocaleString("en-US");
  const pct = (v, d = 1) => v == null ? "—" : (v * 100).toFixed(d) + "%";
  const compact = v => v >= 1e6 ? (v / 1e6).toFixed(2) + "M" : v >= 1e4 ? (v / 1e3).toFixed(1) + "K" : int(v);
  const money = v => "$" + (v >= 1e6 ? (v / 1e6).toFixed(2) + "M" : v >= 1e3 ? (v / 1e3).toFixed(0) + "K" : v.toFixed(0));
  const nice = s => String(s).replace(/_/g, " ");
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const STAGE = { visit: "Visit", product_view: "Viewed a product", add_to_cart: "Added to cart",
    checkout_start: "Started checkout", payment_submitted: "Submitted payment", purchase: "Purchased" };

  function h(html) { const d = document.createElement("div"); d.innerHTML = html.trim(); return d.firstElementChild; }
  function badge(ok, text) { return `<span class="badge ${ok ? "ok" : "bad"}"><span class="dot"></span>${ok ? "✓" : "✗"} ${text}</span>`; }
  function table(rows, cols, opts = {}) {
    const head = cols.map(c => `<th class="${c.num ? "num" : ""}">${c.label}</th>`).join("");
    const body = rows.map((r, i) => `<tr data-i="${i}" class="${opts.clickable ? "clickable" : ""}">` +
      cols.map(c => `<td class="${c.num ? "num" : ""}">${c.fmt ? c.fmt(r[c.key], r) : esc(r[c.key])}</td>`).join("") + "</tr>").join("");
    return `<div class="tbl-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
  }
  function legend(items) {
    return `<div class="legend">${items.map(i => `<span class="k"><span class="${i.sq ? "sq" : "sw"}" style="background:${i.color}"></span>${i.name}</span>`).join("")}</div>`;
  }

  // ---------------------------------------------------------------- pages
  const pages = {};

  pages.overview = () => {
    const k = D.kpis, q = D.quality, rp = q.reproducibility;
    app.innerHTML = `
      <h1>Where do online shoppers give up — and why?</h1>
      <p class="lead">This project invents a realistic online shop (website, mobile app, customer support and orders),
        hides real-world problems inside the data on purpose, then runs an analysis that has to <b>find</b> those problems.
        Because we know the hidden answers, we can check how well the analysis works.</p>
      <div class="status-row">
        ${badge(q.validation.passed, `${q.validation.checks - q.validation.failed}/${q.validation.checks} data-quality checks pass`)}
        ${rp ? badge(rp.all_identical, `Reproducible: ${rp.files_compared}/${rp.files_compared} files identical on re-run`) : ""}
        <span class="badge"><span class="dot" style="background:var(--s1)"></span>seed ${D.meta.seed} · scale ${D.meta.scale}</span>
      </div>
      <div class="tiles">
        ${tile("Visits (sessions)", compact(k.sessions), "web · app · support")}
        ${tile("Events recorded", compact(k.events), "clicks, views, payments, chats")}
        ${tile("Orders", int(k.orders), money(k.revenue) + " revenue")}
        ${tile("Conversion rate", pct(k.conversion_rate), "visits that bought (bots removed)")}
        ${tile("Bots caught", int(k.bot_sessions_detected), "fake visitors filtered out")}
        ${tile("Hidden problems", int(k.labelled_anomalies), "planted on purpose, with answer key")}
      </div>
      <div class="card">
        <h2>How the project works</h2>
        <p class="sub">Four steps, all run by one command: <code>python -m journeylab generate</code></p>
        <div class="steps">
          ${step(1, "Create a fake shop", "Customers, devices, products and 100,000 visits are simulated: browsing, carts, payments, support chats.")}
          ${step(2, "Hide problems", "Broken payment page, slow search, bots, double-counted orders, events arriving late, wrong identity links.")}
          ${step(3, "Clean & analyse", "Remove duplicates, re-order events by time, drop bots, link visits (only with consent), measure drop-offs.")}
          ${step(4, "Check vs answer key", "Compare what the analysis found with what was hidden. Every number on this site comes from that.")}
        </div>
      </div>
      <div class="grid g2 section">
        <div class="card"><h2>The shopping funnel</h2><p class="sub">How many visits reach each step (all channels, bots removed)</p><div id="ovFunnel"></div>
          <p class="sub" style="margin-top:8px">→ See the <a href="#funnel">Funnel</a> page for drop-off by channel and month.</p></div>
        <div class="card"><h2>What happened in each visit</h2><p class="sub">Outcome of every session, decided by 8 documented rules</p><div id="ovOutcomes"></div></div>
      </div>
      <div class="card section">
        <h2>The 4 hidden broken steps — were they found?</h2>
        <p class="sub">The analysis did not know about these. It found them from the error data alone.</p>
        ${table(D.incidents.evaluation.details.map(d => ({ ...d, desc: (D.incidents.truth.find(t => t.incident_id === d.incident_id) || {}).description })), [
          { key: "incident_id", label: "Problem" }, { key: "desc", label: "What was broken (answer key)" },
          { key: "detected", label: "Found?", fmt: v => v ? "✅ yes" : "❌ no" },
          { key: "root_cause_dimension_found", label: "Cause identified", fmt: v => v ? esc(nice(v)) : "<span class='muted'>whole channel</span>" },
          { key: "alert_window", label: "Alert dates" }])}
      </div>`;
    C.hbar($("#ovFunnel"), D.funnel.all.map(s => ({ label: STAGE[s.stage], value: s.sessions_reached,
      tip: `<div class="t">${STAGE[s.stage]}</div><div class="r">sessions <b>${int(s.sessions_reached)}</b></div><div class="r">of all visits <b>${pct(s.cumulative_conversion)}</b></div>` })),
      { fmt: compact, labelWidth: 140 });
    const oc = Object.entries(D.outcomes).sort((a, b) => b[1] - a[1]);
    C.hbar($("#ovOutcomes"), oc.map(([k2, v]) => ({ label: nice(k2), value: v,
      color: k2 === "converted" ? "var(--good)" : k2.startsWith("abandoned") ? "var(--s2)" : "var(--s1)" })), { fmt: compact, labelWidth: 150 });
  };
  const tile = (l, v, n) => `<div class="tile"><div class="label">${l}</div><div class="value">${v}</div><div class="note">${n}</div></div>`;
  const step = (n, t, p) => `<div class="step"><span class="num">${n}</span><h3>${t}</h3><p>${p}</p></div>`;

  pages.funnel = () => {
    app.innerHTML = `
      <h1>Funnel & drop-offs</h1>
      <p class="lead">A <b>funnel</b> follows visitors step by step. The <b>drop-off</b> at each step is the share of people
        who reached the previous step but not this one. Bots and support calls are excluded; duplicates are removed first.</p>
      <div class="grid g2">
        <div class="card">
          <div class="controls"><div class="seg" id="chSeg"><button data-c="all" class="on">All</button><button data-c="web">Website</button><button data-c="app">App</button></div></div>
          <div id="fChart"></div><div id="fTable" style="margin-top:10px"></div>
        </div>
        <div class="card">
          <h2>Conversion rate by month</h2><p class="sub">Share of visits that ended in a purchase</p>
          ${legend([{ name: "Website", color: "var(--s1)" }, { name: "App", color: "var(--s2)" }])}
          <div id="mChart"></div>
          <div class="callout" style="margin-top:12px">Notice the dip in <b>app</b> conversion around May–June: that is the
            hidden broken payment page in app version 5.2.0 (see <a href="#incidents">Broken steps</a>).</div>
        </div>
      </div>
      <div class="card section"><h2>Conversion by traffic source</h2><p class="sub">Where visitors came from</p><div id="srcChart"></div></div>`;
    const draw = ch => {
      const f = D.funnel[ch];
      C.hbar($("#fChart"), f.map(s => ({ label: STAGE[s.stage], value: s.sessions_reached,
        tip: `<div class="t">${STAGE[s.stage]}</div><div class="r">sessions <b>${int(s.sessions_reached)}</b></div><div class="r">from previous step <b>${pct(s.step_conversion)}</b></div><div class="r">dropped off <b>${pct(s.drop_off_rate)}</b></div>` })),
        { fmt: compact, labelWidth: 140 });
      $("#fTable").innerHTML = table(f, [
        { key: "stage", label: "Step", fmt: v => STAGE[v] }, { key: "sessions_reached", label: "Sessions", num: 1, fmt: int },
        { key: "step_conversion", label: "Kept from prev.", num: 1, fmt: v => pct(v) },
        { key: "drop_off_rate", label: "Dropped off", num: 1, fmt: (v, r) => r.stage_no === 1 ? "—" : pct(v) },
        { key: "cumulative_conversion", label: "Of all visits", num: 1, fmt: v => pct(v, 2) }]);
    };
    $("#chSeg").addEventListener("click", e => {
      const b = e.target.closest("button"); if (!b) return;
      [...$("#chSeg").children].forEach(x => x.classList.toggle("on", x === b)); draw(b.dataset.c);
    });
    draw("all");
    C.line($("#mChart"), { x: D.monthly.map(m => m.month), yFmt: v => pct(v, 1), xFmt: m => m.slice(5) + "/26",
      series: [{ name: "Website", color: "var(--s1)", values: D.monthly.map(m => m.web_conversion) },
               { name: "App", color: "var(--s2)", values: D.monthly.map(m => m.app_conversion) }] });
    C.hbar($("#srcChart"), D.sources.sort((a, b) => b.conversion - a.conversion).map(s => ({ label: nice(s.source), value: s.conversion,
      tip: `<div class="t">${nice(s.source)}</div><div class="r">visits <b>${int(s.sessions)}</b></div><div class="r">conversion <b>${pct(s.conversion, 2)}</b></div>` })),
      { fmt: v => pct(v, 1), labelWidth: 130 });
  };

  pages.friction = () => {
    const F = D.friction;
    app.innerHTML = `
      <h1>High-friction steps & paths</h1>
      <p class="lead"><b>Friction</b> is anything that annoys a shopper: an error, a failed payment, a slow page.
        Here we measure how much each problem costs, by comparing affected visits with similar visits that had no problem.</p>
      <div class="card"><h2>Which errors cost the most orders?</h2>
        <p class="sub">Estimated lost orders = affected visits × (normal conversion − conversion when the error happened)</p>
        <div id="lossChart"></div><div style="margin-top:12px">${table(F.impact.slice(0, 10), [
          { key: "channel", label: "Channel" }, { key: "friction_event", label: "Error", fmt: nice }, { key: "error_code", label: "Code" },
          { key: "sessions_affected", label: "Visits hit", num: 1, fmt: int },
          { key: "conversion_rate_affected", label: "Bought (with error)", num: 1, fmt: v => pct(v) },
          { key: "baseline_conversion_same_stage", label: "Bought (no error)", num: 1, fmt: v => pct(v) },
          { key: "est_lost_conversions", label: "Lost orders", num: 1, fmt: v => v.toFixed(0) },
          { key: "support_contact_rate", label: "Called support", num: 1, fmt: v => pct(v) }])}</div></div>
      <div class="grid g2 section">
        <div class="card"><h2>Where people leave (exit rate by page)</h2>
          <div class="controls"><div class="seg" id="exSeg"><button data-c="web" class="on">Website</button><button data-c="app">App</button></div></div>
          <div id="exitChart"></div></div>
        <div class="card"><h2>Last 3 steps before abandoning (with an error)</h2>
          <p class="sub">Paths of shoppers who added to cart but never bought</p>
          ${table(F.paths_with_friction.slice(0, 10), [{ key: "channel", label: "Ch." }, { key: "path", label: "Path", fmt: v => esc(nice(v)) },
            { key: "abandoned_sessions", label: "Visits", num: 1, fmt: int }])}</div>
      </div>`;
    C.hbar($("#lossChart"), F.impact.filter(r => r.est_lost_conversions > 0).slice(0, 8).map(r => ({
      label: `${r.channel} · ${nice(r.error_code || r.friction_event)}`, value: r.est_lost_conversions, color: "var(--critical)",
      tip: `<div class="t">${nice(r.friction_event)} (${r.channel})</div><div class="r">code <b>${r.error_code}</b></div><div class="r">visits hit <b>${int(r.sessions_affected)}</b></div><div class="r">conversion gap <b>${r.conversion_gap_pp.toFixed(1)} pp</b></div><div class="r">est. lost orders <b>${r.est_lost_conversions.toFixed(0)}</b></div>` })),
      { fmt: v => v.toFixed(0), labelWidth: 230 });
    const drawExit = ch => C.hbar($("#exitChart"), F.steps.filter(s => s.channel === ch).sort((a, b) => b.exit_rate - a.exit_rate).map(s => ({
      label: nice(s.page_type), value: s.exit_rate,
      tip: `<div class="t">${nice(s.page_type)} page</div><div class="r">visits seeing it <b>${int(s.sessions)}</b></div><div class="r">left from here <b>${pct(s.exit_rate)}</b></div><div class="r">median load <b>${int(s.p50_load_ms)} ms</b></div><div class="r">slowest 5% load <b>${int(s.p95_load_ms)} ms</b></div>` })),
      { fmt: v => pct(v, 0), labelWidth: 140 });
    $("#exSeg").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return;
      [...$("#exSeg").children].forEach(x => x.classList.toggle("on", x === b)); drawExit(b.dataset.c); });
    drawExit("web");
  };

  pages.incidents = () => {
    const I = D.incidents;
    const title = { payment_error: "App payment errors", shipping_validation_error: "Website address-form errors",
      add_to_cart_failed: "App add-to-cart failures", search_page_load_ms: "Website search page speed" };
    const truthFor = s => I.truth.find(t => (t.event_type === s.signal) || (t.kind === "latency" && s.signal.startsWith(t.step)));
    app.innerHTML = `
      <h1>Broken steps (incident detection)</h1>
      <p class="lead">Four problems were hidden in the data. The analysis watches weekly error rates and raises an
        <b>alert</b> when a week is far above normal (an exact statistical test), then looks for <b>which group</b>
        (app version, country, phone OS) explains the spike. The red shaded area is the answer key.</p>
      <div class="grid g2" id="incGrid"></div>
      <div class="card section"><h2>All alerts raised</h2><p class="sub">Zero alerts were raised for problems that did not exist (no false alarms).</p>
        ${table(I.alerts, [{ key: "alert_id", label: "Alert" }, { key: "channel", label: "Channel" }, { key: "signal", label: "Signal", fmt: nice },
          { key: "segment", label: "Group", fmt: v => esc(nice(v)) }, { key: "start_date", label: "From" }, { key: "end_date", label: "To" },
          { key: "peak_value", label: "Peak", num: 1, fmt: (v, r) => r.kind === "latency_p50" ? int(v) + " ms" : pct(v) },
          { key: "baseline_value", label: "Normal", num: 1, fmt: (v, r) => r.kind === "latency_p50" ? int(v) + " ms" : pct(v) },
          { key: "top_dimension_value", label: "Likely cause", fmt: (v, r) => v ? `${esc(nice(r.top_dimension))} = ${esc(v)}` : "—" }])}</div>`;
    const grid = $("#incGrid");
    I.series.forEach((s, i) => {
      const t = truthFor(s);
      const card = h(`<div class="card"><h2>${title[s.signal]}</h2>
        <p class="sub">${t ? esc(t.description) : ""}</p>
        ${legend(s.segment ? [{ name: `All ${s.channel} traffic`, color: "var(--s1)" }, { name: `Only ${nice(s.segment.replace("=", " "))}`, color: "var(--s2)" }]
                           : [{ name: "Median page load", color: "var(--s1)" }])}
        <div class="c"></div></div>`);
      grid.appendChild(card);
      const series = [{ name: s.segment ? "All traffic" : "Median load", color: "var(--s1)", values: s.points.map(p => p.all_rate) }];
      if (s.segment) series.push({ name: nice(s.segment), color: "var(--s2)", values: s.points.map(p => p.seg_n >= 5 ? p.seg_rate : null) });
      C.line(card.querySelector(".c"), { x: s.points.map(p => p.week), series, height: 220,
        yFmt: s.segment ? (v => pct(v, 0)) : (v => int(v) + "ms"), xFmt: w => w.slice(5),
        tipTitle: w => "Week of " + w,
        bands: t ? [{ from: t.start.slice(0, 10), to: t.end.slice(0, 10), label: t.incident_id }] : [] });
    });
  };

  pages.experiments = () => {
    const E = D.experiments;
    app.innerHTML = `
      <h1>A/B experiments</h1>
      <p class="lead">An <b>A/B test</b> shows half the visitors a new design (treatment) and half the old one (control).
        The dot is the measured difference; the line is the 95% confidence range. If the line does not cross zero, the change really helped.</p>
      <div class="card"><h2>Measured lift on each experiment's target step</h2>${legend([{ name: "Real effect detected", color: "var(--s1)", sq: 1 }, { name: "No significant effect", color: "var(--muted)", sq: 1 }])}<div id="ciChart"></div></div>
      <div class="card section">${table(E, [{ key: "name", label: "Experiment", fmt: nice }, { key: "status", label: "Status" },
        { key: "target_metric", label: "Metric (of those who… → how many…)", fmt: v => { const [a, b] = v.split(" | "); return esc(nice(b) + " → " + nice(a)); } },
        { key: "rate_control", label: "Control", num: 1, fmt: v => pct(v) }, { key: "rate_treatment", label: "Treatment", num: 1, fmt: v => pct(v) },
        { key: "abs_lift", label: "Lift", num: 1, fmt: v => v == null ? "—" : (v > 0 ? "+" : "") + (v * 100).toFixed(1) + " pp" },
        { key: "p_value", label: "p-value", num: 1, fmt: v => v == null ? "—" : v < 0.0001 ? "<0.0001" : v.toFixed(4) },
        { key: "verdict", label: "Check vs answer key", fmt: v => ({ detected: "✅ real effect found", correct_null: "✅ correctly no effect",
          no_traffic_as_expected: "✅ draft, no traffic", missed: "❌ missed", false_positive: "❌ false alarm" }[v] || v) }])}</div>`;
    C.ci($("#ciChart"), E.map(r => ({ label: nice(r.name), est: r.abs_lift, lo: r.ci95_low, hi: r.ci95_high,
      color: r.p_value != null && r.p_value < 0.05 ? "var(--s1)" : "var(--muted)",
      tip: `<div class="t">${nice(r.name)}</div><div class="r">control <b>${pct(r.rate_control)}</b></div><div class="r">treatment <b>${pct(r.rate_treatment)}</b></div><div class="r">lift <b>${r.abs_lift == null ? "—" : (r.abs_lift * 100).toFixed(1) + " pp"}</b></div><div class="r">p-value <b>${r.p_value ?? "—"}</b></div>` })));
  };

  pages.quality = () => {
    const Q = D.quality, E = Q.evaluation;
    const st = E.identity_stitching, bd = E.bot_detection, dd = E.deduplication;
    app.innerHTML = `
      <h1>Data quality & how well the analysis did</h1>
      <p class="lead">Real event data is messy. Each card shows a problem that was planted, what a <b>naive</b> analysis
        would get wrong, and what this project's pipeline got — checked against the hidden answer key.</p>
      <div class="grid g3">
        <div class="card"><h3>Purchases counted twice</h3><div class="big-num">${int(dd.raw_purchase_events)}<span class="arrow">→</span>${int(dd.conversions_after_dedup)}</div>
          <p class="sub">raw purchase events → real orders after removing ${int(dd.double_counted_before_dedup)} duplicates.
          Found ${dd.tp}/${dd.true} planted duplicates. ${badge(dd.reconciled, "matches order table")}</p></div>
        <div class="card"><h3>Events arriving out of order</h3><div class="big-num">${int(E.ingestion_order.tp)}</div>
          <p class="sub">visits fixed by sorting on event time (all ${int(E.ingestion_order.true)} planted cases). Sorting by arrival instead
          would get the last steps wrong in ${pct(E.ingestion_order.naive_last3_steps_wrong_share, 0)} of them.</p></div>
        <div class="card"><h3>Privacy: consent respected</h3><div class="big-num">${int(st.consent_violations_events)}</div>
          <p class="sub">events linked to a person without their consent. A naive approach would link
          <b>${int(st.naive_consent_violations_events)}</b>. ${badge(st.respects_consent, "consent rule holds")}</p></div>
        <div class="card"><h3>Bots caught</h3><div class="big-num">${pct(bd.recall, 1)}</div>
          <p class="sub">of ${int(bd.true)} bot visits detected; precision ${pct(bd.precision, 1)}; only ${pct(bd.human_false_positive_rate, 2)} of real people wrongly flagged.</p>
          <div id="botChart"></div></div>
        <div class="card"><h3>Wrong identity links</h3><div class="big-num">${pct(E.identity_link_review.recall, 0)}</div>
          <p class="sub">of ${int(E.identity_link_review.true)} wrong links rejected. Visits tied to the wrong customer:
          <b>${int(st.wrong_customer_sessions)}</b> (naive: ${int(st.naive_wrong_customer_sessions)}).</p></div>
        <div class="card"><h3>Visit outcomes correct</h3><div class="big-num">${pct(E.journey_outcome.accuracy_vs_expected, 1)}</div>
          <p class="sub">of all 100,000 visits got the same outcome as the answer key. Sessions rebuilt with the 30-minute rule match
          ${pct(E.sessionization.event_time.match_rate, 0)} (vs ${pct(E.sessionization.ingestion_time.match_rate, 1)} if done wrongly).</p></div>
      </div>
      <div class="grid g2 section">
        <div class="card"><h2>Validation checks by category</h2><p class="sub">${Q.validation.checks - Q.validation.failed} of ${Q.validation.checks} pass (keys, links between tables, dates, totals, lifecycles…)</p>
          ${table(Object.entries(Q.validation.by_category).map(([k2, v]) => ({ k: k2, v })), [{ key: "k", label: "Category", fmt: nice }, { key: "v", label: "Result", fmt: v => "✅ " + v }])}</div>
        <div class="card"><h2>Planted problems (answer key)</h2><p class="sub">Stored separately in <code>ground_truth/</code>, never shown to the analysis</p>
          ${table(Q.anomalies, [{ key: "issue_type", label: "Problem", fmt: nice }, { key: "subtype", label: "Variant", fmt: nice }, { key: "count", label: "Count", num: 1, fmt: int }])}</div>
      </div>`;
    C.hbar($("#botChart"), Object.entries(bd.recall_by_type).map(([k2, v]) => ({ label: nice(k2), value: v })), { fmt: v => pct(v, 0), max: 1, labelWidth: 130, row: 28 });
  };

  pages.explorer = () => {
    const groups = [...new Set(S.map(s => s.group))];
    app.innerHTML = `
      <h1>Journey explorer</h1>
      <p class="lead">Pick a real example visit from the dataset and see every event in time order, plus what the analysis
        decided compared with the answer key. ⧉ = duplicate event · ⏱ = arrived out of order · ⚠ = error.</p>
      <div class="explorer">
        <div class="card"><div class="controls"><select id="grp"><option value="">All examples (${S.length})</option>${groups.map(g => `<option>${esc(g)}</option>`).join("")}</select></div>
          <div class="list" id="list"></div></div>
        <div class="card" id="detail"><p class="muted">Select a visit on the left.</p></div>
      </div>`;
    const drawList = () => {
      const g = $("#grp").value, rows = S.filter(s => !g || s.group === g);
      $("#list").innerHTML = table(rows, [{ key: "session_id", label: "Session" }, { key: "channel", label: "Ch." },
        { key: "group", label: "Example of", fmt: v => `<span class="muted">${esc(v)}</span>` }], { clickable: 1 });
      $("#list").querySelectorAll("tr.clickable").forEach(tr => tr.addEventListener("click", () => {
        $("#list").querySelectorAll("tr").forEach(x => x.classList.remove("sel")); tr.classList.add("sel");
        detail(rows[+tr.dataset.i]);
      }));
      if (rows.length) { $("#list").querySelector("tr.clickable").classList.add("sel"); detail(rows[0]); }
    };
    $("#grp").addEventListener("change", drawList);
    drawList();
  };
  const CAT = { purchase: "purchase", add_to_cart: "commerce", checkout_start: "commerce", payment_info_submitted: "commerce",
    product_view: "commerce", cart_view: "commerce", shipping_info_submitted: "commerce", remove_from_cart: "commerce",
    payment_error: "system", shipping_validation_error: "system", add_to_cart_failed: "system", page_error: "system", login_failed: "system",
    login: "identity", ticket_created: "support", agent_assigned: "support", message_customer: "support", message_agent: "support",
    ticket_resolved: "support", ticket_escalated: "support", csat_submitted: "support", contact_support_click: "support", help_view: "support" };
  function detail(s) {
    const t0 = Date.parse(s.events[0].ts);
    const rel = ts => { const d = (Date.parse(ts) - t0) / 1000; return d < 60 ? `+${d.toFixed(1)}s` : d < 3600 ? `+${(d / 60).toFixed(1)}m` : `+${(d / 3600).toFixed(1)}h`; };
    const isBot = s.bot_score != null && s.bot_score >= 0.6;
    $("#detail").innerHTML = `
      <h2>${s.session_id} <span class="badge">${s.channel}</span></h2>
      <p class="sub">${esc(s.group)} · started ${s.start.replace("T", " ").slice(0, 16)} UTC · ${s.events.length} events</p>
      <div class="kv">
        <div>Device</div><div>${esc(s.device_id || "— (phone call)")}</div>
        <div>Logged-in customer</div><div>${esc(s.customer_id || "anonymous")}</div>
        <div>Came from</div><div>${esc(nice(s.traffic_source))} · ${esc(s.geo || "")}</div>
        <div>User agent</div><div class="muted">${esc(s.user_agent || "—")}</div>
      </div>
      <div class="compare">
        <div class="box"><b>What the analysis decided</b><br>Outcome: ${nice(s.outcome)}<br>Bot? ${isBot ? "yes (score " + s.bot_score + ")" : "no"}<br>Linked to customer: ${esc(s.stitched || "no (anonymous or no consent)")}</div>
        <div class="box"><b>Answer key (ground truth)</b><br>Outcome: ${nice(s.truth.expected_outcome)}<br>Actor: ${s.truth.actor}${s.truth.bot_type ? " (" + nice(s.truth.bot_type) + ")" : ""}<br>${(s.truth.expected_outcome === s.outcome && (s.truth.actor === "bot") === isBot) ? "✅ analysis agrees" : "⚠ analysis differs"}</div>
      </div>
      <ul class="timeline">${s.events.map(e => `<li><span class="time">${rel(e.ts)}</span><span class="mk ${CAT[e.type] || ""}"></span>
        <span><b>${nice(e.type)}</b>${e.page ? ` <span class="muted">on ${nice(e.page)}</span>` : ""}${e.value != null && e.type !== "csat_submitted" ? ` · $${e.value.toFixed(2)}` : ""}${e.load ? ` <span class="muted">· ${e.load} ms</span>` : ""}
        ${e.err ? `<span class="flag err">${esc(e.err)}</span>` : ""}${e.dup ? `<span class="flag dupe">duplicate — removed</span>` : ""}${e.late_order ? `<span class="flag late">arrived out of order</span>` : ""}
        <div class="muted" style="font-size:11.5px">${e.id}</div></span></li>`).join("")}</ul>`;
  }

  pages.about = () => {
    const m = D.meta, rows = m.table_rows;
    app.innerHTML = `
      <h1>About this project</h1>
      <p class="lead">Journey Friction Lab is a student data-engineering project: a <b>synthetic data generator</b>
        plus an <b>analytics pipeline</b> that finds where customers drop off across website, app, support and purchases.</p>
      <div class="grid g2">
        <div class="card"><h2>Run it yourself</h2>
<pre>pip install -r requirements.txt
python -m pytest -q
python -m journeylab generate --scale 1.0 --out output/full
python -m journeylab dashboard --data output/full --web web
python -m journeylab serve</pre>
          <p class="sub">The same seed (${m.seed}) always gives exactly the same data.</p></div>
        <div class="card"><h2>Tables in the dataset</h2>${table(Object.entries(rows).map(([k2, v]) => ({ k: k2, v })), [{ key: "k", label: "Table" }, { key: "v", label: "Rows", num: 1, fmt: int }])}</div>
      </div>
      <div class="card section"><h2>Glossary</h2>
        <div class="kv" style="grid-template-columns:180px 1fr">
          <div>Session</div><div>One visit. A new session starts after 30 minutes of no activity.</div>
          <div>Event</div><div>One recorded action: page view, add to cart, payment, support message…</div>
          <div>Funnel</div><div>The steps from visit to purchase; drop-off is how many leave at each step.</div>
          <div>Friction</div><div>Errors, failures or slowness that make people give up.</div>
          <div>Ground truth</div><div>The answer key: what was hidden in the data on purpose.</div>
          <div>Deduplication</div><div>Removing the same event recorded twice.</div>
          <div>Identity stitching</div><div>Linking anonymous visits to a known customer — only allowed with their consent.</div>
          <div>Seed</div><div>A number that makes the random generator repeatable.</div>
        </div></div>`;
  };

  // ---------------------------------------------------------------- router
  function route() {
    const name = (location.hash || "#overview").slice(1);
    const fn = pages[name] || pages.overview;
    document.querySelectorAll(".tabs a").forEach(a => a.classList.toggle("active", a.getAttribute("href") === "#" + (pages[name] ? name : "overview")));
    C.hideTip();
    fn();
    window.scrollTo(0, 0);
  }
  $("#themeToggle").addEventListener("click", () => {
    const r = document.documentElement;
    const dark = r.dataset.theme ? r.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    r.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("jfl-theme", r.dataset.theme); } catch (e) { /* storage unavailable */ }
    route();
  });
  try { const t = localStorage.getItem("jfl-theme"); if (t) document.documentElement.dataset.theme = t; } catch (e) { /* ignore */ }

  Promise.all([fetch("data/dashboard.json").then(r => r.json()), fetch("data/sessions.json").then(r => r.json())])
    .then(([d, s]) => {
      D = d; S = s;
      $("#footMeta").textContent = `Generator v${d.meta.generator_version} · seed ${d.meta.seed} · scale ${d.meta.scale}.`;
      window.addEventListener("hashchange", route);
      route();
    })
    .catch(err => {
      app.innerHTML = `<div class="card"><h2>Could not load the data</h2><p class="sub">${esc(err)}</p>
        <p>If you opened <code>index.html</code> by double-clicking, browsers block loading local files. Run
        <code>python -m journeylab serve</code> and open <code>http://localhost:8000</code> instead.</p></div>`;
    });
})();
