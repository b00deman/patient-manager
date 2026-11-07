/* ============================================================
   BADAWI PHARMACY — الملف المشترك بين الصفحات الثلاث
   الدخول / الثيم واللغة / التنقل / صندوق رسائل المخزون / الطباعة الحرارية
   ============================================================ */
(function () {
  "use strict";

  var I18N = {
    brand: {ar:"صيدلية بدوي", en:"Badawi Pharmacy"},
    brand_sub: {ar:"نظام البيع والشراء والمخزون", en:"POS, Purchases & Inventory"},
    login_title: {ar:"صيدلية بدوي", en:"Badawi Pharmacy"},
    login_sub: {ar:"سجّل الدخول للمتابعة", en:"Sign in to continue"},
    login_user: {ar:"اسم المستخدم", en:"Username"},
    login_pass: {ar:"كلمة المرور", en:"Password"},
    login_btn: {ar:"دخول", en:"Sign in"},
    ph_user: {ar:"اسم المستخدم", en:"username"},
    ph_pass: {ar:"كلمة المرور", en:"password"},
    theme_tip: {ar:"تبديل الوضع الفاتح/الداكن", en:"Toggle theme"},
    logout: {ar:"خروج", en:"Logout"},
    change_pw: {ar:"كلمة المرور", en:"Password"},
    user: {ar:"المستخدم", en:"User"},
    role_admin: {ar:"مدير", en:"Admin"},
    role_user: {ar:"مستخدم", en:"User"},
    nav_pos: {ar:"🧾 الصيدلية / البيع", en:"🧾 Pharmacy / POS"},
    nav_inventory: {ar:"📦 المخزون والمشتريات", en:"📦 Inventory"},
    nav_reports: {ar:"📊 التقارير", en:"📊 Reports"},
    nav_locked: {ar:"لا صلاحية", en:"No permission"},
    alert_prefix: {ar:"⚠️ أدوية قاربت على النفاد (أقل من", en:"⚠️ Low stock (below"},
    alert_suffix: {ar:"عبوة)", en:"packs)"},
    alert_btn: {ar:"عرض التفاصيل", en:"Show details"},
    msg_title: {ar:"⚠️ تنبيه المخزون", en:"⚠️ Stock alert"},
    msg_text: {ar:"الأدوية التالية كميتها أقل من الحد المسموح، يرجى طلبها:", en:"The following items are below the minimum stock, please reorder:"},
    msg_ok: {ar:"فهمت", en:"Got it"},
    msg_qty: {ar:"عبوة", en:"packs"},
    item_unit: {ar:"صنف", en:"item(s)"},
    tamper: {ar:"⛔ تم اكتشاف محاولة تعديل أو عبث في ملفات البيانات — راجع النسخة الاحتياطية فوراً.", en:"⛔ Data tampering detected — check the encrypted backup immediately."},
    restored: {ar:"♻️ تمت استعادة البيانات من آخر نسخة احتياطية مشفّرة.", en:"♻️ Data restored from the latest encrypted backup."},
    close: {ar:"إغلاق", en:"Close"},
    print_btn: {ar:"🖨️ طباعة حرارية", en:"🖨️ Thermal print"},
    pw_title: {ar:"تغيير كلمة المرور", en:"Change password"},
    pw_old: {ar:"كلمة المرور الحالية", en:"Current password"},
    pw_new: {ar:"كلمة المرور الجديدة (8 أحرف على الأقل)", en:"New password (8+ chars)"},
    pw_new_en: {ar:"كلمة المرور الجديدة", en:"New password"},
    pw_save: {ar:"حفظ", en:"Save"},
    camera_title: {ar:"مسح الباركود بالكاميرا", en:"Scan barcode with camera"},
    camera_no: {ar:"المتصفح لا يدعم مسح الباركود بالكاميرا — استخدم الماسح العادي (يدخل كـ Enter).", en:"Camera barcode scanning is not supported — use your USB scanner instead."},
    rc_invoice: {ar:"فاتورة رقم", en:"Invoice"},
    rc_date: {ar:"التاريخ", en:"Date"},
    rc_cashier: {ar:"البائع", en:"Cashier"},
    rc_payment: {ar:"الدفع", en:"Payment"},
    rc_cash: {ar:"كاش", en:"Cash"},
    rc_card: {ar:"شبكة", en:"Card"},
    rc_item: {ar:"الصنف", en:"Item"},
    rc_qty: {ar:"الكمية", en:"Qty"},
    rc_price: {ar:"السعر", en:"Price"},
    rc_amount: {ar:"المبلغ", en:"Amount"},
    rc_subtotal: {ar:"المجموع", en:"Subtotal"},
    rc_vat: {ar:"ضريبة القيمة المضافة", en:"VAT"},
    rc_total: {ar:"الإجمالي", en:"Total"},
    rc_received: {ar:"المستلم", en:"Received"},
    rc_change: {ar:"الباقي", en:"Change"},
    rc_ref: {ar:"مرجع الشبكة", en:"Card ref"},
    rc_thanks: {ar:"شكراً لزيارتكم · نسأل الله الشفاء للجميع", en:"Thank you for your visit · Get well soon"},
    rc_copy: {ar:"نسخة العميل", en:"Customer copy"},
    total_label: {ar:"الإجمالي", en:"Total"},
    save_ok: {ar:"تم الحفظ بنجاح", en:"Saved successfully"},
    error: {ar:"حدث خطأ", en:"Something went wrong"},
    /* ---------- صفحة الصيدلية / نقطة البيع ---------- */
    pos_title: {ar:"قسم الصيدلية — نقطة البيع", en:"Pharmacy — Point of Sale"},
    pos_sub: {ar:"امسح باركود الدواء فيظهر الاسم والسعر فوراً. كل الحقول قابلة للتعديل يدوياً قبل الدفع.", en:"Scan a barcode to load name and price. Every field is editable before payment."},
    scan_title: {ar:"🔎 مسح الباركود", en:"🔎 Barcode scan"},
    scan_hint: {ar:"الماسح يكتب الرقم كأنه لوحة مفاتيح ويضغط Enter تلقائياً — أبقِ المؤشر في هذا الحقل.", en:"The scanner types the code and presses Enter — keep the cursor in this field."},
    barcode_label: {ar:"الباركود", en:"Barcode"},
    barcode_ph: {ar:"امسح الباركود هنا…", en:"Scan barcode here…"},
    scan_btn: {ar:"إضافة للفاتورة", en:"Add to invoice"},
    camera_btn: {ar:"📷 مسح بالكاميرا", en:"📷 Camera scan"},
    decode_title: {ar:"ترجمة الباركود", en:"Barcode decoding"},
    cart_title: {ar:"🧾 الفاتورة الحالية", en:"🧾 Current invoice"},
    cart_hint: {ar:"عدّل الاسم أو السعر أو الكمية يدوياً من الجدول — أي تعديل يُسجّل في سجل التدقيق.", en:"Edit name, price or qty inline — every override is written to the audit log."},
    th_barcode: {ar:"الباركود", en:"Barcode"}, th_drug: {ar:"الدواء", en:"Drug"},
    th_price: {ar:"السعر", en:"Price"}, th_qty: {ar:"الكمية", en:"Qty"},
    th_total: {ar:"المبلغ", en:"Amount"}, th_act: {ar:"", en:""},
    cart_empty: {ar:"الفاتورة فارغة — امسح أول باركود للبدء", en:"Invoice is empty — scan a barcode to start"},
    remove: {ar:"حذف", en:"Remove"},
    pay_title: {ar:"💰 طريقة الدفع", en:"💰 Payment method"},
    pay_hint: {ar:"اختر زراً واحداً من الزرين الجاهزين (بدون قوائم منسدلة).", en:"Pick one of the two ready buttons (no dropdowns)."},
    pay_cash: {ar:"💵 كاش", en:"💵 Cash"}, pay_card: {ar:"💳 شبكة", en:"💳 Card"},
    received_label: {ar:"المبلغ المستلم", en:"Amount received"},
    change_label: {ar:"الباقي", en:"Change"},
    card_ref_label: {ar:"رقم المرجع / آخر 4 أرقام (اختياري)", en:"Reference / last 4 digits (optional)"},
    pay_btn: {ar:"✅ دفع وطباعة", en:"✅ Pay & print"},
    clear_btn: {ar:"فاتورة جديدة", en:"New invoice"},
    reprint_btn: {ar:"🖨️ إعادة طباعة آخر فاتورة", en:"🖨️ Reprint last invoice"},
    not_found: {ar:"❌ الباركود غير مسجّل في المخزون — أضفه من صفحة المخزون أولاً", en:"❌ Barcode not in inventory — add it from the Inventory page"},
    added: {ar:"✓ تمت الإضافة", en:"✓ Added"},
    override: {ar:"تعديل يدوي", en:"Manual override"},
    /* ---------- صفحة المخزون ---------- */
    inv_title: {ar:"📦 المخزون والمشتريات", en:"📦 Inventory & Purchases"},
    inv_sub: {ar:"إدخال الأدوية المشتراة بالباركود، تعديل المخزون، منح الصلاحيات وإعدادات النظام — التعديل للمدير فقط.", en:"Register purchased drugs, adjust stock, grant permissions and configure — editing is admin-only."},
    entry_title: {ar:"➕ إدخال عملية شراء / دواء جديد", en:"➕ New purchase / drug"},
    entry_hint: {ar:"امسح الباركود ← تُرجمته تظهر أدناه ← اكتب اسم الدواء وسعر الشراء وسعر البيع والكمية.", en:"Scan → decoded info appears below → enter name, cost, sell price and quantity."},
    inv_barcode_label: {ar:"باركود الدواء", en:"Drug barcode"},
    inv_barcode_ph: {ar:"امسح الباركود هنا…", en:"Scan barcode here…"},
    decode_btn: {ar:"ترجمة الباركود", en:"Decode barcode"},
    drug_name: {ar:"اسم الدواء", en:"Drug name"},
    sell_price: {ar:"سعر البيع", en:"Sell price"},
    cost_price: {ar:"سعر الشراء", en:"Cost price"},
    qty_bought: {ar:"الكمية المشتراة (عبوات)", en:"Purchased qty (packs)"},
    expiry: {ar:"تاريخ الصلاحية", en:"Expiry date"},
    supplier: {ar:"المورد", en:"Supplier"},
    note: {ar:"ملاحظة", en:"Note"},
    save_purchase: {ar:"💾 حفظ الشراء وتحديث المخزون", en:"💾 Save purchase & update stock"},
    reset_btn: {ar:"تفريغ الحقول", en:"Clear fields"},
    stock_title: {ar:"📋 المخزون الحالي", en:"📋 Current stock"},
    stock_search: {ar:"بحث بالاسم أو الباركود…", en:"Search by name or barcode…"},
    th_sell: {ar:"سعر البيع", en:"Sell"}, th_cost: {ar:"سعر الشراء", en:"Cost"},
    th_expiry: {ar:"الصلاحية", en:"Expiry"}, th_edit: {ar:"تعديل", en:"Edit"},
    th_status: {ar:"الحالة", en:"Status"},
    edit_btn: {ar:"تعديل", en:"Edit"}, save_btn: {ar:"حفظ", en:"Save"},
    cancel_btn: {ar:"إلغاء", en:"Cancel"},
    locked_msg: {ar:"🔒 هذا القسم للمدير فقط — لا يمكنك التعديل أو منح الصلاحيات.", en:"🔒 Admin only — you cannot edit or grant permissions."},
    status_ok: {ar:"متوفر", en:"In stock"}, status_low: {ar:"قارب على النفاد", en:"Low stock"}, status_out: {ar:"نافد", en:"Out of stock"},
    users_title: {ar:"👥 المستخدمون والصلاحيات", en:"👥 Users & permissions"},
    users_hint: {ar:"أنت فقط من يستطيع إنشاء المستخدمين ومنح الصلاحيات أو سحبها.", en:"Only you can create users and grant or revoke permissions."},
    new_user: {ar:"اسم المستخدم (إنجليزي)", en:"Username (latin)"},
    new_name: {ar:"الاسم الظاهر", en:"Display name"},
    new_pass: {ar:"كلمة المرور (8+)", en:"Password (8+)"},
    new_perms: {ar:"الصلاحيات الممنوحة", en:"Granted permissions"},
    add_user_btn: {ar:"إضافة مستخدم", en:"Add user"},
    perm_sell: {ar:"البيع", en:"Sell"}, perm_stock: {ar:"عرض المخزون", en:"View stock"},
    perm_reports: {ar:"التقارير", en:"Reports"}, perm_print: {ar:"إعادة الطباعة", en:"Reprint"},
    active: {ar:"مفعّل", en:"Active"},
    settings_title: {ar:"⚙️ إعدادات الصيدلية", en:"⚙️ Pharmacy settings"},
    pharmacy_name_lbl: {ar:"اسم الصيدلية (على الإيصال)", en:"Pharmacy name (on receipt)"},
    pharmacy_sub_lbl: {ar:"العنوان / السطر الثاني", en:"Subtitle / address"},
    currency_lbl: {ar:"العملة", en:"Currency"},
    vat_lbl: {ar:"ضريبة القيمة المضافة %", en:"VAT %"},
    low_stock_lbl: {ar:"حد التنبيه (عبوات)", en:"Low-stock threshold (packs)"},
    save_settings: {ar:"حفظ الإعدادات", en:"Save settings"},
    backup_btn: {ar:"💽 نسخة احتياطية مشفّرة", en:"💽 Encrypted backup"},
    backups_title: {ar:"النسخ الاحتياطية", en:"Backups"},
    edit_stock_title: {ar:"تعديل صنف", en:"Edit item"},
    /* ---------- صفحة التقارير ---------- */
    rep_title: {ar:"📊 التقارير وكل البيانات", en:"📊 Reports & all data"},
    rep_sub: {ar:"كل المبيعات والمشتريات والمخزون وسجل التغييرات — مع إجماليات وفلاتر بالتاريخ.", en:"Every sale, purchase, stock item and audit event — with totals and date filters."},
    stat_sales: {ar:"إجمالي المبيعات", en:"Total sales"},
    stat_purchases: {ar:"إجمالي المشتريات", en:"Total purchases"},
    stat_profit: {ar:"هامش الربح التقديري", en:"Estimated margin"},
    stat_invoices: {ar:"عدد الفواتير", en:"Invoices"},
    from_date: {ar:"من تاريخ", en:"From date"}, to_date: {ar:"إلى تاريخ", en:"To date"},
    apply_btn: {ar:"تطبيق", en:"Apply"}, export_csv: {ar:"⬇️ تصدير CSV (نص عادي)", en:"⬇️ Export CSV (plain text)"},
    tab_sales: {ar:"المبيعات", en:"Sales"}, tab_purchases: {ar:"المشتريات", en:"Purchases"},
    tab_stock: {ar:"المخزون", en:"Stock"}, tab_audit: {ar:"سجل التدقيق", en:"Audit log"},
    th_invoice: {ar:"الفاتورة", en:"Invoice"}, th_date: {ar:"التاريخ", en:"Date"},
    th_user: {ar:"المستخدم", en:"User"}, th_items: {ar:"الأصناف", en:"Items"},
    th_payment: {ar:"الدفع", en:"Payment"}, th_action: {ar:"", en:""},
    th_op: {ar:"العملية", en:"Action"}, th_detail: {ar:"التفاصيل", en:"Details"},
    print_invoice: {ar:"طباعة", en:"Print"}, no_data: {ar:"لا توجد بيانات", en:"No data"},
    audit_ok: {ar:"✓ سلسلة التدقيق سليمة — لم يُعبث بالبيانات", en:"✓ Audit chain intact — no tampering detected"},
    audit_broken: {ar:"⛔ سلسلة التدقيق مكسورة — يوجد تلاعب", en:"⛔ Audit chain broken — tampering detected"},
    rep_locked: {ar:"🔒 التقارير تحتاج صلاحية من المدير.", en:"🔒 Reports require permission from the admin."}
  };

  var PH = {
    user: null, config: null, perms: [], prefs: {lang:"ar", theme:"light"},
    alerts: [], page: (document.body.getAttribute("data-page") || "pos"),
    t: function (k) {
      var e = I18N[k];
      if (!e) return k;
      if (e[this.prefs.lang] !== undefined) return e[this.prefs.lang];
      return e.ar !== undefined ? e.ar : k;
    },
    esc: function (s) {
      return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
        return {"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c];
      });
    },
    money: function (v) { return (Number(v) || 0).toFixed(2); },
    has: function (p) {
      if (!this.user) return false;
      if (this.user.role === "admin") return true;
      return !!(this.user.perms && this.user.perms[p]);
    },
    api: async function (path, opts) {
      opts = opts || {};
      var res = await fetch(path, {
        method: opts.method || "GET",
        credentials: "same-origin",
        headers: {"Content-Type": "application/json"},
        body: opts.body ? JSON.stringify(opts.body) : undefined
      });
      var data = {};
      try { data = await res.json(); } catch (e) {}
      if (res.status === 401 && !opts.silent401) PH.showLogin(data.message || "");
      if (!res.ok) {
        var err = new Error(data.message || ("HTTP " + res.status));
        err.code = data.code; err.status = res.status;
        throw err;
      }
      return data;
    },
    toast: function (msg, isError) {
      var el = document.getElementById("phToast");
      if (!el) return;
      el.textContent = msg;
      el.className = "toast show" + (isError ? " error" : "");
      clearTimeout(PH._toastTimer);
      PH._toastTimer = setTimeout(function () { el.className = "toast"; }, 3200);
    },
    err: function (e) { PH.toast(e && e.message ? e.message : PH.t("error"), true); }
  };
  window.PH = PH;

  /* ---------------- الثيم واللغة ---------------- */
  function readPrefs() {
    try {
      var p = JSON.parse(localStorage.getItem("ph_prefs") || "{}");
      if (p.lang === "ar" || p.lang === "en") PH.prefs.lang = p.lang;
      if (p.theme === "light" || p.theme === "dark") PH.prefs.theme = p.theme;
    } catch (e) {}
  }
  function applyPrefs() {
    var h = document.documentElement;
    h.setAttribute("data-theme", PH.prefs.theme);
    h.lang = PH.prefs.lang;
    h.dir = PH.prefs.lang === "ar" ? "rtl" : "ltr";
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      el.textContent = PH.t(el.getAttribute("data-i18n"));
    });
    document.querySelectorAll("[data-i18n-ph]").forEach(function (el) {
      el.placeholder = PH.t(el.getAttribute("data-i18n-ph"));
    });
    document.querySelectorAll("[data-i18n-title]").forEach(function (el) {
      el.title = PH.t(el.getAttribute("data-i18n-title"));
    });
    var a = document.getElementById("langAr"), b = document.getElementById("langEn");
    if (a && b) {
      a.classList.toggle("active", PH.prefs.lang === "ar");
      b.classList.toggle("active", PH.prefs.lang === "en");
    }
  }
  PH.applyPrefs = applyPrefs;
  PH.setLang = function (lang) {
    PH.prefs.lang = lang;
    localStorage.setItem("ph_prefs", JSON.stringify(PH.prefs));
    PH.api("/api/prefs", {method:"POST", body:{lang:lang}, silent401:true}).catch(function(){});
    applyPrefs();
    document.dispatchEvent(new CustomEvent("ph:lang"));
  };
  PH.toggleTheme = function () {
    PH.prefs.theme = PH.prefs.theme === "dark" ? "light" : "dark";
    localStorage.setItem("ph_prefs", JSON.stringify(PH.prefs));
    PH.api("/api/prefs", {method:"POST", body:{theme:PH.prefs.theme}, silent401:true}).catch(function(){});
    applyPrefs();
  };

  /* ---------------- الهيكل المشترك ---------------- */
  function chromeHTML() {
    return '' +
    '<div class="topcontrols">' +
      '<div class="brand-mini"><img class="bm-l" src="/brand-left.jpg" alt="">' +
      '<img class="bm-n" src="/brand-name.png" alt=""><img class="bm-r" src="/brand-right.jpg" alt=""></div>' +
      '<div class="ctl-group"><div class="seg">' +
        '<button class="seg-btn active" id="langAr" onclick="PH.setLang(\'ar\')">عربي</button>' +
        '<button class="seg-btn" id="langEn" onclick="PH.setLang(\'en\')">EN</button>' +
      '</div>' +
      '<button class="ctl-btn" id="themeBtn" onclick="PH.toggleTheme()" data-i18n-title="theme_tip">' +
      '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg></button>' +
      '</div></div>' +
    '<div class="container" id="chromeBody">' +
      '<div class="tamper-banner" id="tamperBanner"></div>' +
      '<div class="alert-banner" id="alertBanner"><span class="ab-icon">⚠️</span><span id="alertText"></span>' +
        '<button class="btn-mini ab-btn" id="alertBtn" data-i18n="alert_btn">عرض التفاصيل</button></div>' +
      '<div class="topbar"><div class="topbar-user"><span data-i18n="user">المستخدم</span>: <b id="topUser"></b>' +
        '<span class="role-badge" id="topRole"></span></div>' +
        '<div class="topbar-actions">' +
          '<button class="btn-mini" id="pwBtn" data-i18n="change_pw">كلمة المرور</button>' +
          '<button class="btn-mini btn-logout" id="logoutBtn" data-i18n="logout">خروج</button>' +
        '</div></div>' +
      '<nav class="navbar">' +
        '<a class="nav-link" id="navPos" href="/" data-i18n="nav_pos">🧾 الصيدلية / البيع</a>' +
        '<a class="nav-link" id="navInv" href="/inventory" data-i18n="nav_inventory">📦 المخزون والمشتريات</a>' +
        '<a class="nav-link" id="navRep" href="/reports" data-i18n="nav_reports">📊 التقارير</a>' +
      '</nav>' +
    '</div>';
  }

  function loginHTML() {
    return '<div class="login-card">' +
      '<div class="login-logo" id="loginLogo" data-i18n="login_title">صيدلية بدوي</div>' +
      '<div class="login-sub" data-i18n="login_sub">سجّل الدخول للمتابعة</div>' +
      '<div class="login-field"><label data-i18n="login_user">اسم المستخدم</label>' +
        '<input id="loginUser" autocomplete="username" data-i18n-ph="ph_user"></div>' +
      '<div class="login-field"><label data-i18n="login_pass">كلمة المرور</label>' +
        '<input id="loginPass" type="password" autocomplete="current-password" data-i18n-ph="ph_pass"></div>' +
      '<button class="login-btn" id="loginBtn" data-i18n="login_btn">دخول</button>' +
      '<div class="login-error" id="loginErr"></div></div>';
  }

  function modalsHTML() {
    return '' +
    '<div class="modal-overlay" id="msgOverlay"><div class="modal">' +
      '<div class="msg-icon">⚠️</div><div class="msg-title" data-i18n="msg_title">⚠️ تنبيه المخزون</div>' +
      '<div class="msg-text" id="msgText" data-i18n="msg_text"></div>' +
      '<div class="msg-list" id="msgList"></div>' +
      '<div class="btn-row"><button class="btn btn-primary" id="msgOk" data-i18n="msg_ok">فهمت</button></div>' +
    '</div></div>' +
    '<div class="modal-overlay" id="pwOverlay"><div class="modal">' +
      '<h2 data-i18n="pw_title">تغيير كلمة المرور</h2>' +
      '<div class="form-grid"><div class="form-group"><label data-i18n="pw_old">كلمة المرور الحالية</label><input type="password" id="pwOld"></div>' +
      '<div class="form-group"><label id="pwNewLbl" data-i18n="pw_new_en">كلمة المرور الجديدة</label><input type="password" id="pwNew"></div></div>' +
      '<div class="btn-row"><button class="btn btn-secondary" data-close="pwOverlay" data-i18n="close">إغلاق</button>' +
      '<button class="btn btn-primary" id="pwSave" data-i18n="pw_save">حفظ</button></div></div></div>' +
    '<div class="modal-overlay" id="cameraOverlay"><div class="modal">' +
      '<h2 data-i18n="camera_title">مسح الباركود بالكاميرا</h2>' +
      '<video id="cameraVideo" autoplay playsinline muted></video>' +
      '<div class="hint" id="cameraHint"></div>' +
      '<div class="btn-row"><button class="btn btn-secondary" data-close="cameraOverlay" data-i18n="close">إغلاق</button></div>' +
    '</div></div>' +
    '<div class="modal-overlay" id="receiptModal"><div class="modal">' +
      '<div id="receiptArea"></div>' +
      '<div class="btn-row"><button class="btn btn-secondary" data-close="receiptModal" data-i18n="close">إغلاق</button>' +
      '<button class="btn btn-primary" id="receiptPrint" data-i18n="print_btn">🖨️ طباعة حرارية</button></div>' +
    '</div></div>' +
    '<div class="toast" id="phToast"></div>';
  }

  /* ---------------- صندوق رسائل المخزون (لكل المستخدمين) ---------------- */
  PH.showMsgBox = function (force) {
    var items = PH.alerts || [];
    if (!items.length && !force) return;
    document.getElementById("msgList").innerHTML = items.length
      ? items.map(function (d) {
          return '<div class="msg-item"><span>' + PH.esc(d.name) + ' <span class="mono">' + PH.esc(d.barcode) + '</span></span>' +
                 '<b>' + PH.esc(d.qty) + ' ' + PH.t("msg_qty") + '</b></div>';
        }).join("")
      : '<div class="empty-msg">—</div>';
    document.getElementById("msgText").textContent = PH.t("msg_text");
    document.getElementById("msgOverlay").classList.add("show");
  };

  PH.checkAlerts = async function (showOnChange) {
    if (!PH.user) return;
    try {
      var r = await PH.api("/api/alerts", {silent401:true});
      PH.alerts = r.alerts || [];
      PH.threshold = r.threshold || 15;
      var banner = document.getElementById("alertBanner");
      var txt = document.getElementById("alertText");
      if (PH.alerts.length) {
        txt.textContent = PH.t("alert_prefix") + " " + PH.threshold + " " + PH.t("alert_suffix") +
                          " — " + PH.alerts.length + " " + PH.t("item_unit");
        banner.classList.add("show");
      } else {
        banner.classList.remove("show");
      }
      var sig = PH.alerts.map(function (d) { return d.barcode + ":" + d.qty; }).sort().join("|");
      var seen = sessionStorage.getItem("ph_alert_sig") || "";
      if (sig && sig !== seen) {
        sessionStorage.setItem("ph_alert_sig", sig);
        PH.showMsgBox(true);
      }
      if (!sig) sessionStorage.removeItem("ph_alert_sig");
      if (showOnChange) document.dispatchEvent(new CustomEvent("ph:alerts", {detail: PH.alerts}));
    } catch (e) {}
  };

  /* ---------------- الإيصال الحراري 80mm ----------------
     كروم لا يدعم size:80mm auto، لذا نحسب ارتفاع الورقة من طول الفاتورة
     ونحقن @page بحجم 80mm × الارتفاع الفعلي (يناسب لفة الورق الحراري). */
  PH.setThermalPage = function () {
    var area = document.getElementById("receiptArea");
    if (!area) return;
    var px = area.scrollHeight || 400;
    var mm = Math.max(60, Math.ceil(px * 25.4 / 96) + 10);
    var st = document.getElementById("phPageSize");
    if (!st) { st = document.createElement("style"); st.id = "phPageSize"; document.head.appendChild(st); }
    st.textContent = "@page{size:80mm " + mm + "mm;margin:0}";
  };

  PH.printReceipt = function (sale, cfg, auto) {
    cfg = cfg || PH.config || {};
    var cur = PH.esc(cfg.currency || "ر.س");
    var rows = (sale.items || []).map(function (i) {
      return '<tr><td>' + PH.esc(i.name) + '<br><span style="font-size:9px">' + PH.esc(i.barcode) + '</span></td>' +
        '<td>' + PH.esc(i.qty) + '</td><td>' + PH.money(i.price) + '</td>' +
        '<td>' + PH.money(Number(i.price) * Number(i.qty)) + '</td></tr>';
    }).join("");
    var vatRow = Number(sale.vat) > 0
      ? '<div class="r-line"><span>' + PH.t("rc_vat") + ' (' + PH.esc(cfg.vat_percent) + '%)</span><span>' + PH.money(sale.vat) + ' ' + cur + '</span></div>' : "";
    var cashRow = sale.payment === "cash"
      ? '<div class="r-line"><span>' + PH.t("rc_received") + '</span><span>' + PH.money(sale.received) + ' ' + cur + '</span></div>' +
        '<div class="r-line"><span>' + PH.t("rc_change") + '</span><span>' + PH.money(sale.change) + ' ' + cur + '</span></div>'
      : (sale.card_ref ? '<div class="r-line"><span>' + PH.t("rc_ref") + '</span><span>' + PH.esc(sale.card_ref) + '</span></div>' : "");
    var html = '<div class="rc">' +
      '<div class="r-name">' + PH.esc(cfg.pharmacy_name || PH.t("brand")) + '</div>' +
      '<div class="r-sub">' + PH.esc(cfg.pharmacy_sub || "") + '</div>' +
      '<div class="r-meta">' + PH.t("rc_invoice") + ': <b>' + PH.esc(sale.invoice) + '</b><br>' +
        PH.t("rc_date") + ': ' + PH.esc(sale.ts) + '<br>' +
        PH.t("rc_cashier") + ': ' + PH.esc(sale.user) + ' &nbsp;|&nbsp; ' +
        PH.t("rc_payment") + ': ' + (sale.payment === "cash" ? PH.t("rc_cash") : PH.t("rc_card")) + '</div>' +
      '<table><thead><tr><th>' + PH.t("rc_item") + '</th><th>' + PH.t("rc_qty") + '</th>' +
        '<th>' + PH.t("rc_price") + '</th><th>' + PH.t("rc_amount") + '</th></tr></thead><tbody>' + rows + '</tbody></table>' +
      '<div class="r-tot">' +
        '<div class="r-line"><span>' + PH.t("rc_subtotal") + '</span><span>' + PH.money(sale.subtotal) + ' ' + cur + '</span></div>' +
        vatRow + cashRow +
        '<div class="r-grand r-line"><span>' + PH.t("rc_total") + '</span><span>' + PH.money(sale.total) + ' ' + cur + '</span></div>' +
      '</div>' +
      '<div class="r-foot">' + PH.t("rc_thanks") + '<br>' + PH.t("rc_copy") + '</div>' +
      '<div class="r-barcode">' + PH.esc(sale.invoice) + '</div></div>';
    document.getElementById("receiptArea").innerHTML = html;
    document.getElementById("receiptModal").classList.add("show");
    PH.lastReceipt = sale;
    PH.setThermalPage();
    if (auto) requestAnimationFrame(function () { PH.setThermalPage(); window.print(); });
  };

  /* ---------------- مسح بالكاميرا (إن توفر BarcodeDetector) ---------------- */
  PH.openCamera = function (onCode) {
    var ov = document.getElementById("cameraOverlay");
    ov.classList.add("show");
    var video = document.getElementById("cameraVideo");
    var hint = document.getElementById("cameraHint");
    var stream = null, raf = 0, stopped = false;
    var close = function () {
      stopped = true;
      cancelAnimationFrame(raf);
      if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
      ov.classList.remove("show");
      video.srcObject = null;
    };
    ov._cleanup = close;
    if (!("BarcodeDetector" in window) || !navigator.mediaDevices) {
      hint.textContent = PH.t("camera_no");
      return;
    }
    hint.textContent = "…";
    var detector;
    try { detector = new BarcodeDetector({formats:["ean_13","ean_8","upc_a","code_128","code_39","qr_code"]}); }
    catch (e) { detector = null; }
    navigator.mediaDevices.getUserMedia({video:{facingMode:"environment"}}).then(function (s) {
      if (stopped) { s.getTracks().forEach(function (t) { t.stop(); }); return; }
      stream = s; video.srcObject = s; video.play();
      hint.textContent = "وجّه الكاميرا نحو الباركود…";
      var tick = async function () {
        if (stopped || !detector) return;
        try {
          var codes = await detector.detect(video);
          if (codes && codes.length) { close(); onCode(codes[0].rawValue); return; }
        } catch (e) {}
        raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    }).catch(function () { hint.textContent = PH.t("camera_no"); });
  };

  /* ---------------- الدخول ---------------- */
  PH.showLogin = function (msg) {
    document.getElementById("loginView").classList.add("show");
    document.getElementById("loginView").style.display = "flex";
    var body = document.getElementById("chromeBody");
    if (body) body.style.display = "none";
    var pv = document.getElementById("pageView");
    if (pv) pv.hidden = true;
    document.getElementById("loginErr").textContent = msg || "";
    setTimeout(function () { var u = document.getElementById("loginUser"); if (u) u.focus(); }, 100);
  };

  async function doLogin() {
    var u = document.getElementById("loginUser").value.trim();
    var p = document.getElementById("loginPass").value;
    var btn = document.getElementById("loginBtn");
    btn.disabled = true;
    try {
      await PH.api("/api/login", {method:"POST", body:{username:u, password:p}, silent401:true});
      location.reload();
    } catch (e) {
      document.getElementById("loginErr").textContent = e.message || "";
      btn.disabled = false;
    }
  }

  /* ---------------- التشغيل ---------------- */
  async function boot() {
    readPrefs();
    var chrome = document.getElementById("phChrome");
    var login = document.getElementById("loginView");
    var modals = document.getElementById("phModals");
    if (chrome) chrome.innerHTML = chromeHTML();
    if (login) login.innerHTML = loginHTML();
    if (modals) modals.innerHTML = modalsHTML();
    applyPrefs();

    document.getElementById("loginBtn").addEventListener("click", doLogin);
    document.getElementById("loginPass").addEventListener("keydown", function (e) {
      if (e.key === "Enter") doLogin();
    });
    document.getElementById("logoutBtn").addEventListener("click", async function () {
      try { await PH.api("/api/logout", {method:"POST", body:{}, silent401:true}); } catch (e) {}
      location.reload();
    });
    document.getElementById("pwBtn").addEventListener("click", function () {
      document.getElementById("pwOverlay").classList.add("show");
    });
    document.getElementById("pwSave").addEventListener("click", async function () {
      try {
        await PH.api("/api/change-password", {method:"POST", body:{
          old: document.getElementById("pwOld").value,
          new: document.getElementById("pwNew").value
        }});
        PH.toast(PH.t("save_ok"));
        document.getElementById("pwOverlay").classList.remove("show");
        document.getElementById("pwOld").value = ""; document.getElementById("pwNew").value = "";
      } catch (e) { PH.err(e); }
    });
    document.getElementById("msgOk").addEventListener("click", function () {
      document.getElementById("msgOverlay").classList.remove("show");
    });
    document.getElementById("alertBtn").addEventListener("click", function () { PH.showMsgBox(true); });
    document.getElementById("receiptPrint").addEventListener("click", function () { PH.setThermalPage(); window.print(); });
    document.addEventListener("click", function (e) {
      var c = e.target.closest ? e.target.closest("[data-close]") : null;
      if (c) {
        var ov = document.getElementById(c.getAttribute("data-close"));
        if (ov) {
          if (ov._cleanup) ov._cleanup(); else ov.classList.remove("show");
        }
      }
      if (e.target.classList && e.target.classList.contains("modal-overlay")) e.target.classList.remove("show");
    });

    var me;
    try { me = await PH.api("/api/me", {silent401:true}); }
    catch (e) { PH.showLogin(""); return; }
    PH.user = me.user; PH.config = me.config || {}; PH.perms = me.perms || [];
    if (me.prefs) {
      if (me.prefs.lang === "ar" || me.prefs.lang === "en") PH.prefs.lang = me.prefs.lang;
      if (me.prefs.theme === "light" || me.prefs.theme === "dark") PH.prefs.theme = me.prefs.theme;
    }
    applyPrefs();
    document.getElementById("topUser").textContent = PH.user.name || PH.user.username;
    var role = document.getElementById("topRole");
    role.textContent = PH.user.role === "admin" ? PH.t("role_admin") : PH.t("role_user");
    role.className = "role-badge " + (PH.user.role === "admin" ? "role-admin" : "role-user");
    document.getElementById("loginLogo").textContent = PH.config.pharmacy_name || PH.t("login_title");
    document.title = (PH.config.pharmacy_name || PH.t("brand")) + " — " + PH.t("brand_sub");

    var navPos = document.getElementById("navPos"), navInv = document.getElementById("navInv"), navRep = document.getElementById("navRep");
    if (!PH.has("sell")) { navPos.classList.add("locked"); navPos.href = "#"; navPos.title = PH.t("nav_locked"); }
    if (!PH.has("reports")) { navRep.classList.add("locked"); navRep.href = "#"; navRep.title = PH.t("nav_locked"); }
    document.getElementById("nav" + ({pos:"Pos", inventory:"Inv", reports:"Rep"}[PH.page] || "Pos")).classList.add("active");
    navPos.addEventListener("click", function (e) { if (navPos.classList.contains("locked")) { e.preventDefault(); PH.toast(PH.t("nav_locked"), true); } });
    navRep.addEventListener("click", function (e) { if (navRep.classList.contains("locked")) { e.preventDefault(); PH.toast(PH.t("nav_locked"), true); } });

    var tb = document.getElementById("tamperBanner");
    if (me.warning === "tampered" || me.warning === "audit_broken") tb.textContent = PH.t("tamper");
    else if (me.warning === "restored") tb.textContent = PH.t("restored");
    if (me.warning) tb.classList.add("show");

    document.getElementById("loginView").classList.remove("show");
    document.getElementById("loginView").style.display = "none";
    var pv = document.getElementById("pageView");
    if (pv) pv.hidden = false;

    PH.checkAlerts();
    setInterval(function () { PH.checkAlerts(); }, 20000);
    document.dispatchEvent(new CustomEvent("ph:ready", {detail: me}));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
