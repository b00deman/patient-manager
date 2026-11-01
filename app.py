# -*- coding: utf-8 -*-
"""
مستشفى الخيري - نظام تسجيل بيانات المرضى
Al-Khairi Hospital - Patient Records System

Features:
  - Encrypted local storage (patients.json / users.json) -> not editable from outside
  - Automatic daily backups (keep 30) + manual backups + restore
  - Arabic / English interface
  - Dark / Light theme
  - Last used language, theme and last edit are persisted
  - Login + role based permissions (view / add / edit / delete / print)
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

PORT = 17755

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(APP_DIR, "patients.json")
USERS_FILE = os.path.join(APP_DIR, "users.json")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
BACKUP_DIR = os.path.join(APP_DIR, "backups")

SESSIONS = {}

DEFAULT_ADMIN_USER = "badawi"
DEFAULT_ADMIN_PASS = "Badawi@2026"

PERMS = ["view", "add", "edit", "delete", "print"]

DATA_STATUS = {"warning": ""}

# ------------------------------------------------------------------
#  التشفير  /  Encryption (stdlib only, encrypt-then-MAC)
# ------------------------------------------------------------------

_SECRET = "kha1ri-h0sp1tal-2026-store-key-9f3c1a7b5d2e8460b9c4f1a8e7d3b605"
_FORMAT = "PM1"
_KEYS_CACHE = {}


class TamperError(Exception):
    pass


def _keys(salt):
    """مفتاح تشفير 32 بايت + مفتاح تحقق 32 بايت مشتقين من salt"""
    cached = _KEYS_CACHE.get(salt)
    if cached:
        return cached
    dk = hashlib.pbkdf2_hmac("sha256", _SECRET.encode("utf-8"), salt, 120000, 64)
    pair = (dk[:32], dk[32:])
    _KEYS_CACHE[salt] = pair
    return pair


def _xor_stream(data, key, nonce):
    """HMAC-SHA256 في وضع العدّاد = مفتاح تيار آمن"""
    n = len(data)
    out = bytearray(n)
    pos = 0
    ctr = 0
    while pos < n:
        block = hmac.new(key, nonce + ctr.to_bytes(8, "big"), hashlib.sha256).digest()
        chunk = data[pos:pos + 32]
        for i in range(len(chunk)):
            out[pos + i] = chunk[i] ^ block[i]
        pos += 32
        ctr += 1
    return bytes(out)


def encrypt_store(obj):
    """يحوّل البيانات إلى مغلّف مشفّر — لا يمكن قراءته أو تعديله من الخارج"""
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


# ------------------------------------------------------------------
#  كلمات المرور
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


# ------------------------------------------------------------------
#  الإعدادات (اللغة / الثيم / آخر تعديل)
# ------------------------------------------------------------------

DEFAULT_SETTINGS = {"lang": "ar", "theme": "dark", "last_edit": ""}


def load_settings():
    data = _read_json(SETTINGS_FILE)
    out = dict(DEFAULT_SETTINGS)
    if isinstance(data, dict):
        for k in DEFAULT_SETTINGS:
            if k in data:
                out[k] = data[k]
    if out.get("lang") not in ("ar", "en"):
        out["lang"] = "ar"
    if out.get("theme") not in ("dark", "light"):
        out["theme"] = "dark"
    return out


def save_settings(s):
    _atomic_write(SETTINGS_FILE, json.dumps(s, ensure_ascii=False, indent=2))


def touch_last_edit():
    s = load_settings()
    s["last_edit"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_settings(s)


# ------------------------------------------------------------------
#  النسخ الاحتياطي
# ------------------------------------------------------------------

def ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _prune(prefix, keep):
    try:
        files = sorted([f for f in os.listdir(BACKUP_DIR)
                        if f.startswith(prefix) and f.endswith(".pmbak")], reverse=True)
        for f in files[keep:]:
            try:
                os.remove(os.path.join(BACKUP_DIR, f))
            except OSError:
                pass
    except OSError:
        pass


def write_backup(path, patients):
    ensure_backup_dir()
    env = encrypt_store(patients)
    _atomic_write(path, json.dumps(env, ensure_ascii=False, indent=2))


def daily_backup(patients):
    """نسخة واحدة لكل يوم — تُحدَّث مع كل حفظ، ويُحتفظ بآخر 30 يوم"""
    day = datetime.now().strftime("%Y-%m-%d")
    write_backup(os.path.join(BACKUP_DIR, "daily_%s.pmbak" % day), patients)
    _prune("daily_", 30)


def manual_backup(patients, tag="manual"):
    ensure_backup_dir()
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    name = "%s_%s.pmbak" % (tag, stamp)
    write_backup(os.path.join(BACKUP_DIR, name), patients)
    _prune(tag + "_", 20)
    return name


def list_backups():
    ensure_backup_dir()
    items = []
    for fn in os.listdir(BACKUP_DIR):
        if not fn.endswith(".pmbak"):
            continue
        p = os.path.join(BACKUP_DIR, fn)
        try:
            items.append({
                "name": fn,
                "size": os.path.getsize(p),
                "time": datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M"),
            })
        except OSError:
            pass
    items.sort(key=lambda x: x["time"], reverse=True)
    return items


def newest_backup_data():
    ensure_backup_dir()
    try:
        files = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith(".pmbak")], reverse=True)
    except OSError:
        return None
    for f in files:
        env = _read_json(os.path.join(BACKUP_DIR, f))
        if env is None:
            continue
        try:
            data = decrypt_store(env)
        except Exception:
            continue
        if isinstance(data, list):
            return data
    return None


# ------------------------------------------------------------------
#  المرضى
# ------------------------------------------------------------------

def load_patients():
    if not os.path.exists(DATA_FILE):
        # الملف اتمسح؟ نرجّعه من آخر نسخة احتياطية إن وجدت
        restored = newest_backup_data()
        if restored:
            save_patients(restored)
            DATA_STATUS["warning"] = "restored"
            return restored
        return []
    raw = _read_json(DATA_FILE)

    if isinstance(raw, list):
        # ملف قديم غير مشفّر — نشفّره فوراً
        save_patients(raw)
        return raw

    try:
        data = decrypt_store(raw)
        if not isinstance(data, list):
            raise TamperError("bad payload")
        return data
    except Exception:
        restored = newest_backup_data()
        if restored is not None:
            save_patients(restored)
            DATA_STATUS["warning"] = "restored"
            return restored
        DATA_STATUS["warning"] = "tampered"
        return []


def save_patients(patients):
    env = encrypt_store(patients)
    _atomic_write(DATA_FILE, json.dumps(env, ensure_ascii=False, indent=2))
    DATA_STATUS["warning"] = ""
    try:
        daily_backup(patients)
    except Exception:
        pass


def next_id(patients):
    if not patients:
        return 1
    return max(p["id"] for p in patients) + 1


# ------------------------------------------------------------------
#  المستخدمون
# ------------------------------------------------------------------

def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    raw = _read_json(USERS_FILE)
    if isinstance(raw, list):
        save_users(raw)
        return raw
    try:
        data = decrypt_store(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_users(users):
    _atomic_write(USERS_FILE, json.dumps(encrypt_store(users), ensure_ascii=False, indent=2))


def find_user(username):
    for u in load_users():
        if u["username"].lower() == str(username).lower():
            return u
    return None


def ensure_admin():
    if os.path.exists(USERS_FILE):
        return
    users = [{
        "username": DEFAULT_ADMIN_USER,
        "name": "بدوي",
        "password": hash_password(DEFAULT_ADMIN_PASS),
        "role": "admin",
        "perms": {p: True for p in PERMS},
        "active": True,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }]
    save_users(users)


def public_user(u):
    return {
        "username": u["username"],
        "name": u.get("name", u["username"]),
        "role": u.get("role", "user"),
        "perms": u.get("perms", {p: False for p in PERMS}),
        "active": u.get("active", True),
        "created": u.get("created", ""),
    }


HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>مستشفى الخيري</title>
<script>
try{
  var _p=JSON.parse(localStorage.getItem('pm_prefs')||'{}');
  if(_p.theme==='light'||_p.theme==='dark') document.documentElement.setAttribute('data-theme',_p.theme);
  if(_p.lang==='en'||_p.lang==='ar'){document.documentElement.lang=_p.lang;document.documentElement.dir=(_p.lang==='ar'?'rtl':'ltr');}
}catch(e){}
</script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0f1923;--surface:#162029;--surface2:#0f1923;--border:#1e2d3a;--border2:#2a3b4a;
  --text:#e0e6ed;--dim:#90a4ae;--mute:#78909c;--accent:#4fc3f7;--accent2:#29b6f6;--ink:#0f1923;
  --hover:#1a2632;--chip:#263238;--chip2:#37474f;
  --shadow:0 20px 60px rgba(0,0,0,.45);--shadow-sm:0 2px 12px rgba(0,0,0,.18);
  --danger:#ef5350;--danger2:#e53935;--warn:#ffa726;--warn2:#fb8c00;--ok:#66bb6a;--ok2:#43a047;
  --logout-bg:#3e2723;--logout-fg:#ff8a80;--logout-bg2:#4e342e;--logout-fg2:#ffab91;
}
html[data-theme="light"]{
  --bg:#eef3f8;--surface:#ffffff;--surface2:#f7fafd;--border:#dae4ee;--border2:#c3d4e3;
  --text:#12232e;--dim:#4d6679;--mute:#6d8598;--accent:#0277bd;--accent2:#01579b;--ink:#ffffff;
  --hover:#f1f7fc;--chip:#e6eef6;--chip2:#d7e5f1;
  --shadow:0 14px 44px rgba(16,42,60,.14);--shadow-sm:0 2px 10px rgba(16,42,60,.07);
  --danger:#e53935;--danger2:#c62828;--warn:#ef6c00;--warn2:#e65100;--ok:#2e7d32;--ok2:#1b5e20;
  --logout-bg:#fdecea;--logout-fg:#c62828;--logout-bg2:#fbd9d6;--logout-fg2:#b71c1c;
}
body{font-family:'Segoe UI',Tahoma,Arial,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:20px;padding-top:76px;transition:background .25s,color .25s}
.container{max-width:1000px;margin:0 auto}
header{text-align:center;padding:18px 0 16px;border-bottom:1px solid var(--border);margin-bottom:20px}
header h1{font-size:28px;color:var(--accent);font-weight:600}
header p{color:var(--mute);margin-top:8px;font-size:14px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:var(--shadow-sm)}
.card h2{font-size:18px;color:var(--accent);margin-bottom:18px;font-weight:600}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.form-group{display:flex;flex-direction:column}
.form-group.full{grid-column:1/-1}
.form-group label{font-size:13px;color:var(--dim);margin-bottom:6px}
.form-group input,.form-group select,.form-group textarea{background:var(--surface2);border:1px solid var(--border2);border-radius:8px;padding:10px 14px;color:var(--text);font-size:15px;font-family:inherit;outline:none;transition:border-color .2s}
.form-group input:focus,.form-group select:focus,.form-group textarea:focus{border-color:var(--accent)}
.form-group textarea{resize:vertical;min-height:60px}
.btn-row{display:flex;gap:12px;margin-top:18px;flex-wrap:wrap}
.btn{padding:11px 26px;border:none;border-radius:8px;font-size:15px;font-family:inherit;cursor:pointer;transition:all .2s;font-weight:600}
.btn-primary{background:var(--accent);color:var(--ink)}
.btn-primary:hover{background:var(--accent2)}
.btn-ok{background:var(--ok);color:#fff}
.btn-ok:hover{background:var(--ok2)}
.btn-secondary{background:var(--chip);color:var(--dim);border:1px solid var(--chip2)}
.btn-secondary:hover{background:var(--chip2);color:var(--text)}
.btn-sm{padding:6px 13px;font-size:13px;border-radius:6px}
.btn-del{background:var(--danger);color:#fff}
.btn-del:hover{background:var(--danger2)}
.btn-warn{background:var(--warn);color:#fff}
.btn-warn:hover{background:var(--warn2)}
.search-bar{display:flex;gap:10px;margin-bottom:16px}
.search-bar input{flex:1;background:var(--surface2);border:1px solid var(--border2);border-radius:8px;padding:10px 14px;color:var(--text);font-size:15px;outline:none;font-family:inherit}
.search-bar input:focus{border-color:var(--accent)}
.stats{font-size:13px;color:var(--mute);margin-bottom:14px}
table{width:100%;border-collapse:collapse}
th,td{padding:12px 10px;text-align:start;border-bottom:1px solid var(--border)}
th{color:var(--accent);font-size:13px;font-weight:600}
td{font-size:14px}
tbody tr:hover{background:var(--hover)}
.empty-msg{text-align:center;padding:40px;color:var(--mute);font-size:15px}
.toast{position:fixed;top:70px;left:50%;transform:translateX(-50%);background:var(--ok);color:#fff;padding:12px 24px;border-radius:8px;font-size:15px;z-index:3000;display:none;box-shadow:0 4px 20px rgba(0,0,0,.35);max-width:90vw;text-align:center}
.toast.error{background:var(--danger)}
.toast.show{display:block;animation:fadeIn .3s}
@keyframes fadeIn{from{opacity:0;transform:translate(-50%,-8px)}to{opacity:1;transform:translate(-50%,0)}}
.modal-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.6);z-index:2000;justify-content:center;align-items:center;padding:20px;overflow:auto}
.modal-overlay.show{display:flex}
.modal{background:var(--surface);border:1px solid var(--border2);border-radius:12px;padding:26px;width:100%;max-width:580px;max-height:90vh;overflow:auto;box-shadow:var(--shadow)}
.modal h2{color:var(--accent);margin-bottom:18px;font-size:19px}
.modal .form-grid{grid-template-columns:1fr 1fr}
.modal .btn-row{justify-content:flex-end}
.hint{font-size:13px;color:var(--mute);line-height:1.7;margin-bottom:14px}
#printArea{background:#fff;color:#000;padding:24px;border-radius:8px;margin-bottom:16px}
#printArea .ph-title{font-size:26px;font-weight:bold;text-align:center;margin-bottom:6px;color:#000}
#printArea .ph-sub{text-align:center;font-size:14px;color:#333;margin-bottom:20px;border-bottom:2px solid #000;padding-bottom:12px}
#printArea .ph-patient table{width:100%;border-collapse:collapse}
#printArea .ph-patient th,#printArea .ph-patient td{padding:10px 14px;text-align:start;border:1px solid #999;font-size:15px;color:#000}
#printArea .ph-patient th{background:#eee;font-weight:600;width:30%}
@media print{html,body{background:#fff!important;padding:0!important}body *{visibility:hidden}.modal-overlay{background:transparent!important;position:static!important;padding:0!important;display:block!important}.modal{border:none!important;box-shadow:none!important;max-width:100%!important;max-height:none!important;padding:0!important;background:#fff!important}.modal h2,.modal .btn-row{display:none!important}#printArea,#printArea *{visibility:visible}#printArea{position:absolute!important;left:0;top:0;width:100%;padding:20px;margin:0;border-radius:0;box-shadow:none;background:#fff!important}}

/* ---------- الشريط العلوي الثابت ---------- */
.topcontrols{position:fixed;top:0;left:0;right:0;height:56px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 18px;background:var(--surface);border-bottom:1px solid var(--border);z-index:1500;box-shadow:var(--shadow-sm)}
.brand-mini{font-size:14px;font-weight:700;color:var(--accent)}
.ctl-group{display:flex;align-items:center;gap:8px}
.seg{display:flex;background:var(--chip);border:1px solid var(--border2);border-radius:8px;overflow:hidden}
.seg-btn{background:transparent;border:none;color:var(--dim);padding:6px 13px;font-size:13px;font-family:inherit;cursor:pointer;font-weight:700}
.seg-btn.active{background:var(--accent);color:var(--ink)}
.ctl-btn{background:var(--chip);border:1px solid var(--border2);color:var(--text);width:34px;height:34px;border-radius:8px;cursor:pointer;font-size:16px;line-height:1;display:flex;align-items:center;justify-content:center}
.ctl-btn:hover{background:var(--chip2)}

/* ---------- شاشة الدخول ---------- */
#loginView{display:none;min-height:70vh;align-items:center;justify-content:center}
#loginView.show{display:flex}
.login-card{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:36px 32px;width:100%;max-width:390px;box-shadow:var(--shadow)}
.login-logo{text-align:center;font-size:26px;font-weight:700;color:var(--accent);margin-bottom:6px}
.login-sub{text-align:center;color:var(--mute);font-size:13px;margin-bottom:26px}
.login-field{margin-bottom:16px}
.login-field label{display:block;font-size:13px;color:var(--dim);margin-bottom:6px}
.login-field input{width:100%;background:var(--surface2);border:1px solid var(--border2);border-radius:8px;padding:12px 14px;color:var(--text);font-size:15px;font-family:inherit;outline:none}
.login-field input:focus{border-color:var(--accent)}
.login-btn{width:100%;background:var(--accent);color:var(--ink);border:none;border-radius:8px;padding:13px;font-size:16px;font-weight:700;font-family:inherit;cursor:pointer;margin-top:8px}
.login-btn:hover{background:var(--accent2)}
.login-btn:disabled{opacity:.6;cursor:wait}
.login-error{color:var(--danger);font-size:13px;text-align:center;min-height:18px;margin-top:12px}
.login-hint{color:var(--mute);font-size:12px;text-align:center;margin-top:18px;line-height:1.7}

/* ---------- شريط المستخدم ---------- */
.topbar{display:flex;justify-content:space-between;align-items:center;gap:12px;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:10px 16px;margin-bottom:18px;flex-wrap:wrap;box-shadow:var(--shadow-sm)}
.topbar-user{display:flex;align-items:center;gap:8px;font-size:14px;color:var(--dim);flex-wrap:wrap}
.role-badge{font-size:11px;padding:3px 9px;border-radius:20px;font-weight:700}
.role-admin{background:var(--accent);color:var(--ink)}
.role-user{background:var(--chip2);color:var(--text)}
.topbar-actions{display:flex;gap:8px;flex-wrap:wrap}
.btn-mini{background:var(--chip);color:var(--dim);border:1px solid var(--chip2);border-radius:7px;padding:7px 14px;font-size:13px;font-family:inherit;cursor:pointer;font-weight:600}
.btn-mini:hover{background:var(--chip2);color:var(--text)}
.btn-logout{background:var(--logout-bg);color:var(--logout-fg);border-color:var(--logout-bg)}
.btn-logout:hover{background:var(--logout-bg2);color:var(--logout-fg2)}
.last-edit{font-size:12px;color:var(--mute)}
#appView{display:none}
#appView.show{display:block}

/* ---------- إدارة المستخدمين ---------- */
.user-row{border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:12px;background:var(--surface2)}
.user-row-head{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.user-name{font-weight:700;color:var(--text);font-size:15px}
.user-meta{font-size:12px;color:var(--mute);margin-top:3px}
.perm-list{display:flex;flex-wrap:wrap;gap:14px}
.perm-item{display:flex;align-items:center;gap:6px;font-size:13px;color:var(--dim);cursor:pointer;user-select:none}
.perm-item input{width:16px;height:16px;accent-color:var(--accent);cursor:pointer}
.perm-item input:disabled{opacity:.45;cursor:not-allowed}
.section-title{font-size:14px;color:var(--accent);font-weight:700;margin:22px 0 12px;padding-top:18px;border-top:1px solid var(--border)}
.bk-row{display:flex;justify-content:space-between;align-items:center;gap:10px;border:1px solid var(--border);background:var(--surface2);border-radius:8px;padding:10px 12px;margin-bottom:8px;flex-wrap:wrap}
.bk-name{font-size:13px;color:var(--text);font-weight:600}
.bk-meta{font-size:11px;color:var(--mute);margin-top:2px}
</style>
</head>
<body>

<!-- ============ شريط اللغة والثيم ============ -->
<div class="topcontrols">
  <div class="brand-mini" id="brandMini" data-i18n="brand">مستشفى الخيري</div>
  <div class="ctl-group">
    <div class="seg">
      <button class="seg-btn active" id="langAr" onclick="setLang('ar')">عربي</button>
      <button class="seg-btn" id="langEn" onclick="setLang('en')">EN</button>
    </div>
    <button class="ctl-btn" id="themeBtn" onclick="toggleTheme()" data-i18n-title="theme_tip">🌙</button>
  </div>
</div>

<!-- ================= شاشة تسجيل الدخول ================= -->
<div id="loginView">
  <div class="login-card">
    <div class="login-logo" data-i18n="brand">مستشفى الخيري</div>
    <p class="login-sub" data-i18n="brand_sub">نظام تسجيل بيانات المرضى</p>
    <div class="login-field">
      <label data-i18n="username">اسم المستخدم</label>
      <input type="text" id="loginUser" autocomplete="username" data-i18n-ph="ph_username">
    </div>
    <div class="login-field">
      <label data-i18n="password">كلمة المرور</label>
      <input type="password" id="loginPass" autocomplete="current-password" data-i18n-ph="ph_password">
    </div>
    <button class="login-btn" id="loginBtn" onclick="doLogin()" data-i18n="login">دخول</button>
    <div class="login-error" id="loginError"></div>
    <div class="login-hint" data-i18n="hint_login">الدخول متاح للمستخدمين المصرح لهم فقط</div>
  </div>
</div>

<!-- ================= التطبيق ================= -->
<div id="appView">
<div class="container">

  <div class="topbar">
    <div class="topbar-user">
      <span>👤</span>
      <span id="topUserName">-</span>
      <span id="topUserRole" class="role-badge role-user">-</span>
      <span class="last-edit" id="lastEdit"></span>
    </div>
    <div class="topbar-actions">
      <button class="btn-mini" id="btnUsers" onclick="openUsers()" style="display:none" data-i18n="btn_users">إدارة المستخدمين</button>
      <button class="btn-mini" id="btnBackup" onclick="openBackup()" style="display:none" data-i18n="btn_backup">النسخ الاحتياطي</button>
      <button class="btn-mini" id="btnPass" onclick="openPass()" style="display:none" data-i18n="btn_pass">كلمة المرور</button>
      <button class="btn-mini btn-logout" onclick="doLogout()" data-i18n="btn_logout">تسجيل الخروج</button>
    </div>
  </div>

  <header><h1 data-i18n="brand">مستشفى الخيري</h1><p data-i18n="header_sub">أدخل بيانات المريض وسيتم حفظها تلقائياً — يمكنك البحث والرجوع لها في أي وقت</p></header>

  <div class="card" id="addCard"><h2 data-i18n="card_add">تسجيل مريض جديد</h2>
    <div class="form-grid">
      <div class="form-group"><label data-i18n="lbl_name">الاسم *</label><input type="text" id="name" data-i18n-ph="ph_name"></div>
      <div class="form-group"><label data-i18n="lbl_age">العمر</label><input type="number" id="age" min="0" max="150" data-i18n-ph="ph_age"></div>
      <div class="form-group"><label data-i18n="lbl_gender">الجنس</label>
        <select id="gender">
          <option value="" data-i18n="choose"></option>
          <option value="ذكر" data-i18n="male"></option>
          <option value="أنثى" data-i18n="female"></option>
        </select>
      </div>
      <div class="form-group full"><label data-i18n="lbl_complaint">الشكوى</label><textarea id="complaint" data-i18n-ph="ph_complaint"></textarea></div>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" onclick="addPatient()" data-i18n="btn_register">تسجيل</button>
      <button class="btn btn-ok" onclick="printForm()" data-i18n="btn_print">طباعة</button>
      <button class="btn btn-secondary" onclick="clearForm()" data-i18n="btn_clear">مسح الحقول</button>
    </div>
  </div>

  <div class="card"><h2 data-i18n="card_list">المرضى المسجلين</h2>
    <div class="search-bar">
      <input type="text" id="searchInput" data-i18n-ph="ph_search" oninput="searchPatients()">
      <button class="btn btn-secondary" id="btnExport" onclick="exportCsv()" style="display:none;white-space:nowrap" data-i18n="btn_export">تصدير CSV</button>
    </div>
    <div class="stats" id="stats"></div>
    <table><thead><tr>
      <th>#</th><th data-i18n="th_name">الاسم</th><th data-i18n="th_age">العمر</th>
      <th data-i18n="th_gender">الجنس</th><th data-i18n="th_complaint">الشكوى</th>
      <th data-i18n="th_date">التاريخ</th><th data-i18n="th_actions">إجراءات</th>
    </tr></thead><tbody id="patientTable"></tbody></table>
    <div class="empty-msg" id="emptyMsg" style="display:none" data-i18n="empty_none"></div>
  </div>

</div>
</div>

<!-- نافذة تعديل المريض -->
<div class="modal-overlay" id="editModal"><div class="modal"><h2 data-i18n="edit_title">تعديل بيانات المريض</h2>
  <div class="form-grid">
    <div class="form-group"><label data-i18n="lbl_name">الاسم</label><input type="text" id="editName"></div>
    <div class="form-group"><label data-i18n="lbl_age">العمر</label><input type="number" id="editAge" min="0" max="150"></div>
    <div class="form-group full"><label data-i18n="lbl_gender">الجنس</label>
      <select id="editGender">
        <option value="" data-i18n="choose"></option>
        <option value="ذكر" data-i18n="male"></option>
        <option value="أنثى" data-i18n="female"></option>
      </select>
    </div>
    <div class="form-group full"><label data-i18n="lbl_complaint">الشكوى</label><textarea id="editComplaint"></textarea></div>
  </div>
  <div class="btn-row"><button class="btn btn-primary" onclick="saveEdit()" data-i18n="save_edit">حفظ التعديل</button><button class="btn btn-secondary" onclick="closeModal()" data-i18n="cancel">إلغاء</button></div>
</div></div>

<!-- معاينة الطباعة -->
<div class="modal-overlay" id="printModal"><div class="modal" style="max-width:620px">
  <h2 data-i18n="print_preview">معاينة الطباعة</h2>
  <div id="printArea"></div>
  <div class="btn-row" style="justify-content:center">
    <button class="btn btn-primary" onclick="doPrint()" data-i18n="print_now">طباعة الآن</button>
    <button class="btn btn-secondary" onclick="closePrint()" data-i18n="close">إغلاق</button>
  </div>
</div></div>

<!-- إدارة المستخدمين -->
<div class="modal-overlay" id="usersModal"><div class="modal" style="max-width:660px"><h2 data-i18n="users_title">إدارة المستخدمين</h2>
  <div id="usersList"></div>

  <div class="section-title" data-i18n="add_user_title">إضافة مستخدم جديد</div>
  <div class="form-grid">
    <div class="form-group"><label data-i18n="username">اسم المستخدم</label><input type="text" id="newUsername" autocomplete="off" data-i18n-ph="ph_username_new"></div>
    <div class="form-group"><label data-i18n="lbl_display">الاسم الظاهر</label><input type="text" id="newDisplayName" autocomplete="off" data-i18n-ph="ph_display"></div>
    <div class="form-group full"><label data-i18n="password">كلمة المرور</label><input type="password" id="newPassword" autocomplete="new-password" data-i18n-ph="ph_password_new"></div>
  </div>
  <div style="margin-top:14px">
    <label style="font-size:13px;color:var(--dim);display:block;margin-bottom:8px" data-i18n="perms">الصلاحيات</label>
    <div class="perm-list" id="newPerms">
      <label class="perm-item"><input type="checkbox" data-perm="view" checked> <span data-i18n="p_view">عرض</span></label>
      <label class="perm-item"><input type="checkbox" data-perm="add"> <span data-i18n="p_add">تسجيل</span></label>
      <label class="perm-item"><input type="checkbox" data-perm="edit"> <span data-i18n="p_edit">تعديل</span></label>
      <label class="perm-item"><input type="checkbox" data-perm="delete"> <span data-i18n="p_delete">حذف</span></label>
      <label class="perm-item"><input type="checkbox" data-perm="print"> <span data-i18n="p_print">طباعة</span></label>
    </div>
  </div>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="addUser()" data-i18n="btn_add_user">إضافة المستخدم</button>
    <button class="btn btn-secondary" onclick="closeUsers()" data-i18n="close">إغلاق</button>
  </div>
</div></div>

<!-- النسخ الاحتياطي -->
<div class="modal-overlay" id="backupModal"><div class="modal" style="max-width:620px">
  <h2 data-i18n="backup_title">النسخ الاحتياطي</h2>
  <p class="hint" data-i18n="backup_hint"></p>
  <div class="btn-row" style="justify-content:flex-start;margin-top:0">
    <button class="btn btn-primary btn-sm" onclick="createBackup()" data-i18n="backup_create">إنشاء نسخة الآن</button>
  </div>
  <div id="backupList" style="margin-top:16px"></div>
  <div class="btn-row"><button class="btn btn-secondary" onclick="closeBackup()" data-i18n="close">إغلاق</button></div>
</div></div>

<!-- تغيير كلمة المرور -->
<div class="modal-overlay" id="passModal"><div class="modal" style="max-width:430px">
  <h2 data-i18n="pass_title">تغيير كلمة المرور</h2>
  <div class="form-group" style="margin-bottom:12px"><label data-i18n="pass_current">كلمة المرور الحالية</label><input type="password" id="passCur" autocomplete="current-password"></div>
  <div class="form-group" style="margin-bottom:12px"><label data-i18n="pass_new">كلمة المرور الجديدة</label><input type="password" id="passNew" autocomplete="new-password"></div>
  <div class="form-group"><label data-i18n="pass_confirm">تأكيد كلمة المرور</label><input type="password" id="passConf" autocomplete="new-password"></div>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="savePassword()" data-i18n="save">حفظ</button>
    <button class="btn btn-secondary" onclick="closePass()" data-i18n="cancel">إلغاء</button>
  </div>
</div></div>

<div class="toast" id="toast"></div>

<script>
/* ==================== الترجمة / i18n ==================== */
const I18N={
ar:{
 brand:"مستشفى الخيري",brand_sub:"نظام تسجيل بيانات المرضى",
 username:"اسم المستخدم",password:"كلمة المرور",
 ph_username:"اسم المستخدم",ph_password:"كلمة المرور",
 login:"دخول",logging_in:"جارٍ الدخول...",hint_login:"الدخول متاح للمستخدمين المصرح لهم فقط",
 role_admin:"مدير",role_user:"مستخدم",
 btn_users:"إدارة المستخدمين",btn_backup:"النسخ الاحتياطي",btn_pass:"كلمة المرور",btn_logout:"تسجيل الخروج",
 btn_export:"تصدير CSV",header_sub:"أدخل بيانات المريض وسيتم حفظها تلقائياً — يمكنك البحث والرجوع لها في أي وقت",
 card_add:"تسجيل مريض جديد",lbl_name:"الاسم *",ph_name:"اسم المريض",lbl_age:"العمر",ph_age:"العمر بالسنوات",
 lbl_gender:"الجنس",choose:"-- اختر --",male:"ذكر",female:"أنثى",
 lbl_complaint:"الشكوى",ph_complaint:"اكتب الشكوى / الأعراض",
 btn_register:"تسجيل",btn_print:"طباعة",btn_clear:"مسح الحقول",
 card_list:"المرضى المسجلين",ph_search:"ابحث بالاسم أو العمر أو الجنس أو الشكوى...",
 stats:"عدد المرضى: {n}",th_name:"الاسم",th_age:"العمر",th_gender:"الجنس",th_complaint:"الشكوى",th_date:"التاريخ",th_actions:"إجراءات",
 empty_none:"لا توجد بيانات مسجلة بعد",view_only:"عرض فقط",edit:"تعديل",del:"حذف",print:"طباعة",
 edit_title:"تعديل بيانات المريض",save_edit:"حفظ التعديل",cancel:"إلغاء",save:"حفظ",close:"إغلاق",
 print_preview:"معاينة الطباعة",print_now:"طباعة الآن",paper_sub:"بيانات المريض",
 users_title:"إدارة المستخدمين",add_user_title:"إضافة مستخدم جديد",lbl_display:"الاسم الظاهر",
 ph_username_new:"مثال: ahmed",ph_display:"مثال: أحمد",ph_password_new:"6 أحرف على الأقل",
 perms:"الصلاحيات",p_view:"عرض",p_add:"تسجيل",p_edit:"تعديل",p_delete:"حذف",p_print:"طباعة",
 btn_add_user:"إضافة المستخدم",you:"(أنت)",created:"أُنشئ",no_users:"لا يوجد مستخدمون",
 backup_title:"النسخ الاحتياطي",
 backup_hint:"يتم إنشاء نسخة احتياطية تلقائياً كل يوم مع كل حفظ، ويُحتفظ بآخر 30 نسخة. النسخ مشفّرة في مجلد backups.",
 backup_create:"إنشاء نسخة الآن",backup_none:"لا توجد نسخ احتياطية بعد",restore:"استعادة",size:"الحجم",
 pass_title:"تغيير كلمة المرور",pass_current:"كلمة المرور الحالية",pass_new:"كلمة المرور الجديدة",pass_confirm:"تأكيد كلمة المرور",
 last_edit:"آخر تعديل: ",theme_tip:"تبديل الوضع الليلي/النهاري",
 toast_saved:"تم حفظ بيانات المريض",toast_deleted:"تم حذف بيانات المريض",toast_updated:"تم تحديث البيانات",
 toast_perm:"تم تحديث صلاحيات {u}",toast_user_added:"تمت إضافة المستخدم {u}",toast_user_deleted:"تم حذف المستخدم",
 toast_backup:"تم إنشاء نسخة احتياطية",toast_restored:"تمت استعادة النسخة الاحتياطية",
 toast_pass:"تم تغيير كلمة المرور",toast_lang:"تم حفظ اللغة",toast_theme:"تم حفظ المظهر",
 confirm_del_patient:"هل أنت متأكد من حذف بيانات هذا المريض؟",
 confirm_del_user:"حذف المستخدم \"{u}\" نهائياً؟",
 confirm_restore:"استعادة هذه النسخة؟ سيتم استبدال البيانات الحالية.",
 warn_restored:"ملف البيانات كان معدّلاً من الخارج — تم استرجاع آخر نسخة احتياطية.",
 warn_tampered:"ملف البيانات تالف أو معدّل من الخارج. استخدم النسخ الاحتياطي للاستعادة.",
 e_generic:"حدث خطأ",e_login_required:"يجب تسجيل الدخول",e_admin_only:"هذه العملية للمدير فقط",
 e_perm_denied:"لا تملك صلاحية لهذه العملية",e_name_required:"الاسم مطلوب",
 e_not_found:"غير موجود",e_bad_credentials:"اسم المستخدم أو كلمة المرور غير صحيحة",
 e_inactive:"هذا الحساب موقوف — راجع المدير",e_user_exists:"اسم المستخدم موجود بالفعل",
 e_password_short:"كلمة المرور 6 أحرف على الأقل",e_username_required:"اسم المستخدم مطلوب",
 e_admin_locked:"لا يمكن تعديل أو حذف حساب المدير",e_need_name:"اكتب الاسم أولاً للطباعة",
 e_bad_pass:"كلمة المرور الحالية غير صحيحة",e_pass_mismatch:"كلمتا المرور غير متطابقتين",
 e_conn:"تعذّر الاتصال بالبرنامج"
},
en:{
 brand:"Al-Khairi Hospital",brand_sub:"Patient Records System",
 username:"Username",password:"Password",
 ph_username:"Username",ph_password:"Password",
 login:"Sign in",logging_in:"Signing in...",hint_login:"Access is limited to authorized users only",
 role_admin:"Admin",role_user:"User",
 btn_users:"Users",btn_backup:"Backups",btn_pass:"Password",btn_logout:"Sign out",
 btn_export:"Export CSV",header_sub:"Enter patient details — they are saved automatically and can be searched any time",
 card_add:"New patient",lbl_name:"Name *",ph_name:"Patient name",lbl_age:"Age",ph_age:"Age in years",
 lbl_gender:"Gender",choose:"-- Select --",male:"Male",female:"Female",
 lbl_complaint:"Complaint",ph_complaint:"Write the complaint / symptoms",
 btn_register:"Save",btn_print:"Print",btn_clear:"Clear fields",
 card_list:"Registered patients",ph_search:"Search by name, age, gender or complaint...",
 stats:"Patients: {n}",th_name:"Name",th_age:"Age",th_gender:"Gender",th_complaint:"Complaint",th_date:"Date",th_actions:"Actions",
 empty_none:"No records yet",view_only:"View only",edit:"Edit",del:"Delete",print:"Print",
 edit_title:"Edit patient",save_edit:"Save changes",cancel:"Cancel",save:"Save",close:"Close",
 print_preview:"Print preview",print_now:"Print now",paper_sub:"Patient details",
 users_title:"User management",add_user_title:"Add new user",lbl_display:"Display name",
 ph_username_new:"e.g. ahmed",ph_display:"e.g. Ahmed",ph_password_new:"At least 6 characters",
 perms:"Permissions",p_view:"View",p_add:"Add",p_edit:"Edit",p_delete:"Delete",p_print:"Print",
 btn_add_user:"Add user",you:"(you)",created:"created",no_users:"No users",
 backup_title:"Backups",
 backup_hint:"A backup is created automatically every day on each save, and the last 30 are kept. Backups are encrypted in the backups folder.",
 backup_create:"Create backup now",backup_none:"No backups yet",restore:"Restore",size:"Size",
 pass_title:"Change password",pass_current:"Current password",pass_new:"New password",pass_confirm:"Confirm password",
 last_edit:"Last edit: ",theme_tip:"Toggle dark / light mode",
 toast_saved:"Patient saved",toast_deleted:"Patient deleted",toast_updated:"Record updated",
 toast_perm:"Permissions updated for {u}",toast_user_added:"User {u} added",toast_user_deleted:"User deleted",
 toast_backup:"Backup created",toast_restored:"Backup restored",
 toast_pass:"Password changed",toast_lang:"Language saved",toast_theme:"Theme saved",
 confirm_del_patient:"Delete this patient record?",
 confirm_del_user:"Delete user \"{u}\" permanently?",
 confirm_restore:"Restore this backup? Current data will be replaced.",
 warn_restored:"The data file was modified outside the app — the latest backup was restored.",
 warn_tampered:"The data file is corrupted or was modified outside the app. Use a backup to restore.",
 e_generic:"Something went wrong",e_login_required:"Please sign in",e_admin_only:"Admins only",
 e_perm_denied:"You do not have permission for this action",e_name_required:"Name is required",
 e_not_found:"Not found",e_bad_credentials:"Wrong username or password",
 e_inactive:"This account is disabled — contact the admin",e_user_exists:"Username already exists",
 e_password_short:"Password must be at least 6 characters",e_username_required:"Username is required",
 e_admin_locked:"The admin account cannot be edited or deleted",e_need_name:"Enter a name first to print",
 e_bad_pass:"Current password is incorrect",e_pass_mismatch:"Passwords do not match",
 e_conn:"Cannot reach the application"
}};

let LANG='ar',THEME='dark';
let ME=null,allPatients=[],viewPatients=[],editingId=null,USERS=[],BACKUPS=[];
const PERMS=["view","add","edit","delete","print"];
const PERM_KEY={view:"p_view",add:"p_add",edit:"p_edit",delete:"p_delete",print:"p_print"};

function t(k){const d=I18N[LANG]||I18N.ar;if(d[k]!==undefined)return d[k];return I18N.ar[k]!==undefined?I18N.ar[k]:k;}
function tf(k,rep){let s=t(k);Object.keys(rep||{}).forEach(function(x){s=s.split('{'+x+'}').join(rep[x]);});return s;}
function errMsg(j){if(j&&j.code&&I18N[LANG]&&I18N[LANG]['e_'+j.code]!==undefined)return t('e_'+j.code);return (j&&j.message)||t('e_generic');}
function genderLabel(v){
  if(!v)return '';
  const s=String(v).toLowerCase();
  if(v==='ذكر'||s==='male')return t('male');
  if(v==='أنثى'||s==='female')return t('female');
  return v;
}

/* ==================== المظهر واللغة ==================== */
function applyTheme(){
  document.documentElement.setAttribute('data-theme',THEME);
  const b=document.getElementById('themeBtn');
  if(b) b.textContent=(THEME==='dark')?'☀️':'🌙';
}
function applyI18n(){
  document.documentElement.lang=LANG;
  document.documentElement.dir=(LANG==='ar')?'rtl':'ltr';
  document.title=t('brand');
  document.querySelectorAll('[data-i18n]').forEach(function(el){el.textContent=t(el.getAttribute('data-i18n'));});
  document.querySelectorAll('[data-i18n-ph]').forEach(function(el){el.setAttribute('placeholder',t(el.getAttribute('data-i18n-ph')));});
  document.querySelectorAll('[data-i18n-title]').forEach(function(el){el.setAttribute('title',t(el.getAttribute('data-i18n-title')));});
  document.getElementById('langAr').classList.toggle('active',LANG==='ar');
  document.getElementById('langEn').classList.toggle('active',LANG==='en');
  if(ME) applyPermissions();
  renderTable(viewPatients);
  if(USERS.length) renderUsers();
  if(BACKUPS.length) renderBackups();
  if(LAST_EDIT) renderLastEdit();
}
function savePrefs(){
  try{localStorage.setItem('pm_prefs',JSON.stringify({lang:LANG,theme:THEME}));}catch(e){}
  fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lang:LANG,theme:THEME})}).catch(function(){});
}
function setLang(l){
  if(l===LANG)return;
  LANG=l;applyI18n();savePrefs();
}
function toggleTheme(){
  THEME=(THEME==='dark')?'light':'dark';applyTheme();savePrefs();
}

/* ==================== أدوات ==================== */
function esc(s){if(s===null||s===undefined)return'';return String(s).replace(/[&<>"']/g,function(m){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m];});}
function showToast(m,e){const t2=document.getElementById('toast');t2.textContent=m;t2.className='toast show'+(e?' error':'');setTimeout(function(){t2.className='toast';},3400);}
async function api(url,opts){
  opts=opts||{};
  const r=await fetch(url,opts);
  if(r.status===401){showLogin();throw new Error('unauth');}
  let j={};
  try{j=await r.json();}catch(e){j={status:'error',code:'generic'};}
  j._code=r.status;
  return j;
}

/* ==================== الدخول ==================== */
function showLogin(){
  ME=null;
  document.getElementById('appView').classList.remove('show');
  document.getElementById('loginView').classList.add('show');
  document.getElementById('loginPass').value='';
}
function showApp(){
  document.getElementById('loginView').classList.remove('show');
  document.getElementById('appView').classList.add('show');
}
async function doLogin(){
  const u=document.getElementById('loginUser').value.trim();
  const p=document.getElementById('loginPass').value;
  const err=document.getElementById('loginError');
  const btn=document.getElementById('loginBtn');
  err.textContent='';
  if(!u||!p){err.textContent=t('e_login_required');return;}
  btn.disabled=true;btn.textContent=t('logging_in');
  try{
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
    const j=await r.json();
    if(j.status==='ok'){
      ME=j.user;
      applyPermissions();
      showApp();
      await loadPatients();
    }else{
      err.textContent=errMsg(j);
    }
  }catch(e){
    err.textContent=t('e_conn');
  }finally{
    btn.disabled=false;btn.textContent=t('login');
  }
}
async function doLogout(){
  try{await fetch('/api/logout',{method:'POST'});}catch(e){}
  allPatients=[];viewPatients=[];
  showLogin();
}

/* ==================== الصلاحيات ==================== */
function can(p){return !!(ME&&ME.perms&&ME.perms[p]);}
function isAdmin(){return !!(ME&&ME.role==='admin');}
function applyPermissions(){
  if(!ME)return;
  document.getElementById('topUserName').textContent=ME.name||ME.username;
  const badge=document.getElementById('topUserRole');
  if(isAdmin()){badge.textContent=t('role_admin');badge.className='role-badge role-admin';}
  else{badge.textContent=t('role_user');badge.className='role-badge role-user';}
  document.getElementById('btnUsers').style.display=isAdmin()?'inline-block':'none';
  document.getElementById('btnBackup').style.display=isAdmin()?'inline-block':'none';
  document.getElementById('btnPass').style.display='inline-block';
  document.getElementById('btnExport').style.display=isAdmin()?'inline-block':'none';
  document.getElementById('addCard').style.display=can('add')?'block':'none';
}

/* ==================== آخر تعديل ==================== */
let LAST_EDIT='';
function renderLastEdit(){
  const el=document.getElementById('lastEdit');
  el.innerHTML=LAST_EDIT?(esc(t('last_edit'))+'<span dir="ltr" style="display:inline-block">'+esc(LAST_EDIT)+'</span>'):'';
}
async function loadSettings(){
  try{
    const r=await fetch('/api/settings');
    const j=await r.json();
    if(j&&j.settings){
      if(j.settings.lang==='ar'||j.settings.lang==='en')LANG=j.settings.lang;
      if(j.settings.theme==='dark'||j.settings.theme==='light')THEME=j.settings.theme;
      LAST_EDIT=j.settings.last_edit||'';
    }
  }catch(e){}
  applyTheme();applyI18n();
}

/* ==================== المرضى ==================== */
async function loadPatients(){
  try{
    const j=await api('/api/patients');
    allPatients=j.data||[];
    viewPatients=allPatients;
    renderTable(viewPatients);
    if(j.last_edit){LAST_EDIT=j.last_edit;renderLastEdit();}
    if(j.warning==='restored')showToast(t('warn_restored'),true);
    else if(j.warning==='tampered')showToast(t('warn_tampered'),true);
  }catch(e){}
}
async function addPatient(){
  const n=document.getElementById('name').value.trim();
  const a=document.getElementById('age').value.trim();
  const g=document.getElementById('gender').value;
  const c=document.getElementById('complaint').value.trim();
  if(!n){showToast(t('e_name_required'),true);return;}
  try{
    const j=await api('/api/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n,age:a,gender:g,complaint:c})});
    if(j.status==='ok'){
      showToast(t('toast_saved'));clearForm();
      if(j.last_edit){LAST_EDIT=j.last_edit;renderLastEdit();}
      loadPatients();
    }else showToast(errMsg(j),true);
  }catch(e){}
}
async function searchPatients(){
  const q=document.getElementById('searchInput').value.trim();
  if(!q){viewPatients=allPatients;renderTable(viewPatients);return;}
  try{
    const j=await api('/api/search?q='+encodeURIComponent(q));
    viewPatients=j.data||[];
    renderTable(viewPatients);
  }catch(e){}
}
function renderTable(p){
  const tb=document.getElementById('patientTable');
  const st=document.getElementById('stats');
  const em=document.getElementById('emptyMsg');
  if(!p||!p.length){
    tb.innerHTML='';st.textContent=tf('stats',{n:0});em.style.display='block';return;
  }
  em.style.display='none';
  st.textContent=tf('stats',{n:p.length});
  tb.innerHTML=p.map(function(x){
    let acts='';
    if(can('edit'))acts+='<button class="btn btn-sm btn-warn" onclick="openEdit('+x.id+')">'+esc(t('edit'))+'</button> ';
    if(can('delete'))acts+='<button class="btn btn-sm btn-del" onclick="del('+x.id+')">'+esc(t('del'))+'</button> ';
    if(can('print'))acts+='<button class="btn btn-sm btn-ok" onclick="printPatient('+x.id+')">'+esc(t('print'))+'</button>';
    if(!acts)acts='<span style="color:var(--mute);font-size:12px">'+esc(t('view_only'))+'</span>';
    return '<tr><td>'+x.id+'</td><td>'+esc(x.name)+'</td><td>'+esc(x.age)+'</td><td>'+esc(genderLabel(x.gender))+'</td><td>'+esc(x.complaint)+'</td><td style="font-size:12px;color:var(--mute)" dir="ltr">'+esc(x.date)+'</td><td>'+acts+'</td></tr>';
  }).join('');
}
async function del(id){
  if(!confirm(t('confirm_del_patient')))return;
  try{
    const j=await api('/api/delete/'+id,{method:'POST'});
    if(j.status==='ok'){showToast(t('toast_deleted'));if(j.last_edit){LAST_EDIT=j.last_edit;renderLastEdit();}loadPatients();}
    else showToast(errMsg(j),true);
  }catch(e){}
}
function openEdit(id){
  const p=allPatients.find(function(x){return x.id===id;});
  if(!p)return;
  editingId=id;
  document.getElementById('editName').value=p.name;
  document.getElementById('editAge').value=p.age;
  document.getElementById('editGender').value=p.gender;
  document.getElementById('editComplaint').value=p.complaint;
  document.getElementById('editModal').classList.add('show');
}
async function saveEdit(){
  if(editingId===null)return;
  const n=document.getElementById('editName').value.trim();
  if(!n){showToast(t('e_name_required'),true);return;}
  try{
    const j=await api('/api/update/'+editingId,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      name:n,
      age:document.getElementById('editAge').value.trim(),
      gender:document.getElementById('editGender').value,
      complaint:document.getElementById('editComplaint').value.trim()
    })});
    if(j.status==='ok'){showToast(t('toast_updated'));closeModal();if(j.last_edit){LAST_EDIT=j.last_edit;renderLastEdit();}loadPatients();}
    else showToast(errMsg(j),true);
  }catch(e){}
}
function closeModal(){document.getElementById('editModal').classList.remove('show');editingId=null;}
function clearForm(){
  document.getElementById('name').value='';
  document.getElementById('age').value='';
  document.getElementById('gender').value='';
  document.getElementById('complaint').value='';
}

/* ==================== الطباعة ==================== */
function buildPrintCard(p){
  const pa=document.getElementById('printArea');
  pa.setAttribute('dir',LANG==='ar'?'rtl':'ltr');
  pa.innerHTML=
    '<div class="ph-title">'+esc(t('brand'))+'</div><div class="ph-sub">'+esc(t('paper_sub'))+'</div>'+
    '<div class="ph-patient"><table>'+
    '<tr><th>'+esc(t('lbl_name').replace(' *',''))+'</th><td>'+esc(p.name)+'</td></tr>'+
    '<tr><th>'+esc(t('lbl_age'))+'</th><td>'+esc(p.age)+'</td></tr>'+
    '<tr><th>'+esc(t('lbl_gender'))+'</th><td>'+esc(genderLabel(p.gender))+'</td></tr>'+
    '<tr><th>'+esc(t('lbl_complaint'))+'</th><td>'+esc(p.complaint)+'</td></tr>'+
    '<tr><th>'+esc(t('th_date'))+'</th><td dir="ltr">'+esc(p.date)+'</td></tr>'+
    '</table></div>';
}
function printPatient(id){
  const p=allPatients.find(function(x){return x.id===id;});
  if(!p)return;
  buildPrintCard(p);
  document.getElementById('printModal').classList.add('show');
}
function printForm(){
  const n=document.getElementById('name').value.trim();
  if(!n){showToast(t('e_need_name'),true);return;}
  const now=new Date();
  const d=now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0')+'-'+String(now.getDate()).padStart(2,'0')+' '+String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0');
  buildPrintCard({
    name:n,
    age:document.getElementById('age').value.trim(),
    gender:document.getElementById('gender').value,
    complaint:document.getElementById('complaint').value.trim(),
    date:d
  });
  document.getElementById('printModal').classList.add('show');
}
function doPrint(){window.print();}
function closePrint(){document.getElementById('printModal').classList.remove('show');}

/* ==================== إدارة المستخدمين ==================== */
function openUsers(){
  if(!isAdmin())return;
  document.getElementById('usersModal').classList.add('show');
  loadUsers();
}
function closeUsers(){document.getElementById('usersModal').classList.remove('show');}
async function loadUsers(){
  try{
    const j=await api('/api/users');
    USERS=j.data||[];
    renderUsers();
  }catch(e){}
}
function renderUsers(){
  const box=document.getElementById('usersList');
  if(!USERS.length){box.innerHTML='<div class="empty-msg">'+esc(t('no_users'))+'</div>';return;}
  box.innerHTML=USERS.map(function(u){
    const perms=PERMS.map(function(p){
      const checked=(u.perms&&u.perms[p])?'checked':'';
      const dis=(u.role==='admin')?'disabled':'';
      return '<label class="perm-item"><input type="checkbox" data-u="'+esc(u.username)+'" data-p="'+p+'" '+checked+' '+dis+' onchange="togglePerm(this)"> '+esc(t(PERM_KEY[p]))+'</label>';
    }).join('');
    const isSelf=(u.username===ME.username);
    const badge=(u.role==='admin')?'<span class="role-badge role-admin" style="margin-inline-start:6px">'+esc(t('role_admin'))+'</span>':'';
    const delBtn=isSelf?'<span class="user-meta">'+esc(t('you'))+'</span>':'<button class="btn btn-sm btn-del" onclick="deleteUser(&quot;'+esc(u.username)+'&quot;)">'+esc(t('del'))+'</button>';
    return '<div class="user-row">'+
      '<div class="user-row-head">'+
        '<div><div class="user-name">'+esc(u.name)+badge+'</div>'+
        '<div class="user-meta">@'+esc(u.username)+' · '+esc(t('created'))+' '+esc(u.created||'-')+'</div></div>'+
        '<div>'+delBtn+'</div>'+
      '</div>'+
      '<div class="perm-list">'+perms+'</div>'+
      '</div>';
  }).join('');
}
async function togglePerm(cb){
  const username=cb.getAttribute('data-u');
  const perms={};
  document.querySelectorAll('#usersList input[data-u="'+username+'"]').forEach(function(x){perms[x.getAttribute('data-p')]=x.checked;});
  try{
    const j=await api('/api/users/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username,perms:perms})});
    if(j.status==='ok'){showToast(tf('toast_perm',{u:username}));await loadUsers();}
    else showToast(errMsg(j),true);
  }catch(e){}
}
async function addUser(){
  const username=document.getElementById('newUsername').value.trim();
  const name=document.getElementById('newDisplayName').value.trim();
  const password=document.getElementById('newPassword').value;
  if(!username){showToast(t('e_username_required'),true);return;}
  if(password.length<6){showToast(t('e_password_short'),true);return;}
  const perms={};
  document.querySelectorAll('#newPerms input[data-perm]').forEach(function(x){perms[x.getAttribute('data-perm')]=x.checked;});
  try{
    const j=await api('/api/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username,name:name||username,password:password,perms:perms})});
    if(j.status==='ok'){
      showToast(tf('toast_user_added',{u:username}));
      document.getElementById('newUsername').value='';
      document.getElementById('newDisplayName').value='';
      document.getElementById('newPassword').value='';
      document.querySelectorAll('#newPerms input[data-perm]').forEach(function(x){x.checked=(x.getAttribute('data-perm')==='view');});
      await loadUsers();
    }else showToast(errMsg(j),true);
  }catch(e){}
}
async function deleteUser(username){
  if(!confirm(tf('confirm_del_user',{u:username})))return;
  try{
    const j=await api('/api/users/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username})});
    if(j.status==='ok'){showToast(t('toast_user_deleted'));await loadUsers();}
    else showToast(errMsg(j),true);
  }catch(e){}
}

/* ==================== النسخ الاحتياطي ==================== */
function openBackup(){
  if(!isAdmin())return;
  document.getElementById('backupModal').classList.add('show');
  loadBackups();
}
function closeBackup(){document.getElementById('backupModal').classList.remove('show');}
async function loadBackups(){
  try{
    const j=await api('/api/backups');
    BACKUPS=j.data||[];
    renderBackups();
  }catch(e){}
}
function renderBackups(){
  const box=document.getElementById('backupList');
  if(!BACKUPS.length){box.innerHTML='<div class="empty-msg">'+esc(t('backup_none'))+'</div>';return;}
  box.innerHTML=BACKUPS.map(function(b){
    const kb=Math.max(1,Math.round(b.size/1024));
    return '<div class="bk-row"><div><div class="bk-name">'+esc(b.name)+'</div>'+
      '<div class="bk-meta">'+esc(b.time)+' · '+esc(t('size'))+' '+kb+' KB</div></div>'+
      '<button class="btn btn-sm btn-warn" onclick="restoreBackup(&quot;'+esc(b.name)+'&quot;)">'+esc(t('restore'))+'</button></div>';
  }).join('');
}
async function createBackup(){
  try{
    const j=await api('/api/backups/create',{method:'POST'});
    if(j.status==='ok'){showToast(t('toast_backup'));await loadBackups();}
    else showToast(errMsg(j),true);
  }catch(e){}
}
async function restoreBackup(name){
  if(!confirm(t('confirm_restore')))return;
  try{
    const j=await api('/api/backups/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name})});
    if(j.status==='ok'){showToast(t('toast_restored'));closeBackup();loadPatients();}
    else showToast(errMsg(j),true);
  }catch(e){}
}
async function exportCsv(){
  window.location.href='/api/export.csv?lang='+LANG;
}

/* ==================== كلمة المرور ==================== */
function openPass(){
  document.getElementById('passCur').value='';
  document.getElementById('passNew').value='';
  document.getElementById('passConf').value='';
  document.getElementById('passModal').classList.add('show');
}
function closePass(){document.getElementById('passModal').classList.remove('show');}
async function savePassword(){
  const cur=document.getElementById('passCur').value;
  const nw=document.getElementById('passNew').value;
  const cf=document.getElementById('passConf').value;
  if(nw.length<6){showToast(t('e_password_short'),true);return;}
  if(nw!==cf){showToast(t('e_pass_mismatch'),true);return;}
  try{
    const j=await api('/api/password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({current:cur,new:nw})});
    if(j.status==='ok'){showToast(t('toast_pass'));closePass();}
    else showToast(errMsg(j),true);
  }catch(e){}
}

/* ==================== بدء التشغيل ==================== */
async function boot(){
  await loadSettings();
  try{
    const r=await fetch('/api/me');
    if(r.status===200){
      const j=await r.json();
      ME=j.user;
      applyPermissions();
      showApp();
      await loadPatients();
      return;
    }
  }catch(e){}
  showLogin();
}
document.addEventListener('DOMContentLoaded',function(){
  document.getElementById('loginPass').addEventListener('keydown',function(e){if(e.key==='Enter')doLogin();});
  document.getElementById('loginUser').addEventListener('keydown',function(e){if(e.key==='Enter')document.getElementById('loginPass').focus();});
  boot();
});
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    # ---------- helpers ----------
    def _json(self, data, code=200, extra_headers=None):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code, msg, status=400):
        self._json({"status": "error", "code": code, "message": msg}, status)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    def _session_token(self):
        cookie = self.headers.get("Cookie", "") or ""
        for part in cookie.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "session" and v:
                return v
        return None

    def current_user(self):
        token = self._session_token()
        if not token:
            return None
        username = SESSIONS.get(token)
        if not username:
            return None
        user = find_user(username)
        if not user or not user.get("active", True):
            return None
        return user

    def guard(self, perm=None, admin=False):
        user = self.current_user()
        if not user:
            self._err("login_required", "يجب تسجيل الدخول", 401)
            return None
        if admin and user.get("role") != "admin":
            self._err("admin_only", "هذه العملية للمدير فقط", 403)
            return None
        if perm and not user.get("perms", {}).get(perm):
            self._err("perm_denied", "لا تملك صلاحية لهذه العملية", 403)
            return None
        return user

    # ---------- GET ----------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            body = HTML_CONTENT.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/settings":
            self._json({"status": "ok", "settings": load_settings()})
            return

        if path == "/api/me":
            user = self.current_user()
            if not user:
                self._err("login_required", "غير مسجل", 401)
                return
            self._json({"status": "ok", "user": public_user(user)})
            return

        if path == "/api/patients":
            if not self.guard(perm="view"):
                return
            patients = load_patients()
            self._json({"status": "ok", "data": patients, "count": len(patients),
                        "warning": DATA_STATUS["warning"],
                        "last_edit": load_settings().get("last_edit", "")})
            return

        if path == "/api/search":
            if not self.guard(perm="view"):
                return
            q = unquote(parse_qs(parsed.query).get("q", [""])[0]).lower().strip()
            patients = load_patients()
            if not q:
                self._json({"status": "ok", "data": patients, "count": len(patients)})
                return
            results = [p for p in patients if q in " ".join([
                str(p.get("name", "")), str(p.get("age", "")),
                str(p.get("gender", "")), str(p.get("complaint", "")),
                str(p.get("date", "")),
            ]).lower()]
            self._json({"status": "ok", "data": results, "count": len(results)})
            return

        if path == "/api/users":
            if not self.guard(admin=True):
                return
            self._json({"status": "ok", "data": [public_user(u) for u in load_users()]})
            return

        if path == "/api/backups":
            if not self.guard(admin=True):
                return
            self._json({"status": "ok", "data": list_backups()})
            return

        if path == "/api/export.csv":
            if not self.guard(admin=True):
                return
            lang = parse_qs(parsed.query).get("lang", ["ar"])[0]
            headers = (["#", "Name", "Age", "Gender", "Complaint", "Date"] if lang == "en"
                       else ["#", "الاسم", "العمر", "الجنس", "الشكوى", "التاريخ"])
            lines = [",".join('"%s"' % h for h in headers)]
            for p in load_patients():
                g = p.get("gender", "")
                if lang == "en":
                    g = "Male" if g == "ذكر" else ("Female" if g == "أنثى" else g)
                row = [str(p.get("id", "")), p.get("name", ""), p.get("age", ""),
                       g, p.get("complaint", ""), p.get("date", "")]
                lines.append(",".join('"%s"' % str(c).replace('"', '""') for c in row))
            body = ("\ufeff" + "\r\n".join(lines)).encode("utf-8")
            fname = "patients_%s.csv" % datetime.now().strftime("%Y%m%d_%H%M")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % fname)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404)

    # ---------- POST ----------
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/login":
            self.handle_login()
            return

        if path == "/api/logout":
            token = self._session_token()
            if token:
                SESSIONS.pop(token, None)
            self._json({"status": "ok"}, 200, [("Set-Cookie", "session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")])
            return

        if path == "/api/settings":
            body = self._read_body()
            s = load_settings()
            lang = str(body.get("lang", "")).strip()
            theme = str(body.get("theme", "")).strip()
            if lang in ("ar", "en"):
                s["lang"] = lang
            if theme in ("dark", "light"):
                s["theme"] = theme
            save_settings(s)
            self._json({"status": "ok", "settings": s})
            return

        if path == "/api/password":
            user = self.guard()
            if not user:
                return
            body = self._read_body()
            cur = str(body.get("current", ""))
            new = str(body.get("new", ""))
            if not verify_password(cur, user.get("password", "")):
                self._err("bad_pass", "كلمة المرور الحالية غير صحيحة", 400)
                return
            if len(new) < 6:
                self._err("password_short", "كلمة المرور 6 أحرف على الأقل", 400)
                return
            users = load_users()
            for u in users:
                if u["username"].lower() == user["username"].lower():
                    u["password"] = hash_password(new)
                    break
            save_users(users)
            self._json({"status": "ok", "message": "تم تغيير كلمة المرور"})
            return

        if path == "/api/add":
            if not self.guard(perm="add"):
                return
            body = self._read_body()
            name = str(body.get("name", "")).strip()
            if not name:
                self._err("name_required", "الاسم مطلوب", 400)
                return
            patients = load_patients()
            patient = {
                "id": next_id(patients),
                "name": name,
                "age": str(body.get("age", "")).strip(),
                "gender": str(body.get("gender", "")).strip(),
                "complaint": str(body.get("complaint", "")).strip(),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            patients.append(patient)
            save_patients(patients)
            touch_last_edit()
            self._json({"status": "ok", "message": "تم حفظ بيانات المريض", "data": patient,
                        "last_edit": load_settings().get("last_edit", "")})
            return

        if path.startswith("/api/delete/"):
            if not self.guard(perm="delete"):
                return
            try:
                pid = int(path.split("/api/delete/")[1])
            except ValueError:
                self._err("not_found", "غير موجود", 400)
                return
            patients = load_patients()
            new_list = [p for p in patients if p["id"] != pid]
            if len(new_list) == len(patients):
                self._err("not_found", "غير موجود", 404)
                return
            save_patients(new_list)
            touch_last_edit()
            self._json({"status": "ok", "message": "تم حذف بيانات المريض",
                        "last_edit": load_settings().get("last_edit", "")})
            return

        if path.startswith("/api/update/"):
            if not self.guard(perm="edit"):
                return
            try:
                pid = int(path.split("/api/update/")[1])
            except ValueError:
                self._err("not_found", "غير موجود", 400)
                return
            body = self._read_body()
            patients = load_patients()
            found = False
            for p in patients:
                if p["id"] == pid:
                    p["name"] = str(body.get("name", p["name"])).strip()
                    p["age"] = str(body.get("age", p["age"])).strip()
                    p["gender"] = str(body.get("gender", p["gender"])).strip()
                    p["complaint"] = str(body.get("complaint", p["complaint"])).strip()
                    found = True
                    break
            if not found:
                self._err("not_found", "غير موجود", 404)
                return
            save_patients(patients)
            touch_last_edit()
            self._json({"status": "ok", "message": "تم تحديث البيانات",
                        "last_edit": load_settings().get("last_edit", "")})
            return

        if path == "/api/backups/create":
            if not self.guard(admin=True):
                return
            name = manual_backup(load_patients())
            self._json({"status": "ok", "message": "تم إنشاء نسخة احتياطية", "name": name})
            return

        if path == "/api/backups/restore":
            if not self.guard(admin=True):
                return
            body = self._read_body()
            name = str(body.get("name", "")).strip()
            if not name or "/" in name or "\\" in name or not name.endswith(".pmbak"):
                self._err("not_found", "اسم غير صالح", 400)
                return
            fpath = os.path.join(BACKUP_DIR, name)
            if not os.path.exists(fpath):
                self._err("not_found", "النسخة غير موجودة", 404)
                return
            env = _read_json(fpath)
            try:
                data = decrypt_store(env) if env else None
            except Exception:
                data = None
            if not isinstance(data, list):
                self._err("not_found", "النسخة تالفة", 400)
                return
            try:
                manual_backup(load_patients(), "manual")
            except Exception:
                pass
            save_patients(data)
            touch_last_edit()
            self._json({"status": "ok", "message": "تمت الاستعادة", "count": len(data)})
            return

        if path == "/api/users":
            if not self.guard(admin=True):
                return
            body = self._read_body()
            username = str(body.get("username", "")).strip()
            password = str(body.get("password", ""))
            name = str(body.get("name", "")).strip() or username
            perms_in = body.get("perms", {}) or {}

            if not username:
                self._err("username_required", "اسم المستخدم مطلوب", 400)
                return
            if len(password) < 6:
                self._err("password_short", "كلمة المرور 6 أحرف على الأقل", 400)
                return
            if find_user(username):
                self._err("user_exists", "اسم المستخدم موجود بالفعل", 400)
                return

            users = load_users()
            users.append({
                "username": username,
                "name": name,
                "password": hash_password(password),
                "role": "user",
                "perms": {p: bool(perms_in.get(p)) for p in PERMS},
                "active": True,
                "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
            save_users(users)
            self._json({"status": "ok", "message": "تمت إضافة المستخدم"})
            return

        if path == "/api/users/update":
            if not self.guard(admin=True):
                return
            body = self._read_body()
            username = str(body.get("username", "")).strip()
            users = load_users()
            target = None
            for u in users:
                if u["username"].lower() == username.lower():
                    target = u
                    break
            if not target:
                self._err("not_found", "المستخدم غير موجود", 404)
                return
            if target.get("role") == "admin":
                self._err("admin_locked", "لا يمكن تعديل صلاحيات المدير", 403)
                return

            if "perms" in body and isinstance(body["perms"], dict):
                target["perms"] = {p: bool(body["perms"].get(p)) for p in PERMS}
            if "password" in body and str(body["password"]):
                pw = str(body["password"])
                if len(pw) < 6:
                    self._err("password_short", "كلمة المرور 6 أحرف على الأقل", 400)
                    return
                target["password"] = hash_password(pw)
            if "active" in body:
                target["active"] = bool(body["active"])
            if "name" in body and str(body["name"]).strip():
                target["name"] = str(body["name"]).strip()

            save_users(users)
            self._json({"status": "ok", "message": "تم التحديث"})
            return

        if path == "/api/users/delete":
            if not self.guard(admin=True):
                return
            body = self._read_body()
            username = str(body.get("username", "")).strip()
            users = load_users()
            target = None
            for u in users:
                if u["username"].lower() == username.lower():
                    target = u
                    break
            if not target:
                self._err("not_found", "المستخدم غير موجود", 404)
                return
            if target.get("role") == "admin":
                self._err("admin_locked", "لا يمكن حذف حساب المدير", 403)
                return
            users = [u for u in users if u["username"].lower() != username.lower()]
            save_users(users)
            for token, uname in list(SESSIONS.items()):
                if uname.lower() == username.lower():
                    SESSIONS.pop(token, None)
            self._json({"status": "ok", "message": "تم حذف المستخدم"})
            return

        self.send_error(404)

    def handle_login(self):
        body = self._read_body()
        username = str(body.get("username", "")).strip()
        password = str(body.get("password", ""))

        if not username or not password:
            self._err("login_required", "أدخل اسم المستخدم وكلمة المرور", 400)
            return

        user = find_user(username)
        if not user or not verify_password(password, user.get("password", "")):
            self._err("bad_credentials", "اسم المستخدم أو كلمة المرور غير صحيحة", 401)
            return
        if not user.get("active", True):
            self._err("inactive", "هذا الحساب موقوف — راجع المدير", 403)
            return

        token = secrets.token_urlsafe(32)
        SESSIONS[token] = user["username"]
        self._json(
            {"status": "ok", "user": public_user(user)},
            200,
            [("Set-Cookie", f"session={token}; Path=/; Max-Age=604800; HttpOnly; SameSite=Lax")],
        )


def open_browser():
    webbrowser.open(f"http://localhost:{PORT}")


def main():
    ensure_admin()
    # نسخة احتياطية عند بدء التشغيل (مرة واحدة في اليوم)
    try:
        existing = load_patients()
        day = datetime.now().strftime("%Y-%m-%d")
        if not os.path.exists(os.path.join(BACKUP_DIR, "daily_%s.pmbak" % day)):
            daily_backup(existing)
    except Exception:
        pass

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    threading.Timer(1.0, open_browser).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
