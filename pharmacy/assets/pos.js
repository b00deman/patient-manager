/* ============================================================
   صفحة الصيدلية (POS): باركود → اسم/سعر → تعديل يدوي → زرَي دفع → طباعة حرارية
   ============================================================ */
(function () {
  "use strict";
  var cart = [], payment = null, suggestionTimer = null, suggestions = [], selectedDrug = null, searchSeq = 0;

  function el(id) { return document.getElementById(id); }
  function cfg() { return PH.config || {}; }
  function total() {
    var subtotal = cart.reduce(function (s, i) { return s + Number(i.price) * Number(i.qty); }, 0);
    var vat = subtotal * (Number(cfg().vat_percent) || 0) / 100;
    return {subtotal: subtotal, vat: vat, total: subtotal + vat};
  }

  function render() {
    var body = el("cartBody");
    el("cartEmpty").hidden = cart.length > 0;
    el("cartTable").hidden = cart.length === 0;
    body.innerHTML = cart.map(function (i, idx) {
      var changed = (i.name !== i.original_name || Number(i.price) !== Number(i.original_price));
      return '<tr>' +
        '<td class="mono cell-num">' + PH.esc(i.barcode || "—") + '</td>' +
        '<td><input class="cell" data-i="' + idx + '" data-f="name" value="' + PH.esc(i.name) + '">' +
          (changed ? '<span class="badge badge-warn" style="margin-top:4px">' + PH.t("override") + '</span>' : '') +
        '</td>' +
        '<td><input class="cell cell-num" type="number" min="0" step="0.01" data-i="' + idx + '" data-f="price" value="' + PH.money(i.price) + '"></td>' +
        '<td><input class="cell cell-num" type="number" min="1" step="1" data-i="' + idx + '" data-f="qty" value="' + PH.esc(i.qty) + '"></td>' +
        '<td class="cell-num"><b>' + PH.money(Number(i.price) * Number(i.qty)) + '</b></td>' +
        '<td><button class="btn btn-del btn-sm" data-del="' + idx + '" data-i18n="remove">حذف</button></td>' +
      '</tr>';
    }).join("");
    var t = total();
    el("totalVal").textContent = PH.money(t.total);
    el("curLbl").textContent = PH.esc(cfg().currency || "جنيه سوداني");
    updateChange();
    updatePayButton();
  }

  function updateChange() {
    var t = total().total;
    var r = el("receivedInput").value;
    var rec = (r === "" ? t : Number(r));
    el("changeInput").value = PH.money(Math.max(0, rec - t));
  }

  function updatePayButton() {
    var pending = [el("manualName").value, el("manualPrice").value, el("manualQty").value].some(function (v) { return String(v).trim() !== ""; });
    var qty = Number(el("manualQty").value), price = Number(el("manualPrice").value);
    var validManual = !!el("manualName").value.trim() && el("manualPrice").value !== "" &&
      isFinite(price) && price >= 0 && Number.isInteger(qty) && qty >= 1;
    el("payBtn").disabled = !((cart.length > 0 || validManual) && !(pending && !validManual) && payment && PH.has("sell"));
  }

  function showDecode(dec, drug) {
    var box = el("decodeBox");
    box.hidden = false;
    var valid = dec.valid === null ? "" :
      '<span class="kv">✓ <b>' + (dec.valid ? "رقم التحقق صحيح" : "رقم التحقق غير صحيح ✗") + '</b></span>';
    var found = drug
      ? '<br><span class="kv">💊 <b>' + PH.esc(drug.name) + '</b></span>' +
        '<span class="kv">💰 <b>' + PH.money(drug.sell_price) + ' ' + PH.esc(cfg().currency || "جنيه سوداني") + '</b></span>' +
        '<span class="kv">📦 <b>' + PH.esc(drug.qty) + '</b> عبوة</span>'
      : '<br><span class="badge badge-bad">' + PH.t("not_found") + '</span>';
    box.innerHTML = '<div style="font-weight:800;margin-bottom:4px">' + PH.t("decode_title") + '</div>' +
      '<span class="kv">🔢 <b class="mono">' + PH.esc(dec.code) + '</b></span>' +
      '<span class="kv">🏷️ <b>' + PH.esc(dec.type) + '</b></span>' +
      '<span class="kv">🔍 <b>' + PH.esc(dec.note) + '</b></span>' + valid + found;
  }

  async function scan(code) {
    code = String(code || "").trim();
    if (!code) return;
    try {
      var r = await PH.api("/api/lookup?barcode=" + encodeURIComponent(code));
      showDecode(r.decode, r.drug);
      if (!r.drug) { PH.toast(PH.t("not_found"), true); return; }
      var existing = cart.find(function (x) { return x.barcode === r.drug.barcode; });
      if (existing) existing.qty = Number(existing.qty) + 1;
      else cart.push({
        barcode: r.drug.barcode, name: r.drug.name,
        price: Number(r.drug.sell_price), qty: 1,
        original_price: Number(r.drug.sell_price), original_name: r.drug.name
      });
      render();
      PH.toast(PH.t("added"));
    } catch (e) { PH.err(e); }
    finally {
      el("barcodeInput").value = "";
      el("barcodeInput").focus();
    }
  }

  function addManualLine() {
    var name = el("manualName").value.trim();
    var rawPrice = el("manualPrice").value;
    var price = Number(el("manualPrice").value);
    var qty = Number(el("manualQty").value);
    var pending = [name, rawPrice, el("manualQty").value].some(function (v) { return String(v).trim() !== ""; });
    if (!pending) return true;
    if (!name || el("manualPrice").value === "" || !isFinite(price) || price < 0 || !Number.isInteger(qty) || qty < 1) {
      PH.toast("أدخل اسم الدواء والسعر والكمية بشكل صحيح", true);
      return false;
    }
    var matched = selectedDrug && selectedDrug.name === name ? selectedDrug : null;
    cart.push({barcode:matched ? matched.barcode : "", manual:!matched, name:name, price:price, qty:qty,
      original_price:price, original_name:name});
    ["manualName", "manualPrice", "manualQty"].forEach(function (id) { el(id).value = ""; });
    selectedDrug = null;
    el("drugSuggestions").hidden = true;
    render();
    return true;
  }

  function searchDrugs(query) {
    clearTimeout(suggestionTimer);
    query = query.trim();
    var box = el("drugSuggestions");
    if (!query) { suggestions = []; box.hidden = true; return; }
    suggestionTimer = setTimeout(async function () {
      var seq = ++searchSeq;
      try {
        var r = await PH.api("/api/drug-search?q=" + encodeURIComponent(query));
        if (seq !== searchSeq || el("manualName").value.trim() !== query) return;
        suggestions = r.drugs || [];
        box.innerHTML = suggestions.length ? suggestions.map(function (d, i) {
          return '<button type="button" class="autocomplete-item" data-suggestion="' + i + '"><span>' +
            PH.esc(d.name) + '</span><small>' + PH.money(d.sell_price) + ' ' + PH.esc(cfg().currency || "جنيه سوداني") +
            ' · ' + PH.esc(d.qty) + ' متوفر</small></button>';
        }).join("") : '<div class="empty-msg">' + PH.t("no_drug_matches") + '</div>';
        box.hidden = false;
      } catch (e) { box.hidden = true; }
    }, 180);
  }

  function selectSuggestion(index) {
    var drug = suggestions[index];
    if (!drug) return;
    selectedDrug = drug;
    el("manualName").value = drug.name;
    el("manualPrice").value = Number(drug.sell_price).toFixed(2);
    el("drugSuggestions").hidden = true;
    el("manualQty").focus();
    updatePayButton();
  }

  function selectPayment(p) {
    payment = p;
    el("payCash").classList.toggle("selected", p === "cash");
    el("payCard").classList.toggle("selected", p === "card");
    el("cashFields").hidden = p !== "cash";
    el("cardFields").hidden = p !== "card";
    updatePayButton();
  }

  async function pay() {
    if (!addManualLine()) return;
    if (!cart.length || !payment) return;
    render();
    var btn = el("payBtn");
    btn.disabled = true;
    try {
      var r = await PH.api("/api/sale", {
        method: "POST",
        body: {
          items: cart.map(function (i) {
            return {barcode: i.barcode, manual: !!i.manual, name: i.name, price: Number(i.price), qty: Number(i.qty)};
          }),
          payment: payment,
          received: payment === "cash" ? (el("receivedInput").value === "" ? null : Number(el("receivedInput").value)) : null,
          card_ref: payment === "card" ? el("cardRef").value.trim() : ""
        }
      });
      cart = [];
      el("receivedInput").value = "";
      el("cardRef").value = "";
      selectPayment(null);
      render();
      PH.printReceipt(r.sale, r.config, PH.has("print"));
      PH.toast("✅ " + r.sale.invoice + " — " + PH.money(r.sale.total) + " " + PH.esc(r.config.currency || ""));
      PH.checkAlerts(true);
    } catch (e) {
      PH.err(e);
    } finally {
      btn.disabled = false;
      updatePayButton();
      el("barcodeInput").focus();
    }
  }

  document.addEventListener("ph:ready", function () {
    if (!PH.has("sell")) {
      PH.toast(PH.t("nav_locked") + " (" + PH.t("perm_sell") + ")", true);
    }
    if (!PH.has("print")) el("reprintBtn").hidden = true;
    el("curLbl").textContent = PH.esc(cfg().currency || "جنيه سوداني");
    el("barcodeInput").addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); scan(this.value); }
    });
    el("addBtn").addEventListener("click", function () { scan(el("barcodeInput").value); });
    ["manualName", "manualPrice", "manualQty"].forEach(function (id) {
      el(id).addEventListener("input", updatePayButton);
    });
    el("manualName").addEventListener("input", function () {
      selectedDrug = null;
      searchDrugs(this.value);
    });
    el("drugSuggestions").addEventListener("click", function (e) {
      var item = e.target.closest ? e.target.closest("[data-suggestion]") : null;
      if (item) selectSuggestion(Number(item.getAttribute("data-suggestion")));
    });
    el("cameraBtn").addEventListener("click", function () {
      PH.openCamera(function (code) { el("barcodeInput").value = code; scan(code); });
    });
    el("cartBody").addEventListener("input", function (e) {
      var t = e.target;
      if (!t.classList.contains("cell")) return;
      var i = Number(t.getAttribute("data-i")), f = t.getAttribute("data-f");
      var v = f === "name" ? t.value : Number(t.value);
      if (f !== "name" && (!isFinite(v) || v < 0)) return;
      if (f === "qty" && v < 1) return;
      cart[i][f] = v;
      var t2 = total();
      el("totalVal").textContent = PH.money(t2.total);
      var row = t.closest("tr");
      if (row) {
        row.children[4].innerHTML = "<b>" + PH.money(Number(cart[i].price) * Number(cart[i].qty)) + "</b>";
      }
      updateChange();
    });
    el("cartBody").addEventListener("change", function () { render(); });
    el("cartBody").addEventListener("click", function (e) {
      var b = e.target.closest ? e.target.closest("[data-del]") : null;
      if (b) { cart.splice(Number(b.getAttribute("data-del")), 1); render(); el("barcodeInput").focus(); }
    });
    el("payCash").addEventListener("click", function () { selectPayment("cash"); });
    el("payCard").addEventListener("click", function () { selectPayment("card"); });
    el("receivedInput").addEventListener("input", updateChange);
    el("payBtn").addEventListener("click", pay);
    el("clearBtn").addEventListener("click", function () {
      cart = []; el("receivedInput").value = ""; selectPayment(null); render(); el("barcodeInput").focus();
    });
    el("reprintBtn").addEventListener("click", async function () {
      try {
        var r = await PH.api("/api/last-invoice");
        if (r.sale) PH.printReceipt(r.sale, r.config, false);
        else PH.toast(PH.t("no_data"), true);
      } catch (e) { PH.err(e); }
    });
    // لو الماسح كتب والمؤشر خارج الحقل → نوجّهه تلقائياً لحقل الباركود
    document.addEventListener("keydown", function (e) {
      var a = document.activeElement;
      var inField = a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName);
      if (!inField && e.key.length === 1 && /[0-9]/.test(e.key)) {
        el("barcodeInput").focus();
      }
    });
    render();
    setTimeout(function () { el("barcodeInput").focus(); }, 200);
  });
})();
