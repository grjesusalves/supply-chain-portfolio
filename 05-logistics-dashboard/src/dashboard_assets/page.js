(function () {
  "use strict";
  // All numbers come from the JSON block that build_dashboard.py embeds.
  // The script positions marks and sums weekly counts; it never computes a
  // median, and it never combines the weekly, band and state blocks.
  var D = JSON.parse(document.getElementById("dash-data").textContent);
  var NS = "http://www.w3.org/2000/svg";
  var C = D.colors;
  var DAY = 864e5;
  var WK = D.weeks;
  var N = WK.length;
  var T = WK.map(function (w) { return Date.parse(w.d + "T00:00:00Z"); });
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var fmtN = function (v) { return v.toLocaleString("en-US"); };
  var pct = function (a, b) { return b ? (100 * a / b).toFixed(1) + "%" : "–"; };

  // ---------------------------------------------------------------- tooltip
  var tip = document.getElementById("tip");
  function row(k, v) { return '<div class="r"><span>' + k + "</span><span>" + v + "</span></div>"; }
  function showTip(html, x, y) {
    tip.innerHTML = html;
    tip.hidden = false;
    var sx = window.scrollX, vw = document.documentElement.clientWidth;
    var w = tip.offsetWidth;
    var left = x + 14;
    if (left + w > sx + vw - 8) left = sx + vw - 8 - w;
    if (left < sx + 8) left = sx + 8;
    tip.style.left = left + "px";
    tip.style.top = (y + 16) + "px";
  }
  function tipNear(html, elem) {
    var b = elem.getBoundingClientRect();
    showTip(html, b.left + window.scrollX + Math.min(b.width / 2, 160), b.top + window.scrollY + b.height / 2);
  }
  function hideTip() { tip.hidden = true; }
  document.addEventListener("pointerdown", function (e) {
    if (!e.target.closest("[data-tip-owner]")) hideTip();
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") hideTip(); });

  function mk(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function tx(parent, x, y, s, size, fill, anchor, weight, halo) {
    var a = { x: x.toFixed(1), y: y.toFixed(1), "font-size": size, fill: fill,
      "text-anchor": anchor || "start", "font-weight": weight || 400 };
    if (halo) { a.stroke = "#fff"; a["stroke-width"] = 3; a["paint-order"] = "stroke"; a["stroke-linejoin"] = "round"; }
    var e = mk("text", a, parent);
    e.textContent = s;
    return e;
  }
  function tspan(parent, s, fill, weight) {
    var e = mk("tspan", { fill: fill, "font-weight": weight || 600 }, parent);
    e.textContent = s;
    return e;
  }

  // ------------------------------------------------------- weekly trend
  function weekTip(w) {
    var h = ["<b>Week of " + w.lab.d + "</b>"];
    if (w.s === "gap") {
      h.push('<div class="n">No purchases this week: a gap, not zero.</div>');
    } else {
      h.push(row("Orders purchased", w.lab.p));
      if (w.s === "nodel") {
        h.push('<div class="n">No delivered orders: days and on-time are left blank, not zero.</div>');
      } else {
        h.push(row("Delivered orders", w.lab.n));
        h.push(row("Median purchase-to-door", w.lab.m + " days"));
        h.push(row("On time", w.lab.r + " (" + w.lab.o + " / " + w.lab.n + ")"));
      }
    }
    return h.join("");
  }

  var range = D.presets.all.slice();
  var ctx = null;

  function renderWeekly() {
    var host = document.getElementById("wk-host");
    var compact = host.clientWidth < 640;
    var W = compact ? 380 : 1100;
    var i0 = range[0], i1 = range[1];
    var t0 = T[i0], t1 = T[i1] + 7 * DAY, span = t1 - t0;
    var left = compact ? 44 : 56, right = compact ? 44 : 92, plotW = W - left - right;
    var X = function (ms) { return left + (ms - t0) / span * plotW; };
    var weekW = 7 * DAY / span * plotW;
    var fs = compact ? 11 : 12, tfs = compact ? 11 : 12.5;
    // Y axes stay fixed when the range changes, so a week looks the same
    // size in any view and two ranges can be compared by eye.
    var P = [
      { h: compact ? 128 : 150, lo: 0, hi: D.ordersHi, ticks: [0, 1000, 2000, 3000], fmt: function (v) { return fmtN(v); } },
      { h: compact ? 112 : 128, lo: 0, hi: 20, ticks: [0, 5, 10, 15, 20], fmt: function (v) { return String(v); } },
      { h: compact ? 112 : 128, lo: 70, hi: 100, ticks: [70, 80, 90, 100], fmt: function (v) { return v + "%"; } }
    ];
    var y = 0;
    P.forEach(function (p) { y += compact ? 34 : 36; p.top = y; p.bottom = y + p.h; y = p.bottom + 18; });
    var axisY = P[2].bottom, H = axisY + (compact ? 30 : 40);
    var Y = function (p, v) { v = Math.min(Math.max(v, p.lo), p.hi); return p.bottom - (v - p.lo) / (p.hi - p.lo) * p.h; };
    var fits = function (s, x, anchor) {
      var est = s.length * fs * 0.56;
      // Start-anchored labels may run into the right margin (empty at the
      // top of a panel); end-anchored ones must not cross the y labels.
      return anchor === "end" ? x - est >= left - 4 : x + est <= W - 2;
    };

    var svg = mk("svg", { viewBox: "0 0 " + W + " " + H, "aria-hidden": "true" });
    var defs = mk("defs", {}, svg);
    var pat = mk("pattern", { id: "wkgap", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
    mk("rect", { width: 6, height: 6, fill: "#F3F5F8" }, pat);
    mk("line", { x1: 0, y1: 0, x2: 0, y2: 6, stroke: "#D7DDE5", "stroke-width": 2 }, pat);

    // Gap runs: Mondays with no purchase, shaded in every panel.
    var runs = [];
    for (var i = i0; i <= i1; i++) {
      if (WK[i].s !== "gap") continue;
      if (runs.length && runs[runs.length - 1][1] === i - 1) runs[runs.length - 1][1] = i;
      else runs.push([i, i]);
    }
    P.forEach(function (p) {
      runs.forEach(function (r) {
        var a = X(T[r[0]]), b = X(T[r[1]] + 7 * DAY);
        mk("rect", { x: a, y: p.top, width: b - a, height: p.h, fill: "url(#wkgap)" }, svg);
      });
    });
    var low = D.lowIdx, peak = D.peakIdx;
    var lowIn = low >= i0 && low <= i1, peakIn = peak >= i0 && peak <= i1;
    if (lowIn) [P[1], P[2]].forEach(function (p) {
      mk("rect", { x: X(T[low]) - 1, y: p.top, width: weekW + 2, height: p.h, fill: C.accentPale }, svg);
    });

    // Grid, y labels, year separators.
    P.forEach(function (p) {
      p.ticks.forEach(function (t) {
        var yy = Y(p, t);
        mk("line", { x1: left, x2: left + plotW, y1: yy, y2: yy, stroke: t === p.lo ? "#B9C2CD" : C.grid }, svg);
        tx(svg, left - 8, yy + 4, p.fmt(t), fs, C.muted, "end");
      });
      [2017, 2018].forEach(function (yr) {
        var ms = Date.UTC(yr, 0, 1);
        if (ms > t0 && ms < t1) mk("line", { x1: X(ms), x2: X(ms), y1: p.top, y2: p.bottom, stroke: C.light, "stroke-dasharray": "2 3" }, svg);
      });
    });

    // Panel titles with inline keys instead of a legend.
    var tt = function (p) { return p.top - (compact ? 12 : 14); };
    var t1el = tx(svg, 0, tt(P[0]), compact ? "Orders per week " : "Orders per week, by purchase week  ", tfs, C.ink, "start", 600);
    tspan(t1el, compact ? "■ delivered " : "■ delivered orders  ", C.navy, 500);
    tspan(t1el, compact ? "■ all purchases" : "■ all purchases, any status", C.muted, 500);
    tx(svg, 0, tt(P[1]), "Median purchase-to-door, days", tfs, C.ink, "start", 600);
    tx(svg, 0, tt(P[2]), compact ? "On-time rate, % of delivered" : "On-time rate, % of delivered orders (calendar date)", tfs, C.ink, "start", 600);

    // Panel 1 bars: purchases behind deliveries. Only weeks in the extract.
    var bw = weekW * 0.78;
    for (i = i0; i <= i1; i++) {
      var w = WK[i];
      if (w.s === "gap") continue;
      var bx = X(T[i]) + (weekW - bw) / 2;
      var yp = Y(P[0], w.p);
      mk("rect", { x: bx, y: yp, width: bw, height: P[0].bottom - yp, fill: C.light }, svg);
      if (w.n != null) {
        var yd = Y(P[0], w.n);
        mk("rect", { x: bx, y: yd, width: bw, height: P[0].bottom - yd, fill: C.navy }, svg);
      }
    }

    // Full-period reference lines, labelled in the right margin.
    [[P[1], D.ref.p2d, "Full-period median", D.ref.p2dLab + " days", D.ref.p2dLab + "d"],
     [P[2], D.ref.ot, "Full-period rate", D.ref.otLab, D.ref.otLab]].forEach(function (a) {
      var yy = Y(a[0], a[1]);
      mk("line", { x1: left, x2: left + plotW + 6, y1: yy, y2: yy, stroke: C.slate, "stroke-dasharray": "4 3" }, svg);
      if (compact) tx(svg, left + plotW + 8, yy + 4, a[4], fs, C.slate, "start", 600);
      else { tx(svg, left + plotW + 10, yy - 3, a[2], 11, C.muted); tx(svg, left + plotW + 10, yy + 11, a[3], 12, C.slate, "start", 600); }
    });

    // Lines break at every blank: a missing week is never drawn as zero.
    function line(p, get) {
      var seg = [];
      function flush() {
        if (seg.length === 1) mk("circle", { cx: seg[0][0], cy: seg[0][1], r: 2.2, fill: C.navy }, svg);
        else if (seg.length > 1) mk("polyline", { points: seg.map(function (q) { return q[0].toFixed(1) + "," + q[1].toFixed(1); }).join(" "),
          fill: "none", stroke: C.navy, "stroke-width": compact ? 1.6 : 1.8, "stroke-linejoin": "round" }, svg);
        seg = [];
      }
      for (var k = i0; k <= i1; k++) {
        var v = get(WK[k]);
        if (v == null) flush(); else seg.push([X(T[k]) + weekW / 2, Y(p, v)]);
      }
      flush();
    }
    line(P[1], function (w) { return w.m; });
    line(P[2], function (w) { return w.r == null ? null : w.r * 100; });

    // Values outside a panel's range are pinned to its edge and labelled.
    [[P[1], function (w) { return w.m; }, function (w) { return w.lab.m + " days"; }],
     [P[2], function (w) { return w.r == null ? null : w.r * 100; }, function (w) { return w.lab.r; }]].forEach(function (a) {
      var p = a[0];
      for (var k = i0; k <= i1; k++) {
        var v = a[1](WK[k]);
        if (v == null || (v <= p.hi && v >= p.lo)) continue;
        var cx = X(T[k]) + weekW / 2, above = v > p.hi;
        var cy = above ? p.top + 4 : p.bottom - 4;
        var pts = above ? [[cx - 4, cy + 3], [cx + 4, cy + 3], [cx, cy - 4]] : [[cx - 4, cy - 3], [cx + 4, cy - 3], [cx, cy + 4]];
        mk("polygon", { points: pts.map(function (q) { return q.join(","); }).join(" "), fill: C.slate }, svg);
        var n = WK[k].n;
        var s = a[2](WK[k]) + ", " + n + (n === 1 ? " order" : " orders");
        var an = fits(s, cx + 7, "start") ? "start" : "end";
        tx(svg, an === "start" ? cx + 7 : cx - 7, above ? cy + 4 : cy - 1, s, fs - 1, C.slate, an, 400, true);
      }
    });

    // Annotations, only when the annotated week is in view.
    if (peakIn) {
      var px = X(T[peak]) + weekW / 2, py = Y(P[0], WK[peak].n);
      var ps = compact ? "Peak " + WK[peak].lab.n + ", wk of " + WK[peak].lab.d.slice(0, -5)
        : "Peak: " + WK[peak].lab.n + " delivered, week of " + WK[peak].lab.d;
      var pa = compact ? "start" : "end";
      if (!fits(ps, pa === "end" ? px - 8 : px + 6, pa)) pa = pa === "end" ? "start" : "end";
      tx(svg, pa === "end" ? px - 8 : px + 6, py + 10, ps, fs, C.ink, pa, 500, true);
    }
    if (lowIn) {
      var lx = X(T[low]) + weekW / 2, lw = WK[low];
      var lab3 = lw.lab.r + (compact ? "" : ", week of " + lw.lab.d);
      var lab2 = lw.lab.m + " days" + (compact ? "" : ", week of " + lw.lab.d);
      mk("circle", { cx: lx, cy: Y(P[2], lw.r * 100), r: 3.6, fill: C.accent }, svg);
      mk("circle", { cx: lx, cy: Y(P[1], lw.m), r: 3.6, fill: C.accent }, svg);
      var a3 = fits(lab3, lx - 9, "end") ? "end" : "start";
      tx(svg, a3 === "end" ? lx - 9 : lx + 9, Y(P[2], lw.r * 100) + 4, lab3, fs, C.accent, a3, 600, true);
      var a2 = fits(lab2, lx - 9, "end") ? "end" : "start";
      tx(svg, a2 === "end" ? lx - 9 : lx + 9, Y(P[1], lw.m) - 5, lab2, fs, C.accent, a2, 600, true);
    }
    // Gap label on the longest run in view (two weeks or more).
    var longest = runs.filter(function (r) { return r[1] - r[0] >= 1; }).sort(function (a, b) { return (b[1] - b[0]) - (a[1] - a[0]); })[0];
    if (longest) {
      var gx = X(T[longest[0]]);
      tx(svg, gx, P[0].top + 12, "No purchases:", fs - 1, C.slate, "start", 600, true);
      tx(svg, gx, P[0].top + 25, "gap, not zero", fs - 1, C.slate, "start", 400, true);
    }
    // Late-2018 weeks with purchases and no delivery: a marker, not a zero.
    var tail = [];
    for (i = i0; i <= i1; i++) if (WK[i].s === "nodel" && WK[i].d >= "2018-01-01") tail.push(i);
    if (tail.length) {
      var ta = X(T[tail[0]]), tb = X(T[tail[tail.length - 1]] + 7 * DAY);
      mk("line", { x1: ta, x2: tb, y1: P[1].bottom - 6, y2: P[1].bottom - 6, stroke: C.muted }, svg);
      if (!compact) {
        tx(svg, left + plotW, P[1].top + 12, "Sep–Oct 2018: purchases but no", fs - 1, C.slate, "end", 400, true);
        tx(svg, left + plotW, P[1].top + 25, "delivered order, left blank ↓", fs - 1, C.slate, "end", 400, true);
      }
    }

    // X axis. Tick spacing adapts to the range.
    var spanW = span / (7 * DAY);
    var step = compact ? (spanW > 60 ? 6 : spanW > 26 ? 3 : 2) : (spanW > 60 ? 3 : spanW > 26 ? 2 : 1);
    var d0 = new Date(t0), yy0 = d0.getUTCFullYear(), mo = d0.getUTCMonth() + 1;
    if (mo > 11) { mo = 0; yy0++; }
    for (;;) {
      var ms = Date.UTC(yy0, mo, 1);
      if (ms > t1) break;
      if (mo % step === 0) {
        var xx = X(ms);
        if (xx >= left && xx <= left + plotW) {
          mk("line", { x1: xx, x2: xx, y1: axisY, y2: axisY + 5, stroke: C.muted }, svg);
          tx(svg, xx, axisY + 18, MONTHS[mo] + (compact ? " '" + String(yy0).slice(2) : " " + yy0), fs, C.muted, "middle");
        }
      }
      mo++; if (mo > 11) { mo = 0; yy0++; }
    }
    if (!compact) tx(svg, left + plotW, axisY + 34, "Week of purchase (weeks start Monday)", fs - 1, C.muted, "end");

    // Crosshair synced across the three panels.
    var cross = mk("g", { display: "none", "pointer-events": "none" }, svg);
    var cl = mk("line", { y1: P[0].top, y2: axisY, stroke: C.ink, "stroke-opacity": 0.55 }, cross);
    var cb = mk("rect", { y: P[0].top, height: P[0].h, fill: "none", stroke: C.accent, "stroke-width": 1.5 }, cross);
    var c2 = mk("circle", { r: 4.5, fill: "#fff", stroke: C.navy, "stroke-width": 2 }, cross);
    var c3 = mk("circle", { r: 4.5, fill: "#fff", stroke: C.navy, "stroke-width": 2 }, cross);
    var overlay = mk("rect", { x: left, y: P[0].top, width: plotW, height: axisY - P[0].top, fill: "#fff", "fill-opacity": 0, style: "cursor:crosshair" }, svg);
    var cur = -1;

    function setCross(k, pageX, pageY) {
      cur = k;
      var w = WK[k], cx = X(T[k]) + weekW / 2;
      cross.setAttribute("display", "inline");
      cl.setAttribute("x1", cx); cl.setAttribute("x2", cx);
      cb.setAttribute("x", X(T[k]) + (weekW - bw) / 2 - 1); cb.setAttribute("width", bw + 2);
      if (w.m != null) { c2.setAttribute("cx", cx); c2.setAttribute("cy", Y(P[1], w.m)); c2.setAttribute("display", "inline"); }
      else c2.setAttribute("display", "none");
      if (w.r != null) { c3.setAttribute("cx", cx); c3.setAttribute("cy", Y(P[2], w.r * 100)); c3.setAttribute("display", "inline"); }
      else c3.setAttribute("display", "none");
      if (pageX == null) {
        var pt = svg.createSVGPoint(); pt.x = cx; pt.y = P[1].top;
        var s = pt.matrixTransform(svg.getScreenCTM());
        pageX = s.x + window.scrollX; pageY = s.y + window.scrollY;
      }
      showTip(weekTip(w), pageX, pageY);
      document.getElementById("wk-live").textContent = "Week of " + w.lab.d;
    }
    function clearCross() { cur = -1; cross.setAttribute("display", "none"); }
    function idxAt(e) {
      var pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
      var p = pt.matrixTransform(svg.getScreenCTM().inverse());
      return Math.max(i0, Math.min(i1, i0 + Math.floor((p.x - left) / weekW)));
    }
    overlay.addEventListener("pointermove", function (e) { setCross(idxAt(e), e.pageX, e.pageY); });
    overlay.addEventListener("pointerdown", function (e) { setCross(idxAt(e), e.pageX, e.pageY); });
    overlay.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse") { clearCross(); hideTip(); } });

    host.innerHTML = "";
    host.appendChild(svg);
    host.dataset.compact = compact ? "1" : "0";
    ctx = { setCross: setCross, clearCross: clearCross, i0: i0, i1: i1, cur: function () { return cur; } };
  }

  var host = document.getElementById("wk-host");
  host.setAttribute("data-tip-owner", "");
  host.addEventListener("keydown", function (e) {
    if (!ctx) return;
    var k = ctx.cur();
    if (e.key === "ArrowRight") k = k < 0 ? ctx.i0 : Math.min(ctx.i1, k + 1);
    else if (e.key === "ArrowLeft") k = k < 0 ? ctx.i1 : Math.max(ctx.i0, k - 1);
    else if (e.key === "Home") k = ctx.i0;
    else if (e.key === "End") k = ctx.i1;
    else if (e.key === "Escape") { ctx.clearCross(); hideTip(); return; }
    else return;
    e.preventDefault();
    ctx.setCross(k);
  });
  host.addEventListener("blur", function () { if (ctx) ctx.clearCross(); hideTip(); });

  // Range controls: presets plus two sliders. Summary uses sums of weekly
  // counts only (orders, on-time orders, items, cross-state items), which
  // are additive. Medians are not recomputed for a range.
  var from = document.getElementById("wk-from"), to = document.getElementById("wk-to");
  var fromOut = document.getElementById("wk-from-out"), toOut = document.getElementById("wk-to-out");
  var presetBtns = Array.prototype.slice.call(document.querySelectorAll("[data-preset]"));
  from.max = to.max = String(N - 1);

  function updateSummary() {
    var wk = 0, p = 0, n = 0, o = 0, it = 0, ci = 0;
    for (var i = range[0]; i <= range[1]; i++) {
      var w = WK[i];
      if (w.s === "gap") continue;
      wk++; p += w.p;
      if (w.s === "ok") { n += w.n; o += w.o; it += w.it; ci += w.ci; }
    }
    var full = range[0] === 0 && range[1] === N - 1;
    document.getElementById("wk-summary").innerHTML =
      "<b>" + (full ? "Full period" : "Selected weeks") + ":</b> weeks of " + WK[range[0]].lab.d + " – " + WK[range[1]].lab.d +
      " · " + wk + " purchase weeks · " + fmtN(p) + " orders purchased · " + fmtN(n) + " delivered · " +
      pct(o, n) + " on time (" + fmtN(o) + " / " + fmtN(n) + ") · " + pct(ci, it) + " of delivered items cross a state" +
      "<small>Rates here are sums of weekly counts. Medians are not recomputed for a range; the KPI cards above stay full-period.</small>";
  }
  function setRange(a, b) {
    range = [a, b];
    from.value = a; to.value = b;
    fromOut.textContent = WK[a].lab.d; toOut.textContent = WK[b].lab.d;
    from.setAttribute("aria-valuetext", "Week of " + WK[a].lab.d);
    to.setAttribute("aria-valuetext", "Week of " + WK[b].lab.d);
    presetBtns.forEach(function (btn) {
      var pr = D.presets[btn.dataset.preset];
      btn.setAttribute("aria-pressed", pr[0] === a && pr[1] === b ? "true" : "false");
    });
    hideTip();
    renderWeekly();
    updateSummary();
  }
  from.addEventListener("input", function () {
    var a = +from.value, b = +to.value;
    if (a > b - 3) a = Math.max(0, b - 3);
    setRange(a, b);
  });
  to.addEventListener("input", function () {
    var a = +from.value, b = +to.value;
    if (b < a + 3) b = Math.min(N - 1, a + 3);
    setRange(a, b);
  });
  presetBtns.forEach(function (btn) {
    btn.addEventListener("click", function () { var pr = D.presets[btn.dataset.preset]; setRange(pr[0], pr[1]); });
  });
  var lastCompact = null;
  window.addEventListener("resize", function () {
    var c = host.clientWidth < 640;
    if (c !== lastCompact) { lastCompact = c; renderWeekly(); }
  });

  // ------------------------------------------------------------ bands
  var BI = {};
  D.bands.forEach(function (b) { BI[b.code] = b; });
  function bandTip(b) {
    return "<b>" + b.label + "</b>" + row("Delivered orders", b.orders) + row("Items", b.items) +
      row("Median handling", b.hand + " days") + row("Median transit", b.tran + " days") +
      row("Median purchase-to-door", b.door + " days") + row("On time", b.ot) +
      row("Median freight per item", b.fr);
  }
  var marks = Array.prototype.slice.call(document.querySelectorAll(".band-mark, tr.band-row"));
  var chips = Array.prototype.slice.call(document.querySelectorAll("[data-chip]"));
  var bandSel = null;
  function setBand(code) {
    bandSel = (code === "all" || code === bandSel) ? null : code;
    marks.forEach(function (m) {
      var on = m.dataset.band === bandSel;
      m.classList.toggle("on", on);
      m.classList.toggle("dim", !!bandSel && !on);
      if (m.tagName !== "TR") m.setAttribute("aria-pressed", on ? "true" : "false");
    });
    chips.forEach(function (c) { c.setAttribute("aria-pressed", c.dataset.chip === (bandSel || "all") ? "true" : "false"); });
    var b = bandSel && BI[bandSel];
    document.getElementById("band-readout").innerHTML = b
      ? "<b>" + b.label + ":</b> " + b.orders + " orders · handling " + b.hand + " d · transit " + b.tran + " d · to door " + b.door + " d · on time " + b.ot + " · " + b.fr + " per item"
      : "All bands shown. Click a band, a row or a chip to highlight it.";
  }
  marks.forEach(function (m) {
    m.setAttribute("data-tip-owner", "");
    var b = BI[m.dataset.band];
    m.addEventListener("click", function (e) { setBand(m.dataset.band); showTip(bandTip(b), e.pageX, e.pageY); });
    m.addEventListener("pointermove", function (e) { if (e.pointerType === "mouse") showTip(bandTip(b), e.pageX, e.pageY); });
    m.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse") hideTip(); });
    m.addEventListener("focus", function () { tipNear(bandTip(b), m); });
    m.addEventListener("blur", hideTip);
    m.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setBand(m.dataset.band); tipNear(bandTip(b), m); }
    });
  });
  chips.forEach(function (c) { c.addEventListener("click", function () { setBand(c.dataset.chip === bandSel ? "all" : c.dataset.chip); }); });

  // ---------------------------------------------------------- coverage
  var cov = document.getElementById("cov-svg");
  var top0 = +cov.dataset.top, rh = +cov.dataset.rowh;
  var SI = {}, RE = {};
  D.states.forEach(function (s) { SI[s.code] = s; });
  Array.prototype.forEach.call(cov.querySelectorAll(".st-row"), function (g) { RE[g.dataset.state] = g; });
  function stateTip(s) {
    return "<b>" + s.name + " (" + s.code + ")</b>" +
      row("Customer people", s.people + " (" + s.psl + ")") +
      row("Sellers", s.sellers + " (" + s.ssl + ")") +
      (s.sellers === "0" ? '<div class="n">Customers, no sellers.</div>' : "") +
      '<div class="n">Shares: of 96,096 distinct people; of 3,095 sellers.</div>';
  }
  var sortBtns = Array.prototype.slice.call(document.querySelectorAll("[data-sort]"));
  var reorderTimer = null;
  function sortStates(key) {
    var arr = D.states.slice();
    var cmp = {
      people: function (a, b) { return b.ps - a.ps || (a.code < b.code ? -1 : 1); },
      sellers: function (a, b) { return b.ss - a.ss || b.ps - a.ps; },
      // Gap = customer share minus seller share; most customer-heavy first.
      gap: function (a, b) { return (b.ps - b.ss) - (a.ps - a.ss); }
    }[key];
    arr.sort(cmp);
    arr.forEach(function (s, i) { RE[s.code].style.transform = "translate(0px," + (top0 + i * rh) + "px)"; });
    sortBtns.forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.sort === key ? "true" : "false"); });
    // Match DOM order to the new visual order (for Tab) after the move.
    clearTimeout(reorderTimer);
    reorderTimer = setTimeout(function () { arr.forEach(function (s) { cov.appendChild(RE[s.code]); }); }, 480);
  }
  sortBtns.forEach(function (b) { b.addEventListener("click", function () { sortStates(b.dataset.sort); }); });

  var pick = document.getElementById("st-pick");
  var selState = null;
  function selectState(code) {
    selState = code || null;
    Object.keys(RE).forEach(function (k) {
      RE[k].classList.toggle("sel", k === selState);
      RE[k].setAttribute("aria-pressed", k === selState ? "true" : "false");
    });
    pick.value = selState || "";
    var s = selState && SI[selState];
    document.getElementById("st-readout").innerHTML = s
      ? "<b>" + s.name + " (" + s.code + ")</b> · " + s.people + " customer people (" + s.psl + ") · " + s.sellers + " sellers (" + s.ssl + ")" + (s.sellers === "0" ? " · customers, no sellers" : "")
      : "Pick a state, or click a row, to highlight it.";
  }
  pick.addEventListener("change", function () { selectState(pick.value); });
  Object.keys(RE).forEach(function (k) {
    var g = RE[k], s = SI[k];
    g.setAttribute("data-tip-owner", "");
    g.addEventListener("click", function (e) { selectState(selState === k ? null : k); showTip(stateTip(s), e.pageX, e.pageY); });
    g.addEventListener("pointermove", function (e) { if (e.pointerType === "mouse") showTip(stateTip(s), e.pageX, e.pageY); });
    g.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse") hideTip(); });
    g.addEventListener("focus", function () { tipNear(stateTip(s), g); });
    g.addEventListener("blur", hideTip);
    g.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectState(selState === k ? null : k); }
    });
  });

  // ------------------------------------------------------------- start
  Array.prototype.forEach.call(document.querySelectorAll("[data-js]"), function (e) { e.hidden = false; });
  lastCompact = host.clientWidth < 640;
  setRange(range[0], range[1]);
  setBand("all");
  selectState(null);
  document.documentElement.classList.add("js");
})();
