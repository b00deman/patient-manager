# -*- coding: utf-8 -*-
"""
صيدلية BADAWI — نظام البيع والشراء والمخزون   |   BADAWI PHARMACY
ثلاث صفحات منفصلة، واجهة بنفس شكل نظام المستشفى، بيانات مشفّرة ومحمية من العبث.

Pages :  /            -> نقطة البيع (الصيدلية)
         /inventory   -> المخزون والمشتريات والصلاحيات والإعدادات
         /reports     -> التقارير (كل المبيعات والمشتريات والبيانات)

Run   :  python "pharmacy.py"                 -> http://127.0.0.1:17761
         python "pharmacy.py" --port 18000
         python "pharmacy.py" --no-browser

Default login : badawi / Badawi@2026     (غيّرها من أول دخول)

No external packages — Python standard library only, exactly like the hospital app.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote


def _setup_console():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_setup_console()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
PAGES_DIR = os.path.join(BASE_DIR, "pages")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
DATA_DIR = os.path.join(BASE_DIR, "data")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
STORE_FILE = os.path.join(DATA_DIR, "store.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

PORT_DEFAULT = 17761
APP_TAG = "badawi-pharmacy"
DEFAULT_ADMIN_USER = "badawi"
DEFAULT_ADMIN_PASS = "Badawi@2026"

# الصلاحيات التي يستطيع المدير منحها للمستخدمين
PERMS = ["sell", "stock", "reports", "print"]
# هذه العمليات للمدير فقط ولا يمكن منحها أبداً
ADMIN_ONLY = ["purchase", "drug_edit", "users", "settings", "backup", "export"]

SESSIONS = {}                      # token -> (username, expiry epoch)
DATA_STATUS = {"warning": ""}      # "" | "restored" | "audit_broken" | "tampered"
STORE_LOCK = threading.RLock()

# نطاق المفتاح داخل الكود (نفس أسلوب نظام المستشفى) + HMAC يكشف أي تعديل يدوي
_SECRET = "badawi-pharmacy-2026-at-rest-key-7d2f9c41e8b65a03f"
_FORMAT = "PH1"
_KEYS_CACHE = {}


class TamperError(Exception):
    pass


# ------------------------------------------------------------------
#  التشفير  /  encrypt-then-MAC (stdlib only)
# ------------------------------------------------------------------

def _keys(salt):
    cached = _KEYS_CACHE.get(salt)
    if cached:
        return cached
    dk = hashlib.pbkdf2_hmac("sha256", _SECRET.encode("utf-8"), salt, 120000, 64)
    pair = (dk[:32], dk[32:])
    _KEYS_CACHE[salt] = pair
    return pair


def _xor_stream(data, key, nonce):
    n = len(data)
    out = bytearray(n)
    pos, ctr = 0, 0
    while pos < n:
        block = hmac.new(key, nonce + ctr.to_bytes(8, "big"), hashlib.sha256).digest()
        chunk = data[pos:pos + 32]
        for i in range(len(chunk)):
            out[pos + i] = chunk[i] ^ block[i]
        pos += 32
        ctr += 1
    return bytes(out)


def encrypt_store(obj):
    plain = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(16)
    ek, mk = _keys(salt)
    ct = _xor_stream(plain, ek, nonce)
    tag = hmac.new(mk, _FORMAT.encode() + salt + nonce + ct, hashlib.sha256).digest()
    return {
        "_format": _FORMAT,
        "_note": "بيانات مشفّرة - لا تُعدّل يدوياً / encrypted - do not edit",
        "salt": salt.hex(),
        "nonce": nonce.hex(),
        "tag": tag.hex(),
        "data": base64.b64encode(ct).decode("ascii"),
    }


def decrypt_store(env):
    if not isinstance(env, dict) or env.get("_format") != _FORMAT:
        raise TamperError("unknown format")
    try:
        salt = bytes.fromhex(env["salt"])
        nonce = bytes.fromhex(env["nonce"])
        tag = bytes.fromhex(env["tag"])
        ct = base64.b64decode(env["data"])
    except Exception:
        raise TamperError("bad envelope")
    ek, mk = _keys(salt)
    expect = hmac.new(mk, _FORMAT.encode() + salt + nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(expect, tag):
        raise TamperError("integrity check failed")
    plain = _xor_stream(ct, ek, nonce)
    try:
        return json.loads(plain.decode("utf-8"))
    except Exception:
        raise TamperError("bad payload")


def _atomic_write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


# ------------------------------------------------------------------
#  سلسلة التدقيق / hash-chained audit log
#  كل قيد يحتوي بصمة القيد اللي قبله ← أي حذف أو تعديل ينكشف
# ------------------------------------------------------------------

def _audit_payload(e):
    return json.dumps({k: e.get(k, "") for k in ("ts", "user", "action", "detail")},
                      ensure_ascii=False, sort_keys=True)


def _audit_hash(prev, e):
    return hashlib.sha256((prev + _audit_payload(e)).encode("utf-8")).hexdigest()


def append_audit(data, user, action, detail):
    log = data.setdefault("audit", [])
    prev = log[-1]["h"] if log else "0" * 64
    entry = {"ts": now_str(), "user": user, "action": action, "detail": detail, "prev": prev}
    entry["h"] = _audit_hash(prev, entry)
    log.append(entry)


def verify_audit(data):
    prev = "0" * 64
    for e in data.get("audit", []):
        if e.get("prev") != prev or e.get("h") != _audit_hash(prev, e):
            return False
        prev = e["h"]
    return True


# ------------------------------------------------------------------
#  مخزن البيانات المشفّر
# ------------------------------------------------------------------

DEFAULT_CONFIG = {
    "pharmacy_name": "صيدلية بدوي",
    "pharmacy_sub": "مستشفى الشيخ برير الشيخ الصديق",
    "currency": "ر.س",
    "vat_percent": 0.0,
    "low_stock": 15,
    "invoice_next": 1,
}


def default_store():
    return {"version": 1, "config": dict(DEFAULT_CONFIG), "drugs": [],
            "sales": [], "purchases": [], "audit": []}


def newest_backup_data():
    try:
        files = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith(".phbak")], reverse=True)
    except OSError:
        return None
    for f in files:
        try:
            data = decrypt_store(_read_json(os.path.join(BACKUP_DIR, f)))
            if isinstance(data, dict) and "drugs" in data:
                return data
        except Exception:
            continue
    return None


def load_store():
    if not os.path.exists(STORE_FILE):
        return default_store()
    try:
        data = decrypt_store(_read_json(STORE_FILE))
        if not isinstance(data, dict) or "drugs" not in data:
            raise TamperError("bad payload")
    except Exception:
        restored = newest_backup_data()
        if restored is not None:
            save_store(restored)
            DATA_STATUS["warning"] = "restored"
            return restored
        DATA_STATUS["warning"] = "tampered"
        return default_store()
    if not verify_audit(data):
        DATA_STATUS["warning"] = "audit_broken"
    else:
        DATA_STATUS["warning"] = ""
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(data.get("config") or {})
    data["config"] = cfg
    return data


def save_store(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    _atomic_write(STORE_FILE, json.dumps(encrypt_store(data), ensure_ascii=False, indent=2))
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        daily = os.path.join(BACKUP_DIR, "daily_%s.phbak" % today_str())
        _atomic_write(daily, json.dumps(encrypt_store(data), ensure_ascii=False, indent=2))
        files = sorted([f for f in os.listdir(BACKUP_DIR)
                        if f.startswith("daily_") and f.endswith(".phbak")], reverse=True)
        for f in files[30:]:
            try:
                os.remove(os.path.join(BACKUP_DIR, f))
            except OSError:
                pass
    except Exception:
        pass


def manual_backup(data):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    name = "manual_%s.phbak" % datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _atomic_write(os.path.join(BACKUP_DIR, name),
                  json.dumps(encrypt_store(data), ensure_ascii=False, indent=2))
    return name


def list_backups():
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        out = []
        for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
            if f.endswith(".phbak"):
                p = os.path.join(BACKUP_DIR, f)
                out.append({"name": f, "size": os.path.getsize(p),
                            "time": datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")})
        return out
    except OSError:
        return []


# ------------------------------------------------------------------
#  المستخدمون / كلمات المرور / الجلسات
# ------------------------------------------------------------------

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 120000)
    return salt + "$" + dk.hex()


def verify_password(password, stored):
    try:
        salt = stored.split("$", 1)[0]
        return hmac.compare_digest(hash_password(password, salt), stored)
    except Exception:
        return False


def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    try:
        data = decrypt_store(_read_json(USERS_FILE))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_users(users):
    os.makedirs(DATA_DIR, exist_ok=True)
    _atomic_write(USERS_FILE, json.dumps(encrypt_store(users), ensure_ascii=False, indent=2))


def ensure_admin():
    if os.path.exists(USERS_FILE):
        return
    save_users([{
        "username": DEFAULT_ADMIN_USER, "name": "بدوي",
        "password": hash_password(DEFAULT_ADMIN_PASS), "role": "admin",
        "perms": {p: True for p in PERMS}, "active": True, "created": now_str(),
    }])


def find_user(username):
    for u in load_users():
        if u["username"].lower() == str(username).lower():
            return u
    return None


def public_user(u):
    return {"username": u["username"], "name": u.get("name", u["username"]),
            "role": u.get("role", "user"),
            "perms": ({p: True for p in PERMS} if u.get("role") == "admin"
                      else {p: bool(u.get("perms", {}).get(p)) for p in PERMS}),
            "active": u.get("active", True)}


def has_perm(user, perm):
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    if perm in ADMIN_ONLY:
        return False
    return bool(user.get("perms", {}).get(perm))


# ------------------------------------------------------------------
#  الباركود / فك الترجمة والتحقق
# ------------------------------------------------------------------

def ean_check_digit(digits12):
    s = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(digits12))
    return str((10 - s % 10) % 10)


def decode_barcode(raw):
    code = re.sub(r"\s+", "", str(raw or ""))
    info = {"code": code, "type": "غير معروف", "valid": None, "note": ""}
    if not code:
        info["note"] = "باركود فارغ"
        return info
    if code.isdigit():
        n = len(code)
        if n == 13:
            info["type"] = "EAN-13"
            info["valid"] = (ean_check_digit(code[:12]) == code[12])
            info["note"] = "رقم التحقق " + ("صحيح ✓" if info["valid"] else "غير صحيح ✗")
        elif n == 12:
            info["type"] = "UPC-A"
            info["valid"] = (ean_check_digit("0" + code[:11]) == code[11])
            info["note"] = "يُقرأ كـ EAN-13: 0" + code
        elif n == 8:
            info["type"] = "EAN-8"
            info["valid"] = True
            info["note"] = "باركود قصير (8 خانات)"
        elif n == 14:
            info["type"] = "GTIN-14"
            info["valid"] = True
            info["note"] = "باركود كرتون/دفعة"
        else:
            info["type"] = "رقمي (%d خانات)" % n
            info["note"] = "باركود داخلي أو Code 128"
    else:
        info["type"] = "Code 128 / Code 39"
        info["note"] = "يحتوي حروفاً أو رموزاً — يُستخدم كما هو"
    return info


def find_drug(data, barcode):
    code = re.sub(r"\s+", "", str(barcode or ""))
    return next((d for d in data["drugs"] if str(d.get("barcode", "")) == code), None)


def num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def money(v):
    return round(float(v) + 1e-9, 2)


# ------------------------------------------------------------------
#  الإعدادات المحلية (لغة / ثيم) — غير حساسة
# ------------------------------------------------------------------

def load_prefs():
    d = _read_json(SETTINGS_FILE)
    return d if isinstance(d, dict) else {"lang": "ar", "theme": "light"}


def save_prefs(p):
    _atomic_write(SETTINGS_FILE, json.dumps(p, ensure_ascii=False, indent=2))


# ------------------------------------------------------------------
#  خادم الويب
# ------------------------------------------------------------------

PAGES = {
    "/": "pos.html",
    "/index.html": "pos.html",
    "/pos": "pos.html",
    "/pos.html": "pos.html",
    "/inventory": "inventory.html",
    "/inventory.html": "inventory.html",
    "/reports": "reports.html",
    "/reports.html": "reports.html",
}

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".ico": "image/x-icon", ".svg": "image/svg+xml",
}

BRAND_FILES = {
    "/brand-left.jpg": ("left_man.jpg", "image/jpeg"),
    "/brand-name.png": ("name.png", "image/png"),
    "/brand-right.jpg": ("right_man.jpg", "image/jpeg"),
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "BadawiPharmacy/1.0"

    def log_message(self, *args):
        pass

    # ---------- helpers ----------
    def _send(self, code, body, ctype, extra=None, cache="no-store"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, data, code=200, extra=None):
        self._send(code, json.dumps(data, ensure_ascii=False), "application/json; charset=utf-8", extra)

    def _err(self, code, msg, status=400):
        self._json({"status": "error", "code": code, "message": msg}, status)

    def _ok(self, **kw):
        out = {"status": "ok"}
        out.update(kw)
        self._json(out)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    def _token(self):
        cookie = self.headers.get("Cookie", "") or ""
        for part in cookie.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "ph_session" and v:
                return v
        return None

    def current_user(self):
        token = self._token()
        if not token:
            return None
        rec = SESSIONS.get(token)
        if not rec or rec[1] < datetime.now().timestamp():
            SESSIONS.pop(token, None)
            return None
        u = find_user(rec[0])
        if not u or not u.get("active", True):
            return None
        return u

    def guard(self, perm=None):
        u = self.current_user()
        if not u:
            self._err("login_required", "يجب تسجيل الدخول", 401)
            return None
        if perm and not has_perm(u, perm):
            msg = "هذه العملية للمدير فقط" if perm in ADMIN_ONLY else "لا تملك صلاحية لهذه العملية"
            self._err("admin_only" if perm in ADMIN_ONLY else "perm_denied", msg, 403)
            return None
        return u

    def _static(self, path):
        if path in BRAND_FILES:
            fname, ctype = BRAND_FILES[path]
            fpath = os.path.join(PROJECT_DIR, fname)
            if not os.path.exists(fpath):
                self._send(404, b"", "text/plain")
                return
            with open(fpath, "rb") as f:
                self._send(200, f.read(), ctype, cache="public, max-age=86400")
            return
        if path.startswith("/assets/"):
            name = os.path.basename(path)
            fpath = os.path.join(ASSETS_DIR, name)
            if not re.fullmatch(r"[A-Za-z0-9_.\-]+", name) or not os.path.exists(fpath):
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
            ext = os.path.splitext(name)[1].lower()
            with open(fpath, "rb") as f:
                self._send(200, f.read(), CONTENT_TYPES.get(ext, "application/octet-stream"),
                           cache="no-cache")
            return
        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def _page(self, name):
        path = os.path.join(PAGES_DIR, name)
        if not os.path.exists(path):
            self._send(500, "صفحة غير موجودة: " + name, "text/html; charset=utf-8")
            return
        with open(path, "r", encoding="utf-8") as f:
            self._send(200, f.read(), "text/html; charset=utf-8")

    # ---------- GET ----------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        q = parse_qs(parsed.query)

        if path in PAGES:
            self._page(PAGES[path])
            return
        if path.startswith("/assets/") or path in BRAND_FILES:
            self._static(path)
            return

        if path == "/api/ping":
            self._ok(app=APP_TAG, pid=os.getpid())
            return

        if path == "/api/me":
            u = self.current_user()
            if not u:
                self._err("login_required", "غير مسجل", 401)
                return
            with STORE_LOCK:
                data = load_store()
            self._ok(user=public_user(u), config=data["config"],
                     warning=DATA_STATUS["warning"], prefs=load_prefs(),
                     perms=PERMS, admin_only=ADMIN_ONLY)
            return

        if path == "/api/alerts":
            if not self.current_user():
                self._err("login_required", "غير مسجل", 401)
                return
            with STORE_LOCK:
                data = load_store()
            limit = num(data["config"].get("low_stock"), 15)
            low = [{"barcode": d.get("barcode", ""), "name": d.get("name", ""),
                    "qty": int(num(d.get("qty"))), "expiry": d.get("expiry", "")}
                   for d in data["drugs"] if num(d.get("qty")) < limit]
            self._ok(alerts=low, threshold=int(limit))
            return

        if path == "/api/lookup":
            if not self.guard():
                return
            raw = unquote(q.get("barcode", [""])[0])
            with STORE_LOCK:
                data = load_store()
            drug = find_drug(data, raw)
            self._ok(decode=decode_barcode(raw),
                     drug=({k: drug.get(k) for k in
                            ("barcode", "name", "sell_price", "cost_price", "qty", "expiry", "supplier", "min_stock")}
                           if drug else None))
            return

        if path == "/api/drugs":
            if not self.guard("stock"):
                return
            with STORE_LOCK:
                data = load_store()
            self._ok(drugs=data["drugs"], config=data["config"])
            return

        if path == "/api/sales":
            if not self.guard("reports"):
                return
            with STORE_LOCK:
                data = load_store()
            self._ok(sales=list(reversed(data["sales"])), config=data["config"])
            return

        if path == "/api/purchases":
            if not self.guard("reports"):
                return
            with STORE_LOCK:
                data = load_store()
            self._ok(purchases=list(reversed(data["purchases"])), config=data["config"])
            return

        if path == "/api/audit":
            if not self.guard("reports"):
                return
            with STORE_LOCK:
                data = load_store()
            self._ok(audit=list(reversed(data["audit"])), valid=verify_audit(data))
            return

        if path == "/api/users":
            if not self.guard("users"):
                return
            self._ok(users=[public_user(u) for u in load_users()], perms=PERMS)
            return

        if path == "/api/last-invoice":
            u = self.guard("print")
            if not u:
                return
            with STORE_LOCK:
                data = load_store()
            last = next((s for s in reversed(data["sales"]) if s.get("user") == u["username"]), None)
            self._ok(sale=last, config=data["config"])
            return

        if path == "/api/export":
            if not self.guard("export"):
                return
            kind = q.get("type", ["sales"])[0]
            with STORE_LOCK:
                data = load_store()
            import csv
            import io
            buf = io.StringIO()
            w = csv.writer(buf)
            if kind == "sales":
                w.writerow(["invoice", "ts", "user", "barcode", "name", "qty", "price", "line_total", "payment", "total"])
                for s in data["sales"]:
                    for it in s.get("items", []):
                        w.writerow([s.get("invoice"), s.get("ts"), s.get("user"), it.get("barcode"),
                                    it.get("name"), it.get("qty"), it.get("price"),
                                    money(num(it.get("price")) * num(it.get("qty"))),
                                    s.get("payment"), s.get("total")])
            elif kind == "purchases":
                w.writerow(["ts", "user", "barcode", "name", "cost_price", "sell_price", "qty", "expiry", "supplier"])
                for p in data["purchases"]:
                    w.writerow([p.get(k, "") for k in ("ts", "user", "barcode", "name", "cost_price", "sell_price", "qty", "expiry", "supplier")])
            else:
                w.writerow(["barcode", "name", "sell_price", "cost_price", "qty", "expiry", "supplier"])
                for d in data["drugs"]:
                    w.writerow([d.get(k, "") for k in ("barcode", "name", "sell_price", "cost_price", "qty", "expiry", "supplier")])
            append_audit(data, self.current_user()["username"], "export", "تصدير CSV: " + kind)
            save_store(data)
            self._send(200, "\ufeff" + buf.getvalue(), "text/csv; charset=utf-8",
                       extra=[("Content-Disposition", "attachment; filename=%s.csv" % kind)])
            return

        if path == "/api/backups":
            if not self.guard("backup"):
                return
            self._ok(backups=list_backups())
            return

        self._send(404, b"Not found", "text/plain; charset=utf-8")

    # ---------- POST ----------
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._body()

        if path == "/api/login":
            username = str(body.get("username", "")).strip()
            password = str(body.get("password", ""))
            u = find_user(username)
            if not u or not u.get("active", True) or not verify_password(password, u.get("password", "")):
                self._err("bad_credentials", "اسم المستخدم أو كلمة المرور غير صحيحة", 401)
                return
            token = secrets.token_urlsafe(32)
            SESSIONS[token] = (u["username"], datetime.now().timestamp() + 12 * 3600)
            self._json({"status": "ok", "user": public_user(u)}, 200,
                       extra=[("Set-Cookie", "ph_session=%s; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200" % token)])
            return

        if path == "/api/logout":
            token = self._token()
            if token:
                SESSIONS.pop(token, None)
            self._json({"status": "ok"}, 200,
                       extra=[("Set-Cookie", "ph_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")])
            return

        if path == "/api/change-password":
            u = self.guard()
            if not u:
                return
            old, new = str(body.get("old", "")), str(body.get("new", ""))
            if not verify_password(old, u.get("password", "")):
                self._err("bad_password", "كلمة المرور الحالية غير صحيحة", 400)
                return
            if len(new) < 8:
                self._err("short_password", "كلمة المرور الجديدة 8 أحرف على الأقل", 400)
                return
            users = load_users()
            for x in users:
                if x["username"] == u["username"]:
                    x["password"] = hash_password(new)
                    break
            save_users(users)
            with STORE_LOCK:
                data = load_store()
                append_audit(data, u["username"], "password", "تغيير كلمة المرور")
                save_store(data)
            self._ok()
            return

        if path == "/api/prefs":
            if not self.guard():
                return
            p = load_prefs()
            if body.get("lang") in ("ar", "en"):
                p["lang"] = body["lang"]
            if body.get("theme") in ("light", "dark"):
                p["theme"] = body["theme"]
            save_prefs(p)
            self._ok(prefs=p)
            return

        # ---------- البيع ----------
        if path == "/api/sale":
            u = self.guard("sell")
            if not u:
                return
            items = body.get("items") or []
            payment = body.get("payment")
            if payment not in ("cash", "card"):
                self._err("payment", "اختر طريقة الدفع: كاش أو شبكة", 400)
                return
            if not items:
                self._err("empty", "الفاتورة فارغة — امسح باركود أولاً", 400)
                return
            with STORE_LOCK:
                data = load_store()
                cfg = data["config"]
                clean, needed = [], {}
                for it in items:
                    code = re.sub(r"\s+", "", str(it.get("barcode", "")))
                    d = find_drug(data, code)
                    if not d:
                        self._err("unknown_drug", "باركود غير مسجّل في المخزون: " + code, 400)
                        return
                    qty = int(num(it.get("qty"), 0))
                    price = money(num(it.get("price"), d.get("sell_price")))
                    if qty < 1 or price < 0:
                        self._err("bad_line", "الكمية أو السعر غير صحيح (" + code + ")", 400)
                        return
                    needed[code] = needed.get(code, 0) + qty
                    override = (price != money(num(d.get("sell_price"))) or
                                str(it.get("name", "")).strip() != str(d.get("name", "")).strip())
                    clean.append({"barcode": code,
                                  "name": str(it.get("name") or d.get("name") or "").strip(),
                                  "price": price, "qty": qty,
                                  "cost_price": money(num(d.get("cost_price"))),
                                  "override": bool(override),
                                  "original_price": money(num(d.get("sell_price")))})
                for code, qty in needed.items():
                    d = find_drug(data, code)
                    if num(d.get("qty")) < qty:
                        self._err("no_stock", "الكمية غير كافية: %s (المتوفر %d)" %
                                  (d.get("name", code), int(num(d.get("qty")))), 400)
                        return
                subtotal = money(sum(num(i["price"]) * i["qty"] for i in clean))
                vat = money(subtotal * num(cfg.get("vat_percent"), 0) / 100.0)
                total = money(subtotal + vat)
                received = money(num(body.get("received"), total)) if payment == "cash" else total
                if payment == "cash" and received < total:
                    self._err("short_cash", "المبلغ المستلم أقل من الإجمالي", 400)
                    return
                change = money(received - total) if payment == "cash" else 0.0
                inv_no = int(num(cfg.get("invoice_next"), 1))
                cfg["invoice_next"] = inv_no + 1
                sale = {"id": "S%d" % inv_no, "invoice": "PH-%06d" % inv_no, "ts": now_str(),
                        "user": u["username"], "items": clean, "subtotal": subtotal, "vat": vat,
                        "total": total, "payment": payment, "received": received,
                        "change": change, "card_ref": str(body.get("card_ref", "")).strip() if payment == "card" else ""}
                for i in clean:
                    d = find_drug(data, i["barcode"])
                    d["qty"] = int(num(d.get("qty")) - i["qty"])
                    d["updated"] = now_str()
                data["sales"].append(sale)
                overrides = [i["barcode"] for i in clean if i["override"]]
                append_audit(data, u["username"], "sale",
                             "%s | %s | %.2f%s" % (sale["invoice"],
                             "كاش" if payment == "cash" else "شبكة", total,
                             " | تعديل يدوي: " + ",".join(overrides) if overrides else ""))
                save_store(data)
            self._json({"status": "ok", "sale": sale, "config": dict(cfg)})
            return

        # ---------- إدخال مشتريات / تعديل المخزون (مدير فقط) ----------
        if path == "/api/purchase":
            u = self.guard("purchase")
            if not u:
                return
            code = re.sub(r"\s+", "", str(body.get("barcode", "")))
            name = str(body.get("name", "")).strip()
            qty = int(num(body.get("qty"), 0))
            cost = money(num(body.get("cost_price"), 0))
            sell = money(num(body.get("sell_price"), 0))
            if not code or not name:
                self._err("missing", "الباركود واسم الدواء مطلوبان", 400)
                return
            if qty < 1 or sell < 0 or cost < 0:
                self._err("bad_values", "الكمية والأسعار يجب أن تكون أرقاماً صحيحة", 400)
                return
            with STORE_LOCK:
                data = load_store()
                d = find_drug(data, code)
                if d is None:
                    d = {"barcode": code, "name": name, "cost_price": cost,
                         "sell_price": sell, "qty": 0, "min_stock": None,
                         "expiry": str(body.get("expiry", "")).strip(),
                         "supplier": str(body.get("supplier", "")).strip(),
                         "created": now_str(), "updated": now_str()}
                    data["drugs"].append(d)
                else:
                    d["name"] = name
                    d["cost_price"] = cost
                    d["sell_price"] = sell
                    if body.get("expiry"):
                        d["expiry"] = str(body.get("expiry")).strip()
                    if body.get("supplier"):
                        d["supplier"] = str(body.get("supplier")).strip()
                    d["updated"] = now_str()
                d["qty"] = int(num(d.get("qty")) + qty)
                pur = {"id": "P%s%d" % (datetime.now().strftime("%Y%m%d%H%M%S"), len(data["purchases"]) + 1),
                       "ts": now_str(), "user": u["username"], "barcode": code, "name": name,
                       "cost_price": cost, "sell_price": sell, "qty": qty,
                       "expiry": d.get("expiry", ""), "supplier": d.get("supplier", ""),
                       "note": str(body.get("note", "")).strip()}
                data["purchases"].append(pur)
                append_audit(data, u["username"], "purchase",
                             "%s | %s × %d | شراء %.2f / بيع %.2f" % (code, name, qty, cost, sell))
                save_store(data)
            self._ok(purchase=pur, drug={k: d.get(k) for k in
                     ("barcode", "name", "sell_price", "cost_price", "qty", "expiry", "supplier")})
            return

        if path == "/api/drug/update":
            u = self.guard("drug_edit")
            if not u:
                return
            code = re.sub(r"\s+", "", str(body.get("barcode", "")))
            with STORE_LOCK:
                data = load_store()
                d = find_drug(data, code)
                if not d:
                    self._err("not_found", "الدواء غير موجود", 404)
                    return
                before = {k: d.get(k) for k in ("name", "sell_price", "cost_price", "qty", "expiry", "supplier", "min_stock")}
                for k in ("name", "expiry", "supplier"):
                    if k in body:
                        d[k] = str(body[k]).strip()
                for k in ("sell_price", "cost_price", "min_stock"):
                    if k in body and body[k] not in (None, ""):
                        d[k] = money(num(body[k], d.get(k) or 0))
                if "qty" in body:
                    newq = int(num(body["qty"], d.get("qty")))
                    if newq < 0:
                        self._err("bad_qty", "الكمية لا تكون سالبة", 400)
                        return
                    d["qty"] = newq
                d["updated"] = now_str()
                after = {k: d.get(k) for k in before}
                changes = "%s → %s" % (json.dumps(before, ensure_ascii=False),
                                       json.dumps(after, ensure_ascii=False))
                append_audit(data, u["username"], "drug_edit", code + " | " + changes)
                save_store(data)
            self._ok(drug=d)
            return

        # ---------- المستخدمون والصلاحيات (مدير فقط) ----------
        if path == "/api/users/add":
            u = self.guard("users")
            if not u:
                return
            username = str(body.get("username", "")).strip().lower()
            password = str(body.get("password", ""))
            if not re.fullmatch(r"[A-Za-z0-9_.\-]{3,30}", username):
                self._err("bad_username", "اسم المستخدم 3-30 حرفاً (إنجليزي/أرقام)", 400)
                return
            if len(password) < 8:
                self._err("short_password", "كلمة المرور 8 أحرف على الأقل", 400)
                return
            users = load_users()
            if any(x["username"].lower() == username for x in users):
                self._err("exists", "المستخدم موجود بالفعل", 400)
                return
            perms = {p: bool(body.get("perms", {}).get(p)) for p in PERMS}
            users.append({"username": username, "name": str(body.get("name", "")).strip() or username,
                          "password": hash_password(password), "role": "user", "perms": perms,
                          "active": True, "created": now_str()})
            save_users(users)
            with STORE_LOCK:
                data = load_store()
                append_audit(data, u["username"], "user_add", username + " | " + json.dumps(perms, ensure_ascii=False))
                save_store(data)
            self._ok()
            return

        if path == "/api/users/update":
            u = self.guard("users")
            if not u:
                return
            username = str(body.get("username", "")).strip().lower()
            users = load_users()
            target = next((x for x in users if x["username"].lower() == username), None)
            if not target:
                self._err("not_found", "المستخدم غير موجود", 404)
                return
            if target.get("role") == "admin" and body.get("active") is False:
                self._err("protected", "لا يمكن تعطيل المدير", 400)
                return
            if "name" in body:
                target["name"] = str(body["name"]).strip()
            if "active" in body:
                target["active"] = bool(body["active"])
            if "perms" in body and target.get("role") != "admin":
                target["perms"] = {p: bool(body["perms"].get(p)) for p in PERMS}
            if body.get("password"):
                if len(str(body["password"])) < 8:
                    self._err("short_password", "كلمة المرور 8 أحرف على الأقل", 400)
                    return
                target["password"] = hash_password(str(body["password"]))
            save_users(users)
            with STORE_LOCK:
                data = load_store()
                append_audit(data, u["username"], "user_update",
                             username + " | " + json.dumps({k: body.get(k) for k in ("name", "active", "perms")},
                                                           ensure_ascii=False))
                save_store(data)
            self._ok()
            return

        if path == "/api/users/delete":
            u = self.guard("users")
            if not u:
                return
            username = str(body.get("username", "")).strip().lower()
            users = load_users()
            target = next((x for x in users if x["username"].lower() == username), None)
            if not target or target.get("role") == "admin":
                self._err("protected", "لا يمكن حذف المدير", 400)
                return
            users = [x for x in users if x["username"].lower() != username]
            save_users(users)
            for tok, rec in list(SESSIONS.items()):
                if rec[0].lower() == username:
                    SESSIONS.pop(tok, None)
            with STORE_LOCK:
                data = load_store()
                append_audit(data, u["username"], "user_delete", username)
                save_store(data)
            self._ok()
            return

        # ---------- الإعدادات / النسخ الاحتياطي (مدير فقط) ----------
        if path == "/api/settings/update":
            u = self.guard("settings")
            if not u:
                return
            with STORE_LOCK:
                data = load_store()
                cfg = data["config"]
                for k in ("pharmacy_name", "pharmacy_sub", "currency"):
                    if k in body:
                        cfg[k] = str(body[k]).strip()[:100]
                if "vat_percent" in body:
                    v = num(body["vat_percent"], 0)
                    cfg["vat_percent"] = max(0.0, min(100.0, v))
                if "low_stock" in body:
                    cfg["low_stock"] = int(max(1, num(body["low_stock"], 15)))
                append_audit(data, u["username"], "settings", json.dumps(cfg, ensure_ascii=False))
                save_store(data)
                self._ok(config=dict(cfg))
            return

        if path == "/api/backup":
            u = self.guard("backup")
            if not u:
                return
            with STORE_LOCK:
                data = load_store()
                append_audit(data, u["username"], "backup", "نسخة احتياطية يدوية")
                save_store(data)
                name = manual_backup(data)
            self._ok(name=name)
            return

        self._send(404, b"Not found", "text/plain; charset=utf-8")


class QuietServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _port_free(port):
    import socket
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def main():
    opts = {"port": PORT_DEFAULT, "no_browser": False}
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--port", "-p") and i + 1 < len(argv):
            try:
                opts["port"] = int(argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif a.startswith("--port="):
            try:
                opts["port"] = int(a.split("=", 1)[1])
            except ValueError:
                pass
            i += 1
        elif a in ("--no-browser", "--nobrowser"):
            opts["no_browser"] = True
            i += 1
        else:
            i += 1

    os.makedirs(DATA_DIR, exist_ok=True)
    ensure_admin()

    port = opts["port"]
    for _ in range(12):
        if _port_free(port):
            break
        port += 1
    url = "http://127.0.0.1:%d/" % port
    server = QuietServer(("127.0.0.1", port), Handler)
    print("=" * 60)
    print("  BADAWI PHARMACY — صيدلية بدوي")
    print("  " + url)
    print("  الدخول: %s / %s" % (DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASS))
    print("  البيانات مشفّرة في: " + DATA_DIR)
    print("=" * 60)
    if not opts["no_browser"]:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nتم إيقاف الخادم.")
        server.server_close()


if __name__ == "__main__":
    main()
