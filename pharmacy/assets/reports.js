/* ============================================================
   صفحة التقارير: كل المبيعات + المشتريات + المخزون + سجل التدقيق
   ============================================================ */
(function () {
  "use strict";
  var sales = [], purchases = [], drugs = [], audit = [], auditValid = true;
  var tab = "sales", from = "", to = "";

  function el(id) { return document.getElementById(id); }
  function cur() { return PH.esc((PH.config || {}).currency || "ر.س"); }
  function inRange(ts) {
    var d = String(ts || "").slice(0, 10);
    if (from && d < from) return false;
    if (to && d > to) return false;
    return true;
  }
  function n(v) { return Number(v) || 0; }

  function computeStats() {
    var s = sales.filter(function (x) { return inRange(x.ts); });
    var p = purchases.filter(function (x) { return inRange(x.ts); });
    var sumSales = s.reduce(function (a, x) { return a + n(x.total); }, 0);
    var sumPurch = p.reduce(function (a, x) { return a + n(x.cost_price) * n(x.qty); }, 0);
    var margin = s.reduce(function (a, x) {
      return a + (x.items || []).reduce(function (b, i) {
        return b + (n(i.price) - n(i.cost_price)) * n(i.qty);
      }, 0);
    }, 0);
    el("stSales").textContent = PH.money(sumSales) + " " + cur();
    el("stPurch").textContent = PH.money(sumPurch) + " " + cur();
    el("stProfit").textContent = PH.money(margin) + " " + cur();
    el("stCount").textContent = String(s.length);
  }

  function head(cols) {
    return "<tr>" + cols.map(function (c) { return "<th>" + PH.t(c) + "</th>"; }).join("") + "</tr>";
  }

  function render() {
    var rows = "", cols = [];
    if (tab === "sales") {
      cols = ["th_invoice", "th_date", "th_user", "th_items", "th_payment", "th_total", "th_action"];
      var list = sales.filter(function (x) { return inRange(x.ts); });
      rows = list.map(function (s, idx) {
        var items = (s.items || []).map(function (i) {
          return PH.esc(i.name) + " × " + PH.esc(i.qty) +
                 (i.override ? ' <span class="badge badge-warn">' + PH.t("override") + "</span>" : "");
        }).join("<br>");
        var pay = s.payment === "cash" ? PH.t("rc_cash") : PH.t("rc_card");
        return "<tr><td class='mono'><b>" + PH.esc(s.invoice) + "</b></td>" +
          "<td class='cell-num'>" + PH.esc(s.ts) + "</td><td>" + PH.esc(s.user) + "</td>" +
          "<td>" + items + "</td><td><span class='badge badge-info'>" + pay + "</span></td>" +
          "<td class='cell-num'><b>" + PH.money(s.total) + " " + cur() + "</b></td>" +
          "<td>" + (PH.has("print")
            ? "<button class='btn btn-secondary btn-sm' data-print='" + idx + "'>" + PH.t("print_invoice") + "</button>"
            : "") + "</td></tr>";
      }).join("");
    } else if (tab === "purchases") {
      cols = ["th_date", "th_user", "th_barcode", "drug_name", "th_qty", "th_cost", "th_sell", "th_expiry", "supplier", "note"];
      rows = purchases.filter(function (x) { return inRange(x.ts); }).map(function (p) {
        return "<tr><td class='cell-num'>" + PH.esc(p.ts) + "</td><td>" + PH.esc(p.user) + "</td>" +
          "<td class='mono'>" + PH.esc(p.barcode) + "</td><td>" + PH.esc(p.name) + "</td>" +
          "<td class='cell-num'>" + PH.esc(p.qty) + "</td><td class='cell-num'>" + PH.money(p.cost_price) + "</td>" +
          "<td class='cell-num'>" + PH.money(p.sell_price) + "</td><td>" + PH.esc(p.expiry || "—") + "</td>" +
          "<td>" + PH.esc(p.supplier || "—") + "</td><td>" + PH.esc(p.note || "—") + "</td></tr>";
      }).join("");
    } else if (tab === "stock") {
      cols = ["th_barcode", "drug_name", "th_sell", "th_cost", "th_qty", "th_expiry", "supplier", "th_status"];
      var limit = Number((PH.config || {}).low_stock) || 15;
      rows = drugs.map(function (d) {
        var q = n(d.qty);
        var st = q <= 0 ? '<span class="badge badge-bad">' + PH.t("status_out") + "</span>"
          : q < limit ? '<span class="badge badge-warn">' + PH.t("status_low") + "</span>"
          : '<span class="badge badge-ok">' + PH.t("status_ok") + "</span>";
        return "<tr><td class='mono'>" + PH.esc(d.barcode) + "</td><td>" + PH.esc(d.name) + "</td>" +
          "<td class='cell-num'>" + PH.money(d.sell_price) + "</td><td class='cell-num'>" + PH.money(d.cost_price) + "</td>" +
          "<td class='cell-num'><b>" + PH.esc(q) + "</b></td><td>" + PH.esc(d.expiry || "—") + "</td>" +
          "<td>" + PH.esc(d.supplier || "—") + "</td><td>" + st + "</td></tr>";
      }).join("");
    } else {
      cols = ["th_date", "th_user", "th_op", "th_detail", "th_barcode"];
      rows = audit.map(function (a) {
        return "<tr><td class='cell-num'>" + PH.esc(a.ts) + "</td><td>" + PH.esc(a.user) + "</td>" +
          "<td><span class='badge badge-info'>" + PH.esc(a.action) + "</span></td>" +
          "<td style='max-width:480px;white-space:normal'>" + PH.esc(a.detail) + "</td>" +
          "<td class='mono'>" + PH.esc(String(a.h || "").slice(0, 12)) + "…</td></tr>";
      }).join("");
      el("auditState").innerHTML = auditValid
        ? '<span class="badge badge-ok">' + PH.t("audit_ok") + "</span>"
        : '<span class="badge badge-bad">' + PH.t("audit_broken") + "</span>";
    }
    if (tab !== "audit") el("auditState").innerHTML = "";
    el("repHead").innerHTML = head(cols);
    el("repBody").innerHTML = rows;
    el("repEmpty").hidden = !!rows;
    el("repTable").hidden = !rows;
  }

  async function loadAll() {
    var r1 = await PH.api("/api/sales");
    var r2 = await PH.api("/api/purchases");
    var r3 = await PH.api("/api/drugs");
    var r4 = await PH.api("/api/audit");
    sales = r1.sales || []; purchases = r2.purchases || [];
    drugs = r3.drugs || []; audit = r4.audit || [];
    auditValid = !!r4.valid;
    if (r1.config) PH.config = Object.assign(PH.config || {}, r1.config);
    computeStats();
    render();
  }

  document.addEventListener("ph:ready", async function () {
    if (!PH.has("reports")) {
      el("repContent").hidden = true;
      el("repLocked").style.display = "flex";
      return;
    }
    document.querySelectorAll(".tab-btn").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll(".tab-btn").forEach(function (x) { x.classList.remove("active"); });
        b.classList.add("active");
        tab = b.getAttribute("data-tab");
        render();
      });
    });
    el("applyFilter").addEventListener("click", function () {
      from = el("dateFrom").value; to = el("dateTo").value;
      computeStats(); render();
    });
    el("exportCsv").addEventListener("click", function () {
      var kind = (tab === "sales" || tab === "purchases") ? tab : "stock";
      window.location.href = "/api/export?type=" + kind;
    });
    el("repBody").addEventListener("click", function (e) {
      var b = e.target.closest ? e.target.closest("[data-print]") : null;
      if (!b) return;
      var idx = Number(b.getAttribute("data-print"));
      var list = sales.filter(function (x) { return inRange(x.ts); });
      if (list[idx]) PH.printReceipt(list[idx], PH.config, false);
    });
    document.addEventListener("ph:lang", function () { computeStats(); render(); });
    try { await loadAll(); } catch (e) { PH.err(e); }
  });
})();
