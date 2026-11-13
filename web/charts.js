/* Tiny SVG chart helpers (no libraries). Each chart redraws itself when the window resizes. */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const tip = () => document.getElementById("tooltip");
  const redraws = new Set();
  let rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => redraws.forEach(f => f()), 120); });

  function el(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs || {}) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function showTip(evt, html) {
    const t = tip(); t.innerHTML = html; t.classList.add("show");
    const pad = 14, w = t.offsetWidth, h = t.offsetHeight;
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + w > window.innerWidth - 8) x = evt.clientX - w - pad;
    if (y + h > window.innerHeight - 8) y = evt.clientY - h - pad;
    t.style.left = x + "px"; t.style.top = y + "px";
  }
  function hideTip() { tip().classList.remove("show"); }
  function niceMax(v) {
    if (v <= 0) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    const n = v / p;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
  }
  // rounded data-end bar (square at baseline) as a path
  function barPath(x, y, w, h, r, horizontal) {
    r = Math.min(r, horizontal ? h / 2 : w / 2, horizontal ? w : h);
    if (w <= 0 || h <= 0) return "";
    if (horizontal) return `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`;
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
  }
  function mount(container, draw) {
    const f = () => { container.innerHTML = ""; draw(Math.max(280, container.clientWidth || 600)); };
    f(); redraws.add(f);
  }

  /* Horizontal bars: items [{label, value, tip}] */
  function hbar(container, items, o = {}) {
    container.classList.add("chart");
    mount(container, (W) => {
      const labelW = o.labelWidth || 150, row = o.row || 34, barH = Math.min(18, row - 12), padR = 70;
      const H = items.length * row + 6;
      const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": o.aria || "bar chart" }, container);
      const max = o.max || Math.max(...items.map(d => d.value)) || 1;
      const plotW = W - labelW - padR;
      el("line", { x1: labelW, x2: labelW, y1: 0, y2: H, stroke: "var(--axis)" }, svg);
      items.forEach((d, i) => {
        const y = i * row + (row - barH) / 2;
        const w = Math.max(d.value > 0 ? 2 : 0, plotW * d.value / max);
        const t = el("text", { x: labelW - 10, y: y + barH / 2 + 4, "text-anchor": "end" }, svg);
        t.textContent = d.label;
        const p = el("path", { d: barPath(labelW, y, w, barH, 4, true), style: `fill:${d.color || o.color || "var(--s1)"}` }, svg);
        const v = el("text", { x: labelW + w + 6, y: y + barH / 2 + 4, class: "val" }, svg);
        v.textContent = (o.fmt || String)(d.value);
        const hit = el("rect", { x: 0, y: i * row, width: W, height: row, fill: "transparent" }, svg);
        hit.addEventListener("mousemove", e => { p.style.opacity = .82; showTip(e, d.tip || `<div class="t">${d.label}</div><div class="r">value <b>${(o.fmt || String)(d.value)}</b></div>`); });
        hit.addEventListener("mouseleave", () => { p.style.opacity = 1; hideTip(); });
      });
    });
  }

  /* Line chart: {x:[labels], series:[{name,color,values}], yFmt, bands:[{from,to,label}], yMax} */
  function line(container, o) {
    container.classList.add("chart");
    mount(container, (W) => {
      const H = o.height || 240, m = { l: 52, r: 16, t: 12, b: 28 };
      const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": o.aria || "line chart" }, container);
      const n = o.x.length, pw = W - m.l - m.r, ph = H - m.t - m.b;
      const vals = o.series.flatMap(s => s.values.filter(v => v != null));
      const ymax = o.yMax || niceMax(Math.max(...vals, 0) * 1.05);
      const X = i => m.l + (n <= 1 ? pw / 2 : pw * i / (n - 1));
      const Y = v => m.t + ph - ph * v / ymax;
      (o.bands || []).forEach(b => {
        const i0 = o.x.findIndex(x => x >= b.from), i1raw = o.x.findIndex(x => x >= b.to);
        if (i0 < 0) return;
        const i1 = i1raw < 0 ? n - 1 : i1raw;
        const r = el("rect", { x: X(i0), y: m.t, width: Math.max(2, X(i1) - X(i0)), height: ph, style: "fill:var(--band)" }, svg);
        const t = el("text", { x: X(i0) + 4, y: m.t + 12, class: "axis-text" }, svg); t.textContent = b.label;
      });
      for (let k = 0; k <= 4; k++) {
        const v = ymax * k / 4, y = Y(v);
        el("line", { x1: m.l, x2: W - m.r, y1: y, y2: y, stroke: k === 0 ? "var(--axis)" : "var(--grid)" }, svg);
        const t = el("text", { x: m.l - 8, y: y + 4, "text-anchor": "end", class: "axis-text" }, svg);
        t.textContent = (o.yFmt || String)(v);
      }
      const step = Math.max(1, Math.ceil(n / Math.floor(pw / 70)));
      o.x.forEach((x, i) => {
        if (i % step) return;
        const t = el("text", { x: X(i), y: H - 8, "text-anchor": "middle", class: "axis-text" }, svg);
        t.textContent = o.xFmt ? o.xFmt(x) : x;
      });
      o.series.forEach(s => {
        let d = "", pen = false;
        s.values.forEach((v, i) => {
          if (v == null) { pen = false; return; }
          d += (pen ? "L" : "M") + X(i).toFixed(1) + "," + Y(v).toFixed(1); pen = true;
        });
        el("path", { d, fill: "none", style: `stroke:${s.color}`, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round",
          "stroke-dasharray": s.dash || "" }, svg);
      });
      const cross = el("line", { y1: m.t, y2: m.t + ph, stroke: "var(--axis)", opacity: 0 }, svg);
      const dots = o.series.map(s => el("circle", { r: 4, style: `fill:${s.color};stroke:var(--surface)`, "stroke-width": 2, opacity: 0 }, svg));
      const hit = el("rect", { x: m.l, y: m.t, width: pw, height: ph, fill: "transparent" }, svg);
      hit.addEventListener("mousemove", e => {
        const box = svg.getBoundingClientRect(), sx = (e.clientX - box.left) * (W / box.width);
        const i = Math.max(0, Math.min(n - 1, Math.round((sx - m.l) / pw * (n - 1))));
        cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.setAttribute("opacity", 1);
        let html = `<div class="t">${o.tipTitle ? o.tipTitle(o.x[i], i) : o.x[i]}</div>`;
        o.series.forEach((s, k) => {
          const v = s.values[i];
          dots[k].setAttribute("opacity", v == null ? 0 : 1);
          if (v != null) { dots[k].setAttribute("cx", X(i)); dots[k].setAttribute("cy", Y(v)); }
          html += `<div class="r"><span><span class="sq" style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${s.color};margin-right:6px"></span>${s.name}</span><b>${v == null ? "—" : (o.yFmt || String)(v)}</b></div>`;
          if (s.extra) html += s.extra(i);
        });
        showTip(e, html);
      });
      hit.addEventListener("mouseleave", () => { cross.setAttribute("opacity", 0); dots.forEach(d => d.setAttribute("opacity", 0)); hideTip(); });
    });
  }

  /* Estimate with 95% interval: rows [{label, est, lo, hi, color, tip}] */
  function ci(container, rows, o = {}) {
    container.classList.add("chart");
    mount(container, (W) => {
      const labelW = o.labelWidth || 190, row = 40, H = rows.length * row + 30, padR = 24;
      const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "lift with confidence intervals" }, container);
      const ext = Math.max(...rows.flatMap(r => [Math.abs(r.lo ?? 0), Math.abs(r.hi ?? 0)]), 0.01);
      const lim = niceMax(ext * 1.1), pw = W - labelW - padR;
      const X = v => labelW + pw * (v + lim) / (2 * lim);
      [-lim, -lim / 2, 0, lim / 2, lim].forEach(v => {
        el("line", { x1: X(v), x2: X(v), y1: 0, y2: H - 22, stroke: v === 0 ? "var(--axis)" : "var(--grid)" }, svg);
        const t = el("text", { x: X(v), y: H - 6, "text-anchor": "middle", class: "axis-text" }, svg);
        t.textContent = (v > 0 ? "+" : "") + (v * 100).toFixed(0) + " pp";
      });
      rows.forEach((r, i) => {
        const y = i * row + row / 2;
        const t = el("text", { x: labelW - 10, y: y + 4, "text-anchor": "end" }, svg); t.textContent = r.label;
        if (r.est == null) { const n = el("text", { x: X(0) + 8, y: y + 4, class: "axis-text" }, svg); n.textContent = "no traffic (draft)"; return; }
        el("line", { x1: X(r.lo), x2: X(r.hi), y1: y, y2: y, style: `stroke:${r.color}`, "stroke-width": 2, "stroke-linecap": "round" }, svg);
        el("circle", { cx: X(r.est), cy: y, r: 5, style: `fill:${r.color};stroke:var(--surface)`, "stroke-width": 2 }, svg);
        const hit = el("rect", { x: 0, y: y - row / 2, width: W, height: row, fill: "transparent" }, svg);
        hit.addEventListener("mousemove", e => showTip(e, r.tip));
        hit.addEventListener("mouseleave", hideTip);
      });
    });
  }

  window.Charts = { hbar, line, ci, showTip, hideTip };
})();
