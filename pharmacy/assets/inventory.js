/* ============================================================
   صفحة المخزون: ترجمة باركود + إدخال مشتريات + تعديل + صلاحيات + إعدادات
   كل عمليات الكتابة محمية أيضاً على السيرفر (مدير فقط)
   ============================================================ */
(function () {
  "use strict";
  var drugs = [], users = [], editCode = null, search = "";

  function el(id) { return document.getElementById(id); }
  function isAdmin() { return PH.user && PH.user.role === "admin"; }
  function cur() { return PH.esc((PH.config || {}).currency || "ر.س"); }
  function threshold() { return Number((PH.config || {}).low_stock) || 15; }

  function statusOf(d) {
    var q = Number(d.qty) || 0;
    if (q <= 0) return '<span class="badge badge-bad">' + PH.t("status_out") + '</span>';
    if (q < threshold()) return '<span class="badge badge-warn">' + PH.t("status_low") + ' (' + q + ')</span>';
    return '<span class="badge badge-ok">' + PH.t("status_ok") + '</span>';
  }

  function renderStock() {
    var list = drugs.filter(function (d) {
      return !search || (String(d.name) + " " + String(d.barcode)).toLowerCase().indexOf(search.toLowerCase()) >= 0;
    });
    el("stockEmpty").hidden = list.length > 0;
    el("stockTable").hidden = list.length === 0;
    el("stockBody").innerHTML = list.map(function (d) {
      var editing = editCode === d.barcode;
      var cell = function (field, type, val) {
        return editing
          ? '<input class="cell" data-ef="' + field + '" type="' + (type || "text") + '" value="' + PH.esc(val == null ? "" : val) + '">'
          : PH.esc(val == null ? "—" : val);
      };
      var numCell = function (field, val) {
        return editing
          ? '<input class="cell cell-num" data-ef="' + field + '" type="number" step="0.01" min="0" value="' + PH.esc(val) + '">'
          : '<span class="cell-num">' + PH.money(Number(val) || 0) + '</span>';
      };
      var action = editing
        ? '<button class="btn btn-ok btn-sm" data-save="' + PH.esc(d.barcode) + '">' + PH.t("save_btn") + '</button> ' +
          '<button class="btn btn-secondary btn-sm" data-cancel="1">' + PH.t("cancel_btn") + '</button>'
        : (isAdmin() ? '<button class="btn btn-secondary btn-sm" data-edit="' + PH.esc(d.barcode) + '">' + PH.t("edit_btn") + '</button>' : '<span class="muted">🔒</span>');
      return '<tr data-code="' + PH.esc(d.barcode) + '">' +
        '<td class="mono cell-num">' + PH.esc(d.barcode) + '</td>' +
        '<td>' + cell("name", "text", d.name) + '</td>' +
        '<td>' + numCell("sell_price", d.sell_price) + '</td>' +
        '<td>' + numCell("cost_price", d.cost_price) + '</td>' +
        '<td>' + (editing
            ? '<input class="cell cell-num" data-ef="qty" type="number" step="1" min="0" value="' + PH.esc(d.qty) + '">'
            : '<b class="cell-num">' + PH.esc(d.qty) + '</b>') + '</td>' +
        '<td>' + cell("expiry", "date", d.expiry) + '</td>' +
        '<td>' + cell("supplier", "text", d.supplier) + '</td>' +
        '<td>' + statusOf(d) + '</td>' +
        '<td>' + action + '</td>' +
      '</tr>';
    }).join("");
  }

  async function loadDrugs() {
    try {
      var r = await PH.api("/api/drugs");
      drugs = r.drugs || [];
      if (r.config) PH.config = Object.assign(PH.config || {}, r.config);
      renderStock();
    } catch (e) {
      el("stockEmpty").textContent = PH.t("locked_msg");
      el("stockEmpty").hidden = false;
      el("stockTable").hidden = true;
    }
  }

  function showDecode(dec, drug) {
    var box = el("invDecodeBox");
    box.hidden = false;
    var valid = dec.valid === null ? "" :
      '<span class="kv">✅ <b>' + (dec.valid ? "رقم التحقق صحيح" : "رقم التحقق غير صحيح ✗") + '</b></span>';
    var linked = drug
      ? '<br><span class="badge badge-info">موجود مسبقاً: ' + PH.esc(drug.name) +
        ' — ' + PH.money(drug.sell_price) + ' ' + cur() + ' — ' + PH.esc(drug.qty) + ' عبوة</span>' +
        '<br><span class="muted">الحقول عُبّئت تلقائياً، والكمية المكتوبة ستُضاف للرصيد الحالي.</span>'
      : '<br><span class="badge badge-ok">باركود جديد — اكتب بيانات الدواء بالأسفل.</span>';
    box.innerHTML = '<div style="font-weight:800;margin-bottom:4px">' + PH.t("decode_title") + '</div>' +
      '<span class="kv">🔢 <b class="mono">' + PH.esc(dec.code) + '</b></span>' +
      '<span class="kv">🏷️ <b>' + PH.esc(dec.type) + '</b></span>' +
      '<span class="kv">🔍 <b>' + PH.esc(dec.note) + '</b></span>' + valid + linked;
  }

  async function decode(code, fill) {
    code = String(code || "").trim();
    if (!code) { PH.toast("اكتب أو امسح باركود", true); return; }
    try {
      var r = await PH.api("/api/lookup?barcode=" + encodeURIComponent(code));
      showDecode(r.decode, r.drug);
      if (fill !== false) {
        if (r.drug) {
          el("fName").value = r.drug.name || "";
          el("fCost").value = PH.money(r.drug.cost_price);
          el("fSell").value = PH.money(r.drug.sell_price);
          el("fExpiry").value = r.drug.expiry || "";
          el("fSupplier").value = r.drug.supplier || "";
        } else {
          ["fName", "fCost", "fSell", "fExpiry", "fSupplier"].forEach(function (id) { el(id).value = ""; });
          el("fCost").value = "0"; el("fSell").value = "0";
        }
        el("fQty").value = "1";
        el("fName").focus();
      }
    } catch (e) { PH.err(e); }
  }

  function clearPurchase() {
    ["invBarcode", "fName", "fCost", "fSell", "fQty", "fExpiry", "fSupplier", "fNote"].forEach(function (id) { el(id).value = ""; });
    el("fCost").value = "0"; el("fSell").value = "0"; el("fQty").value = "1";
    el("invDecodeBox").hidden = true;
    el("invBarcode").focus();
  }

  async function savePurchase() {
    var code = el("invBarcode").value.trim();
    if (!code) { PH.toast("امسح الباركود أولاً", true); el("invBarcode").focus(); return; }
    var body = {
      barcode: code, name: el("fName").value.trim(),
      cost_price: Number(el("fCost").value || 0), sell_price: Number(el("fSell").value || 0),
      qty: Number(el("fQty").value || 0), expiry: el("fExpiry").value,
      supplier: el("fSupplier").value.trim(), note: el("fNote").value.trim()
    };
    try {
      await PH.api("/api/purchase", {method:"POST", body:body});
      PH.toast(PH.t("save_ok") + " — " + body.name);
      clearPurchase();
      await loadDrugs();
      PH.checkAlerts(true);
    } catch (e) { PH.err(e); }
  }

  /* ---------------- المستخدمون ---------------- */
  function permLabels() {
    return {sell:PH.t("perm_sell"), stock:PH.t("perm_stock"),
            reports:PH.t("perm_reports"), print:PH.t("perm_print")};
  }

  function renderUsers() {
    var labels = permLabels();
    el("nuPerms").innerHTML = (PH.perms || []).map(function (p) {
      return '<label class="perm-item"><input type="checkbox" data-np="' + p + '"> ' + PH.esc(labels[p] || p) + '</label>';
    }).join("");
    el("usersList").innerHTML = users.map(function (u) {
      var admin = u.role === "admin";
      var boxes = (PH.perms || []).map(function (p) {
        var checked = admin || (u.perms && u.perms[p]);
        return '<label class="perm-item"><input type="checkbox" data-up="' + p + '" ' +
               (checked ? "checked" : "") + ' ' + (admin ? "disabled" : "") + '> ' +
               PH.esc(labels[p] || p) + '</label>';
      }).join("");
      return '<div class="user-row" data-user="' + PH.esc(u.username) + '">' +
        '<div class="user-row-head"><div><div class="user-name">' + PH.esc(u.name) +
          ' <span class="muted mono">@' + PH.esc(u.username) + '</span></div>' +
          '<div class="user-meta">' + (admin ? PH.t("role_admin") : PH.t("role_user")) + '</div></div>' +
          '<div><label class="perm-item"><input type="checkbox" data-active ' +
            (u.active ? "checked" : "") + ' ' + (admin ? "disabled" : "") + '> ' + PH.t("active") + '</label></div></div>' +
        '<div class="perm-list">' + boxes + '</div>' +
        '<div class="btn-row" style="margin-top:12px">' +
          '<input class="cell" type="password" data-newpass placeholder="' + PH.esc(PH.t("pw_new")) + '" style="max-width:220px">' +
          '<button class="btn btn-primary btn-sm" data-saveuser>' + PH.t("save_btn") + '</button>' +
          (admin ? "" : '<button class="btn btn-del btn-sm" data-deluser>' + PH.t("remove") + '</button>') +
        '</div></div>';
    }).join("");
  }

  async function loadUsers() {
    var r = await PH.api("/api/users");
    users = r.users || [];
    PH.perms = r.perms || PH.perms;
    renderUsers();
  }

  async function saveUser(row) {
    var username = row.getAttribute("data-user");
    var perms = {};
    row.querySelectorAll("[data-up]").forEach(function (c) { perms[c.getAttribute("data-up")] = c.checked; });
    var active = row.querySelector("[data-active]").checked;
    var pwd = row.querySelector("[data-newpass]").value;
    try {
      await PH.api("/api/users/update", {method:"POST", body:{
        username:username, perms:perms, active:active, password:pwd || undefined
      }});
      PH.toast(PH.t("save_ok"));
      await loadUsers();
    } catch (e) { PH.err(e); }
  }

  /* ---------------- الإعدادات ---------------- */
  function fillSettings() {
    var c = PH.config || {};
    el("sName").value = c.pharmacy_name || "";
    el("sSub").value = c.pharmacy_sub || "";
    el("sCur").value = c.currency || "ر.س";
    el("sVat").value = c.vat_percent || 0;
    el("sLow").value = c.low_stock || 15;
  }

  async function loadBackups() {
    try {
      var r = await PH.api("/api/backups");
      el("backupsList").innerHTML = (r.backups || []).slice(0, 12).map(function (b) {
        return '<div class="bk-row"><span class="bk-name mono">' + PH.esc(b.name) + '</span>' +
          '<span class="muted">' + PH.esc(b.time) + ' · ' + (b.size / 1024).toFixed(1) + ' KB · 🔒 مشفّرة</span></div>';
      }).join("") || '<div class="empty-msg">' + PH.t("no_data") + '</div>';
    } catch (e) {}
  }

  document.addEventListener("ph:ready", async function () {
    if (!isAdmin()) {
      ["entryCard", "usersCard", "settingsCard"].forEach(function (id) { el(id).hidden = true; });
      el("lockedBanner").style.display = "flex";
    }
    await loadDrugs();

    if (isAdmin()) {
      el("invBarcode").addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); decode(this.value); }
      });
      el("decodeBtn").addEventListener("click", function () { decode(el("invBarcode").value); });
      el("invCameraBtn").addEventListener("click", function () {
        PH.openCamera(function (code) { el("invBarcode").value = code; decode(code); });
      });
      el("savePurchase").addEventListener("click", savePurchase);
      el("resetPurchase").addEventListener("click", clearPurchase);

      el("stockSearch").addEventListener("input", function () { search = this.value; renderStock(); });
      el("stockBody").addEventListener("click", async function (e) {
        var t = e.target;
        var ed = t.closest ? t.closest("[data-edit]") : null;
        if (ed) { editCode = ed.getAttribute("data-edit"); renderStock(); return; }
        if (t.closest && t.closest("[data-cancel]")) { editCode = null; renderStock(); return; }
        var sv = t.closest ? t.closest("[data-save]") : null;
        if (sv) {
          var code = sv.getAttribute("data-save");
          var row = sv.closest("tr");
          var body = {barcode: code};
          row.querySelectorAll("[data-ef]").forEach(function (i) { body[i.getAttribute("data-ef")] = i.value; });
          try {
            await PH.api("/api/drug/update", {method:"POST", body:body});
            editCode = null;
            PH.toast(PH.t("save_ok"));
            await loadDrugs();
            PH.checkAlerts(true);
          } catch (err) { PH.err(err); }
        }
      });

      await loadUsers();
      el("usersList").addEventListener("click", async function (e) {
        var row = e.target.closest ? e.target.closest(".user-row") : null;
        if (!row) return;
        if (e.target.closest && e.target.closest("[data-saveuser]")) { await saveUser(row); return; }
        if (e.target.closest && e.target.closest("[data-deluser]")) {
          var username = row.getAttribute("data-user");
          if (!confirm("حذف المستخدم «" + username + "»؟")) return;
          try {
            await PH.api("/api/users/delete", {method:"POST", body:{username:username}});
            PH.toast(PH.t("save_ok")); await loadUsers();
          } catch (err) { PH.err(err); }
        }
      });
      el("addUserBtn").addEventListener("click", async function () {
        var perms = {};
        el("nuPerms").querySelectorAll("[data-np]").forEach(function (c) { perms[c.getAttribute("data-np")] = c.checked; });
        try {
          await PH.api("/api/users/add", {method:"POST", body:{
            username:el("nuUser").value.trim(), name:el("nuName").value.trim(),
            password:el("nuPass").value, perms:perms
          }});
          ["nuUser", "nuName", "nuPass"].forEach(function (id) { el(id).value = ""; });
          PH.toast(PH.t("save_ok")); await loadUsers();
        } catch (e) { PH.err(e); }
      });

      fillSettings();
      el("saveSettings").addEventListener("click", async function () {
        try {
          var r = await PH.api("/api/settings/update", {method:"POST", body:{
            pharmacy_name:el("sName").value, pharmacy_sub:el("sSub").value,
            currency:el("sCur").value, vat_percent:Number(el("sVat").value || 0),
            low_stock:Number(el("sLow").value || 15)
          }});
          PH.config = Object.assign(PH.config || {}, r.config);
          PH.toast(PH.t("save_ok"));
          renderStock();
          PH.checkAlerts(true);
        } catch (e) { PH.err(e); }
      });
      el("backupBtn").addEventListener("click", async function () {
        try {
          var r = await PH.api("/api/backup", {method:"POST", body:{}});
          PH.toast("💽 " + r.name);
          await loadBackups();
        } catch (e) { PH.err(e); }
      });
      await loadBackups();
    } else {
      el("stockSearch").addEventListener("input", function () { search = this.value; renderStock(); });
    }
  });
})();
