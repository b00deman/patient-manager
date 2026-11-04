# -*- coding: utf-8 -*-
"""
مستشفى الشيخ برير الشيخ الصديق - نظام تسجيل بيانات المرضى   |   BADAWI PROJECT
Alsheikh Berair Hospital - Patient Records System |   BADAWI PROJECT

النسخة المحمولة الكاملة: المشروع كله في ملف واحد (BADAWI PROJECT.py)
Portable all-in-one edition: the whole project lives in this single file.

Features:
  - Encrypted local storage (patients.json / users.json) -> not editable from outside
  - Automatic daily backups (keep 30) + manual backups + restore
  - Arabic / English interface
  - Dark / Light theme
  - Last used language, theme and last edit are persisted
  - Login + role based permissions (view / add / edit / delete / print)
  - Seed data embedded -> works on a brand-new machine with zero setup

التشغيل / Usage:
  python "BADAWI PROJECT.py"                       # تشغيل عادي
  python "BADAWI PROJECT.py" --port 18000          # منفذ مختلف
  python "BADAWI PROJECT.py" --datadir "D:/PM"     # مجلد بيانات مخصص
  python "BADAWI PROJECT.py" --no-browser          # بدون فتح المتصفح

بيانات الدخول الافتراضية: badawi / Badawi@2026
Default login: badawi / Badawi@2026
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import socket
import sys

# ------------------------------------------------------------------
#  تجهيز الـ console لعرض العربية بشكل صحيح على كل الأجهزة
#  (ويندوز يستخدم cp1252 افتراضياً ويسبّب UnicodeEncodeError)
# ------------------------------------------------------------------

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


import threading
import webbrowser
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

PORT_DEFAULT = 17760
APP_TAG = "badawi-hospital"


def _parse_args():
    """يقرأ خيارات التشغيل من سطر الأوامر"""
    opts = {"port": PORT_DEFAULT, "datadir": None, "no_browser": False, "windowed": False}
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
            continue
        if a.startswith("--port="):
            try:
                opts["port"] = int(a.split("=", 1)[1])
            except ValueError:
                pass
            i += 1
            continue
        if a in ("--datadir", "--data-dir") and i + 1 < len(argv):
            opts["datadir"] = argv[i + 1]
            i += 2
            continue
        if a.startswith("--datadir=") or a.startswith("--data-dir="):
            opts["datadir"] = a.split("=", 1)[1]
            i += 1
            continue
        if a in ("--no-browser", "--nobrowser"):
            opts["no_browser"] = True
            i += 1
            continue
        if a in ("--windowed", "--hide-console"):
            opts["windowed"] = True
            i += 1
            continue
        i += 1
    return opts


_OPTS = _parse_args()
PORT = _OPTS["port"]
ACTIVE_PORT = PORT


def _resolve_app_dir():
    """
    يختار مجلد البيانات:
      1) مجلد السكربت/الملف التنفيذي نفسه (كي تسير البيانات مع الملف)
      2) أو مجلد APPDATA لو كان المجلد غير قابل للكتابة (مثل Program Files)
    """
    if _OPTS.get("datadir"):
        d = os.path.abspath(os.path.expanduser(_OPTS["datadir"]))
        try:
            os.makedirs(d, exist_ok=True)
            return d
        except Exception:
            pass

    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.dirname(os.path.abspath(sys.executable)))
    else:
        candidates.append(os.path.dirname(os.path.abspath(__file__)))

    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    candidates.append(os.path.join(base, "BadawiPatientManager"))
    candidates.append(os.path.join(os.path.expanduser("~"), "BadawiPatientManager"))

    for c in candidates:
        try:
            os.makedirs(c, exist_ok=True)
            probe = os.path.join(c, ".write_test")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(probe)
            return c
        except Exception:
            continue
    return os.path.expanduser("~")


APP_DIR = _resolve_app_dir()

DATA_FILE = os.path.join(APP_DIR, "patients.json")
USERS_FILE = os.path.join(APP_DIR, "users.json")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
BACKUP_DIR = os.path.join(APP_DIR, "backups")

SESSIONS = {}

DEFAULT_ADMIN_USER = "badawi"
DEFAULT_ADMIN_PASS = "Badawi@2026"

PERMS = ["view", "add", "edit", "delete", "print", "lab"]

DATA_STATUS = {"warning": ""}

# ------------------------------------------------------------------
#  بيانات Seed مدمجة داخل الملف (تعمل على جهاز جديد من أول تشغيل)
# ------------------------------------------------------------------

_SEED_FILES = {
    "patients.json": "ew0KICAiX2Zvcm1hdCI6ICJQTTEiLA0KICAiX25vdGUiOiAi2KjZitin2YbYp9iqINmF2LTZgdmR2LHYqSAtINmE2Kcg2KrZj9i52K/ZkdmEINmK2K/ZiNmK2KfZiyAvIGVuY3J5cHRlZCAtIGRvIG5vdCBlZGl0IiwNCiAgInNhbHQiOiAiOGZmMjFiNjg1ZjQ1NWYyMWVlMmQ0ZDM2ODFmYmFhYjMiLA0KICAibm9uY2UiOiAiMmM2N2I1ZjA1OThlMzgwZTAxNjQ4NGI2ODFiOThlNTkiLA0KICAidGFnIjogIjczMjUzOWM5YWM0ZDNmZWZiMzgwNWUxMzE5N2JjMWY3NTkyMmEyNmNmMzRhNDY0ZTcyN2I3NThmOGZlYTJiOWUiLA0KICAiZGF0YSI6ICI0SzBmbGp0cmJnTVRlaDNtL3pPeVl0RHh4NUJUY0VuejNlV2R3S0o3M09ZZnh6YlhZbWtLeEZQQ1AwYm1ZYSsybjYzN1ZDM05LWjJEaW82RjZQY1pSUncrMDRlME9nak4rcmVQQmRDQWFqbWtiQW04emhWdzdVbk9uMm9pMy9rQUpHNVV0enlpbmc5UGhuenZxbUdidUhsK2dDV2pLWmpXaUM1OHh5ZFVpTVJVcGVQMG1ka01OeUlhNWxxWnMwSmpLSFJIUEhtUlFyYVdoUE1lUVVoSzJuOFJISitUUEVjSzRkbXhOK3pDdjhTOEhFa0xpclVRSVlpWSt1YnhCZ3ovd3dVcnAzUXJPVXYvUXNVazhSTzdzRWcyNmxHcDlpcGJiVDdyRzVDZFRXRnRiWEVUK1NNOHYxR3E2OUYxTWFIMGVGM2kzNW9hTUIweFd6MHMwZ3NwZmo4Yk5YRVBEWEJPaDN0RFA1bnk1SUQ5bjBveUZoaEhYZU9OZUNPdHpDKzVDVHlLVUZQSWVFeTJkM2p5TEdackVoTGF6aWdDMXZDRjI5Ym9JdkRCZHQ5NExiMFVBL3owOFlNNHZHYTRUMnhGRXJSQWs1bkVEMmduYnhVRGp2dmxvVm0yakVCdUUvQmt3YzY2K1I1OUhqL2Y2UEdocVFYaXBjSjN5Ly9KelMvdzhKdi9LaTdRIg0KfQ==",
    "users.json": "ew0KICAiX2Zvcm1hdCI6ICJQTTEiLA0KICAiX25vdGUiOiAi2KjZitin2YbYp9iqINmF2LTZgdmR2LHYqSAtINmE2Kcg2KrZj9i52K/ZkdmEINmK2K/ZiNmK2KfZiyAvIGVuY3J5cHRlZCAtIGRvIG5vdCBlZGl0IiwNCiAgInNhbHQiOiAiNWY4OGY0MTA4ZTA3MjRjMDhlZmEwNTUwNWRhNjk5YzgiLA0KICAibm9uY2UiOiAiY2Q2NDg2OWRmYzgxMGNlM2E0N2Q4ODcyZThhNjI5NjYiLA0KICAidGFnIjogImQ3NGE4YjIzZWQ1OTkzMmRhMWFhYWI2ZDY5ODJiMmQ0M2E2ZTQyNzYzZGM4ODIxYWZmNWY1MDdhZWJjYmZmYmUiLA0KICAiZGF0YSI6ICI2dGZVdW9XTDVSYmI1Vm14N3ViV2hvcERTbnFnTlJ5T0E2Vk9ZUVEzU1J3ZmF5YnJkS1ZGSElDMXRWdVR3UjhBVzR6MjBuU28yTzNEdjNqMGJNczdJWVNvTUYrU01xWDNvdnhFSkxWQzZaSkZ1U2lSZ2d0RVFqckZNWkZEKytPNEhYZElab2VNUVJiWkJONUp3VkUydkpCcTBJdWd4VjYzNEhQUHJFZ0VEOUdSNmtzN3g0TXErYUprMUkxYkpMeUhDOW9XTlBOellmNmxadmVUWjlOcDF4UzB5SXlGMm0vNDlyRXA3ajdWSWlnOS82YXRkZjM0cm9XQ1lsWndrUnNiTXdDemNlclhDN1ZibUdhWms2OTlPMk9JN3Y3ZEh4RDhzaVhmTEFZaEN0SlJ6bUNLdW1mLzI0NEQwTm5CeGpGZk9OYWdQOFVsWEJCbDc3di9USi9vcWltaVdVeHdMaE5ROFAxWmlhVmRGSlVzdldyWmUzVEMxeElyMjhmTjUzZ1N2QUVUWTNwZGZkQ2VTTTFtZWJYQTJRPT0iDQp9",
    "settings.json": "ewogICJsYW5nIjogImFyIiwKICAidGhlbWUiOiAiZGFyayIsCiAgImxhc3RfZWRpdCI6ICIiCn0=",
}


def seed_data_files():
    """ينشئ ملفات البيانات من النسخة المدمجة إذا لم تكن موجودة"""
    created = []
    for name, blob in _SEED_FILES.items():
        if not blob:
            continue
        path = os.path.join(APP_DIR, name)
        if os.path.exists(path):
            continue
        try:
            raw = base64.b64decode(blob)
            _atomic_write(path, raw.decode("utf-8"))
            created.append(name)
        except Exception:
            pass
    return created


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

DEFAULT_SETTINGS = {"lang": "ar", "theme": "dark", "last_edit": "", "last_ticket_number": 0}


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


def peek_next_ticket_number(patients):
    settings = load_settings()
    last = int(settings.get("last_ticket_number", 0) or 0)
    existing = [int(p.get("ticket_no", p.get("id", 0)) or 0) for p in patients]
    return max([last] + existing) + 1


def allocate_ticket_number(patients):
    settings = load_settings()
    number = peek_next_ticket_number(patients)
    settings["last_ticket_number"] = number
    save_settings(settings)
    return number


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
<html lang="ar" dir="rtl" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>مستشفى الشيخ برير الشيخ الصديق</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Lalezar&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap" rel="stylesheet">
<script>
try{
  var _p=JSON.parse(localStorage.getItem('pm_prefs')||'{}');
  if(_p.theme==='light'||_p.theme==='dark') document.documentElement.setAttribute('data-theme',_p.theme);
  if(_p.lang==='en'||_p.lang==='ar'){document.documentElement.lang=_p.lang;document.documentElement.dir=(_p.lang==='ar'?'rtl':'ltr');}
}catch(e){}
</script>
<style>
/* ============================================================
   مستشفى الشيخ برير الشيخ الصديق — refreshed UI (colors / typography / spacing)
   Consolidated single theme system — dark + light
   ============================================================ */

/* ---------- Design tokens ---------- */
:root{
  color-scheme:dark;
  /* الوضع الداكن — الألوان الفاتحة: #F6FBFF / #D6ECFF */
  --bg:#0d1319;--surface:#161e26;--surface2:#111921;--border:#263440;--border2:#384a59;
  --text:#F6FBFF;--dim:#D6ECFF;--mute:#9FB8CC;
  --accent:#F6FBFF;--accent2:#D6ECFF;--ink:#171F27;--accent-soft:rgba(214,236,255,.14);
  --hover:#1c2833;--chip:#1e2b37;--chip2:#2d3f4e;
  --shadow:0 1px 2px rgba(0,0,0,.22),0 20px 48px -20px rgba(0,0,0,.55);
  --shadow-sm:0 1px 2px rgba(0,0,0,.18),0 8px 20px -12px rgba(0,0,0,.40);
  --danger:#f2685f;--danger2:#df4d44;--warn:#f5a524;--warn2:#df8d0f;--ok:#4fc26b;--ok2:#3ba757;
  --logout-bg:#3a2320;--logout-fg:#ff9d94;--logout-bg2:#4a2e2a;--logout-fg2:#ffb5ab;
  --radius:18px;--radius-sm:11px;--radius-input:12px;
}
html[data-theme="light"]{
  color-scheme:light;
  /* الوضع النهاري — الألوان الغامقة: #383838 / #707070 / #A8A8A8 / #8B8C84 */
  --bg:#F3F4F4;--surface:#FFFFFF;--surface2:#F7F8F8;--border:#D6D8D7;--border2:#A8A8A8;
  --text:#383838;--dim:#707070;--mute:#8B8C84;
  --accent:#383838;--accent2:#707070;--ink:#F6FBFF;--accent-soft:rgba(56,56,56,.10);
  --hover:#E9EAEA;--chip:#E7E8E8;--chip2:#C9CBC9;
  --shadow:0 1px 2px rgba(30,35,38,.07),0 20px 46px -20px rgba(30,35,38,.28);
  --shadow-sm:0 1px 2px rgba(30,35,38,.05),0 8px 20px -12px rgba(30,35,38,.16);
  --danger:#d94f45;--danger2:#b93a31;--warn:#e07f10;--warn2:#c66a08;--ok:#2f8f46;--ok2:#227136;
  --logout-bg:#fdecea;--logout-fg:#c0392b;--logout-bg2:#f9dcd8;--logout-fg2:#a93226;
}

/* ---------- Base ---------- */
*{margin:0;padding:0;box-sizing:border-box;scrollbar-width:thin;scrollbar-color:var(--chip2) transparent}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--chip2);border-radius:10px;border:2px solid transparent;background-clip:padding-box}
::-webkit-scrollbar-thumb:hover{background:var(--mute);background-clip:padding-box}
::selection{background:var(--accent);color:var(--ink)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
svg{flex:none}
@media (prefers-reduced-motion:reduce){*{animation-duration:.01ms!important;transition-duration:.01ms!important}}

body{
  font-family:"IBM Plex Sans Arabic","Noto Sans Arabic",Tahoma,"Segoe UI",Arial,sans-serif;
  background:var(--bg);color:var(--text);min-height:100vh;
  padding:92px 24px 40px;letter-spacing:.01em;
  transition:background .25s,color .25s;overflow-x:hidden;
}
body:before{
  content:"";position:fixed;inset:0 0 auto;height:260px;pointer-events:none;
  background:linear-gradient(180deg,var(--accent-soft),transparent);z-index:-1;
}
.container{max-width:1120px;margin:0 auto}

html[lang="en"] body{font-family:"Inter","Segoe UI",system-ui,-apple-system,Roboto,"Helvetica Neue",Arial,sans-serif;letter-spacing:0}
html[lang="en"] header h1,html[lang="en"] .brand-mini,html[lang="en"] .login-logo{font-family:"Inter","Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;font-weight:800;letter-spacing:-.02em}
html[lang="en"] input,html[lang="en"] select,html[lang="en"] textarea,html[lang="en"] button{font-family:inherit}

input:-webkit-autofill{-webkit-box-shadow:0 0 0 1000px var(--surface2) inset;-webkit-text-fill-color:var(--text);caret-color:var(--text)}

/* ---------- Fixed top controls ---------- */
.topcontrols{
  position:fixed;top:0;left:0;right:0;height:64px;display:flex;align-items:center;
  justify-content:space-between;gap:12px;padding:0 max(24px,calc((100vw - 1120px)/2));
  background:rgba(13,19,25,.86);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
  border-bottom:1px solid var(--border);z-index:1500;box-shadow:0 8px 26px -18px rgba(0,0,0,.7);
}
html[data-theme="light"] .topcontrols{background:rgba(255,255,255,.86)}
.brand-mini{font-family:"Lalezar","Cairo","Noto Kufi Arabic","Reem Kufi","IBM Plex Sans Arabic",Tahoma,sans-serif;font-size:18px;font-weight:400;letter-spacing:0;color:var(--accent)}
.ctl-group{display:flex;align-items:center;gap:8px}
.seg{display:flex;gap:2px;background:var(--chip);border:1px solid var(--border2);border-radius:11px;padding:3px}
.seg-btn{background:transparent;border:none;color:var(--dim);padding:7px 14px;font-size:13px;font-family:inherit;cursor:pointer;font-weight:700;border-radius:8px;transition:background .18s,color .18s}
.seg-btn:hover{color:var(--text)}
.seg-btn.active{background:var(--accent);color:var(--ink);box-shadow:0 2px 8px -3px rgba(0,0,0,.45)}
.ctl-btn{background:var(--chip);border:1px solid var(--border2);color:var(--text);width:38px;height:38px;border-radius:10px;cursor:pointer;font-size:16px;line-height:1;display:flex;align-items:center;justify-content:center;transition:background .18s,transform .18s}
.ctl-btn:hover{background:var(--chip2);transform:translateY(-1px)}

/* ---------- Login bar ---------- */
#loginView{display:none;min-height:72vh;align-items:center;justify-content:center}
#loginView.show{display:flex}
.login-card{
  background:var(--surface);border:1px solid var(--border);border-radius:24px;
  padding:42px 36px;width:100%;max-width:760px;box-shadow:var(--shadow);
  position:relative;overflow:hidden;
}
.login-card:before{content:"";position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,var(--accent),var(--accent2) 55%,transparent)}
.login-logo{font-family:"Lalezar","Cairo","Noto Kufi Arabic","Reem Kufi","IBM Plex Sans Arabic",Tahoma,sans-serif;text-align:center;font-size:32px;font-weight:400;letter-spacing:0;color:var(--accent);margin-bottom:6px}
.login-sub{text-align:center;color:var(--mute);font-size:14px;margin-bottom:26px}
.login-bar{display:flex;flex-direction:column;align-items:stretch;gap:12px;background:var(--surface2);border:1px solid var(--border2);border-radius:16px;padding:16px}
.login-field{margin-bottom:0;width:100%;min-width:0}
.login-field label{display:block;font-size:14px;font-weight:600;color:var(--dim);margin-bottom:7px}
.login-field input{width:100%;background:var(--surface);border:1px solid var(--border2);border-radius:var(--radius-input);padding:12px 15px;color:var(--text);font-size:16px;font-family:inherit;outline:none;min-height:48px;transition:border-color .18s,box-shadow .18s,background .18s}
.login-field input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft);background:var(--surface)}
.pw-wrap{position:relative}
.pw-wrap input{padding-inline-end:46px}
.pw-eye{position:absolute;inset-inline-end:7px;top:50%;transform:translateY(-50%);width:36px;height:36px;border:none;background:transparent;color:var(--mute);border-radius:9px;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:background .18s,color .18s}
.pw-eye:hover{background:var(--chip);color:var(--text)}
.login-btn{width:100%;background:var(--accent);color:var(--ink);border:none;border-radius:var(--radius-sm);padding:13px 26px;min-height:48px;font-size:17px;font-weight:700;font-family:inherit;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:8px;box-shadow:0 8px 20px -10px rgba(0,0,0,.5);transition:background .18s,transform .18s,box-shadow .18s}
.login-btn:hover{background:var(--accent2);transform:translateY(-1px)}
.login-btn:disabled{opacity:.6;cursor:wait;transform:none}
.login-error{color:var(--danger);font-size:14px;font-weight:600;text-align:center;min-height:18px;margin-top:12px}

/* ---------- User bar ---------- */
.topbar{display:flex;justify-content:space-between;align-items:center;gap:12px;background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:12px 16px;margin-bottom:22px;flex-wrap:wrap;box-shadow:var(--shadow-sm)}
.topbar-user{display:flex;align-items:center;gap:8px;font-size:14px;color:var(--dim);flex-wrap:wrap}
.role-badge{font-size:12px;padding:4px 10px;border-radius:20px;font-weight:700}
.role-admin{background:var(--accent);color:var(--ink)}
.role-user{background:var(--chip2);color:var(--text)}
.topbar-actions{display:flex;gap:8px;flex-wrap:wrap}
.btn-mini{display:inline-flex;align-items:center;gap:7px;background:var(--chip);color:var(--dim);border:1px solid var(--chip2);border-radius:10px;padding:8px 15px;font-size:14px;font-family:inherit;cursor:pointer;font-weight:600;min-height:36px;transition:background .18s,color .18s,transform .18s}
.btn-mini:hover{background:var(--chip2);color:var(--text);transform:translateY(-1px)}
.btn-logout{background:var(--logout-bg);color:var(--logout-fg);border-color:var(--logout-bg)}
.btn-logout:hover{background:var(--logout-bg2);color:var(--logout-fg2)}
.last-edit{font-size:13px;color:var(--mute)}
#appView{display:none}
#appView.show{display:block}

/* ---------- Header ---------- */
header{
  position:relative;overflow:hidden;text-align:start;padding:28px 30px 26px;margin-bottom:24px;
  border:1px solid var(--border);border-radius:20px;background:var(--surface);box-shadow:var(--shadow-sm);
}
header:after{content:"";position:absolute;inset-inline-start:0;top:0;bottom:0;width:4px;background:linear-gradient(180deg,var(--accent),transparent)}
header h1{font-family:"Lalezar","Cairo","Noto Kufi Arabic","Reem Kufi","IBM Plex Sans Arabic",Tahoma,sans-serif;font-size:36px;letter-spacing:0;color:var(--accent);line-height:1.45;font-weight:400}
header p{font-size:15px;color:var(--mute);max-width:650px;line-height:1.9;margin-top:8px}

/* ---------- Cards ---------- */
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:28px;margin-bottom:22px;box-shadow:var(--shadow-sm)}
.card h2{font-size:20px;font-weight:700;letter-spacing:-.01em;color:var(--text);display:flex;align-items:center;gap:10px;margin-bottom:18px}
.card h2:before{content:"";display:inline-block;flex:none;width:5px;height:22px;border-radius:5px;background:var(--accent)}
.section-title{font-size:15px;color:var(--accent);font-weight:700;margin:22px 0 12px;padding-top:18px;border-top:1px solid var(--border)}
.hint{font-size:14px;color:var(--mute);line-height:1.8;margin-bottom:14px}

/* ---------- Forms ---------- */
.form-grid{display:grid;grid-template-columns:1fr;gap:11px}
#addCard{padding:24px}
#addCard .form-group label{margin-bottom:5px}
#addCard .form-group input,#addCard .form-group select{min-height:42px;padding:9px 13px;font-size:15px}
#addCard .form-group textarea{min-height:68px;padding:9px 13px;font-size:15px}
.form-group{display:flex;flex-direction:column}
.form-group.full{grid-column:1/-1}
.form-group label{font-size:13px;font-weight:700;letter-spacing:.02em;color:var(--dim);margin-bottom:7px}
.form-group input,.form-group select,.form-group textarea,
.search-bar input{
  background:var(--surface2);border:1px solid var(--border2);border-radius:var(--radius-input);
  padding:12px 15px;color:var(--text);font-size:16px;font-family:inherit;outline:none;min-height:48px;width:100%;
  transition:border-color .18s,box-shadow .18s,background .18s;
}
.form-group input:focus,.form-group select:focus,.form-group textarea:focus,
.search-bar input:focus{
  border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft);background:var(--surface);
}
.form-group textarea{min-height:92px;line-height:1.8;resize:vertical}
.form-group select{cursor:pointer}

/* ---------- Buttons ---------- */
.btn-row{display:flex;gap:12px;margin-top:18px;flex-wrap:wrap}
.btn{
  display:inline-flex;align-items:center;justify-content:center;gap:8px;
  padding:11px 22px;min-height:46px;border:none;border-radius:var(--radius-sm);
  font-size:16px;font-family:inherit;font-weight:700;letter-spacing:.01em;cursor:pointer;
  transition:background .18s,transform .15s,box-shadow .18s,filter .18s;
}
.btn:active{transform:translateY(1px) scale(.99)}
.btn-primary{background:var(--accent);color:var(--ink);box-shadow:0 6px 16px -8px rgba(0,0,0,.45)}
.btn-primary:hover{background:var(--accent2);transform:translateY(-1px)}
.btn-ok{background:var(--ok);color:#000}
.btn-ok:hover{background:var(--ok2);transform:translateY(-1px)}
.btn-del{background:var(--danger);color:#fff}
.btn-del:hover{background:var(--danger2);transform:translateY(-1px)}
.btn-warn{background:var(--warn);color:#000}
.btn-warn:hover{background:var(--warn2);transform:translateY(-1px)}
.btn-secondary{background:var(--chip);color:var(--dim);border:1px solid var(--chip2)}
.btn-secondary:hover{background:var(--chip2);color:var(--text)}
.btn-sm{padding:6px 13px;min-height:34px;font-size:14px;border-radius:9px}

/* ---------- Search + stats ---------- */
.search-bar{display:flex;gap:12px;margin-bottom:14px}
.search-bar input{flex:1}
.stats{display:flex;align-items:center;gap:8px;font-size:14px;color:var(--mute);margin-bottom:12px}
.stats:before{content:"";flex:none;width:7px;height:7px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.empty-msg{text-align:center;padding:34px 20px;color:var(--mute);font-size:16px;border:1px dashed var(--border2);border-radius:14px;background:var(--surface2)}

/* ---------- Table ---------- */
#appView>.container>.card{overflow-x:auto}
table{width:100%;border-collapse:separate;border-spacing:0 7px;margin-top:-7px}
th{padding:13px 12px;text-align:start;color:var(--dim);font-size:13px;font-weight:700;letter-spacing:.02em;border-bottom:1px solid var(--border);white-space:nowrap}
td{padding:14px 12px;text-align:start;border-bottom:1px solid var(--border);font-size:15px;line-height:1.6;color:var(--text)}
tbody tr{background:var(--surface2);transition:background .15s}
tbody tr td:first-child{border-radius:0 12px 12px 0}
tbody tr td:last-child{border-radius:12px 0 0 12px}
tbody tr:hover{background:var(--hover)}

/* ---------- Toast ---------- */
.toast{
  position:fixed;top:84px;left:50%;transform:translateX(-50%);
  background:var(--ok);color:#000;padding:13px 22px;border-radius:12px;
  font-size:16px;font-weight:600;z-index:3000;display:none;text-align:center;
  box-shadow:0 12px 30px -10px rgba(0,0,0,.5);max-width:90vw;
}
.toast.error{background:var(--danger)}
.toast.show{display:block;animation:fadeIn .28s}
@keyframes fadeIn{from{opacity:0;transform:translate(-50%,-10px)}to{opacity:1;transform:translate(-50%,0)}}

/* ---------- Modals ---------- */
.modal-overlay{
  display:none;position:fixed;inset:0;background:rgba(8,12,16,.62);
  backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);
  z-index:2000;justify-content:center;align-items:center;padding:20px;overflow:auto;
}
.modal-overlay.show{display:flex}
.modal{background:var(--surface);border:1px solid var(--border2);border-radius:20px;padding:30px;width:100%;max-width:580px;max-height:90vh;overflow:auto;box-shadow:var(--shadow)}
.modal h2{display:flex;align-items:center;gap:10px;color:var(--text);font-size:20px;font-weight:700;margin-bottom:20px}
.modal h2:before{content:"";flex:none;width:5px;height:20px;border-radius:5px;background:var(--accent)}
.modal .form-grid{grid-template-columns:1fr 1fr}
.modal .btn-row{justify-content:flex-end}

/* ---------- Users / backups ---------- */
.user-row{border:1px solid var(--border);border-radius:14px;padding:16px;margin-bottom:12px;background:var(--surface2);transition:border-color .18s}
.user-row:hover{border-color:var(--border2)}
.user-row-head{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.user-name{font-weight:700;color:var(--text);font-size:16px}
.user-meta{font-size:13px;color:var(--mute);margin-top:3px}
.perm-list{display:flex;flex-wrap:wrap;gap:14px}
.perm-item{display:flex;align-items:center;gap:6px;font-size:14px;color:var(--dim);cursor:pointer;user-select:none}
.perm-item input{width:16px;height:16px;accent-color:var(--accent);cursor:pointer}
.perm-item input:disabled{opacity:.45;cursor:not-allowed}
.bk-row{display:flex;justify-content:space-between;align-items:center;gap:10px;border:1px solid var(--border);background:var(--surface2);border-radius:12px;padding:11px 14px;margin-bottom:8px;flex-wrap:wrap}
.bk-name{font-size:14px;color:var(--text);font-weight:600}
.bk-meta{font-size:12px;color:var(--mute);margin-top:2px}

/* ---------- Print preview (single-page patient receipt) ---------- */
#printArea{background:#fff;color:#000;padding:24px;border-radius:8px;margin-bottom:16px;direction:rtl}
#printArea .ph-title{font-size:26px;font-weight:bold;text-align:center;margin-bottom:8px;color:#000}
#printArea .ph-datetime{text-align:center;font-size:14px;line-height:1.8;margin:8px 0 14px;padding-bottom:12px;border-bottom:2px solid #000;color:#000}
#printArea .ph-patient table{width:100%;border-collapse:collapse;page-break-inside:avoid;break-inside:avoid}
#printArea .ph-patient th,#printArea .ph-patient td{padding:9px 12px;text-align:start;border:1px solid #222;font-size:15px;color:#000;line-height:1.45}
#printArea .ph-patient th{background:#f3f3f3;font-weight:700;width:30%}
#printArea .ph-footer{text-align:center;font-size:19px;font-weight:700;margin-top:18px;color:#000}
@page{size:A4;margin:12mm}
@media print{
  html,body{background:#fff!important;padding:0!important;margin:0!important;width:100%!important;height:auto!important;overflow:visible!important}
  body:before{display:none!important}
  body *{visibility:hidden!important}
  #printModal{display:block!important;position:static!important;inset:auto!important;visibility:visible!important;background:transparent!important;padding:0!important;margin:0!important;width:100%!important;height:auto!important;overflow:visible!important;backdrop-filter:none!important;-webkit-backdrop-filter:none!important}
  #printModal .modal{display:block!important;position:static!important;visibility:visible!important;border:none!important;border-radius:0!important;box-shadow:none!important;width:100%!important;max-width:none!important;max-height:none!important;overflow:visible!important;padding:0!important;margin:0!important;background:#fff!important}
  #printModal .modal>*{visibility:hidden!important}
  #printArea,#printArea *{visibility:visible!important}
  #printArea{position:static!important;width:100%!important;max-width:100%!important;padding:0!important;margin:0!important;border-radius:0!important;box-shadow:none!important;background:#fff!important;page-break-inside:avoid;break-inside:avoid}
  #printArea .ph-title{font-size:24px}
  #printArea .ph-patient th,#printArea .ph-patient td{padding:8px 10px;font-size:14px}
}

/* ---------- Responsive ---------- */
@media(max-width:700px){
  body{padding:78px 14px 24px}
  .topcontrols{padding:0 14px}
  header{padding:23px 20px}
  header h1{font-size:28px}
  .card{padding:20px;border-radius:16px}
  .topbar{align-items:flex-start}
  .topbar-actions{width:100%}
  .topbar-actions .btn-mini{flex:1}
  .form-grid,.modal .form-grid{grid-template-columns:1fr}
  .form-group.full{grid-column:auto}
  .modal{padding:22px}
  .seg-btn{padding:7px 10px}
  .search-bar{flex-wrap:wrap}
  .login-bar{flex-direction:column;align-items:stretch}
  .login-btn{width:100%}
  .login-card{padding:30px 22px}
}
</style>
</head>
<body>

<!-- ============ شريط اللغة والثيم ============ -->
<div class="topcontrols">
  <div class="brand-mini" id="brandMini" data-i18n="brand">مستشفى الشيخ برير الشيخ الصديق</div>
  <div class="ctl-group">
    <div class="seg">
      <button class="seg-btn active" id="langAr" onclick="setLang('ar')">عربي</button>
      <button class="seg-btn" id="langEn" onclick="setLang('en')">EN</button>
    </div>
    <button class="ctl-btn" id="themeBtn" onclick="toggleTheme()" data-i18n-title="theme_tip"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg></button>
  </div>
</div>

<!-- ================= شاشة تسجيل الدخول ================= -->
<div id="loginView">
  <div class="login-card">
    <div class="login-logo" data-i18n="brand">مستشفى الشيخ برير الشيخ الصديق</div>
    <p class="login-sub" data-i18n="brand_sub">نظام تسجيل بيانات المرضى</p>
    <div class="login-bar">
      <div class="login-field">
        <label data-i18n="username">اسم المستخدم</label>
        <input type="text" id="loginUser" autocomplete="username" data-i18n-ph="ph_username">
      </div>
      <div class="login-field">
        <label data-i18n="password">كلمة المرور</label>
        <div class="pw-wrap">
          <input type="password" id="loginPass" autocomplete="current-password" data-i18n-ph="ph_password">
          <button type="button" class="pw-eye" id="pwEye" onclick="togglePw()" data-i18n-title="pw_show"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg></button>
        </div>
      </div>
      <button class="login-btn" id="loginBtn" onclick="doLogin()"><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="M10 17l5-5-5-5"/><path d="M15 12H3"/></svg><span data-i18n="login">دخول</span></button>
    </div>
    <div class="login-error" id="loginError"></div>
  </div>
</div>

<!-- ================= التطبيق ================= -->
<div id="appView">
<div class="container">

  <div class="topbar">
    <div class="topbar-user">
      <span><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></span>
      <span id="topUserName">-</span>
      <span id="topUserRole" class="role-badge role-user">-</span>
      <span class="last-edit" id="lastEdit"></span>
    </div>
    <div class="topbar-actions">
      <button class="btn-mini" id="btnUsers" onclick="openUsers()" style="display:none"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg><span data-i18n="btn_users">إدارة المستخدمين</span></button>
      <button class="btn-mini" id="btnBackup" onclick="openBackup()" style="display:none"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"/></svg><span data-i18n="btn_backup">النسخ الاحتياطي</span></button>
      <button class="btn-mini" id="btnPass" onclick="openPass()" style="display:none"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg><span data-i18n="btn_pass">كلمة المرور</span></button>
      <button class="btn-mini btn-logout" onclick="doLogout()"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg><span data-i18n="btn_logout">تسجيل الخروج</span></button>
    </div>
  </div>

  <header><h1 data-i18n="brand">مستشفى الشيخ برير الشيخ الصديق</h1><p data-i18n="header_sub">أدخل بيانات المريض وسيتم حفظها تلقائياً — يمكنك البحث والرجوع لها في أي وقت</p></header>

  <div class="card" id="addCard"><h2 data-i18n="card_add">تسجيل مريض جديد</h2>
    <div class="form-grid">
      <div class="form-group"><label data-i18n="ticket_number">رقم التذكرة</label><input type="text" id="ticketNumber" readonly></div>
      <div class="form-group"><label data-i18n="lbl_name">الاسم *</label><input type="text" id="name" data-i18n-ph="ph_name"></div>
      <div class="form-group"><label data-i18n="lbl_age">العمر</label><input type="number" id="age" min="0" max="150" data-i18n-ph="ph_age"></div>
      <div class="form-group"><label data-i18n="lbl_gender">الجنس</label>
        <select id="gender">
          <option value="" data-i18n="choose"></option>
          <option value="ذكر" data-i18n="male"></option>
          <option value="أنثى" data-i18n="female"></option>
        </select>
      </div>
      <div class="form-group"><label data-i18n="lbl_complaint">الشكوى</label><textarea id="complaint" data-i18n-ph="ph_complaint"></textarea></div>
      <div class="form-group"><label data-i18n="lbl_payment_method">طريقة الدفع</label><select id="paymentMethod"><option value="" data-i18n="choose"></option><option value="cash" data-i18n="payment_cash">كاش</option><option value="transfer" data-i18n="payment_transfer">تحويل</option></select></div>
      <div class="form-group"><label data-i18n="lbl_amount">المبلغ</label><input type="number" id="amount" min="0" step="0.01" inputmode="decimal" data-i18n-ph="ph_amount"></div>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" onclick="registerAndPrint()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg><span data-i18n="btn_register_print">تسجيل وطباعة</span></button>
      <button class="btn btn-secondary" onclick="clearForm()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg><span data-i18n="btn_clear">مسح الحقول</span></button>
    </div>
  </div>

  <div class="card"><h2 data-i18n="card_list">المرضى المسجلين</h2>
    <div class="search-bar">
      <input type="text" id="searchInput" data-i18n-ph="ph_search" oninput="searchPatients()">
      <button class="btn btn-secondary" id="btnExport" onclick="exportCsv()" style="display:none"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg><span data-i18n="btn_export">تصدير CSV</span></button>
    </div>
    <div class="stats" id="stats"></div>
    <table><thead><tr>
      <th>#</th><th data-i18n="th_name">الاسم</th><th data-i18n="th_age">العمر</th>
      <th data-i18n="th_gender">الجنس</th><th data-i18n="th_complaint">الشكوى</th>
      <th data-i18n="lbl_payment_method">طريقة الدفع</th><th data-i18n="lbl_amount">المبلغ</th>
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
    <div class="form-group"><label data-i18n="lbl_payment_method">طريقة الدفع</label><select id="editPaymentMethod"><option value="" data-i18n="choose"></option><option value="cash" data-i18n="payment_cash">كاش</option><option value="transfer" data-i18n="payment_transfer">تحويل</option></select></div>
    <div class="form-group"><label data-i18n="lbl_amount">المبلغ</label><input type="number" id="editAmount" min="0" step="0.01" inputmode="decimal"></div>
  </div>
  <div class="btn-row"><button class="btn btn-primary" onclick="saveEdit()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg><span data-i18n="save_edit">حفظ التعديل</span></button><button class="btn btn-secondary" onclick="closeModal()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg><span data-i18n="cancel">إلغاء</span></button></div>
</div></div>

<!-- معاينة الطباعة -->
<div class="modal-overlay" id="printModal"><div class="modal" style="max-width:620px">
  <h2 data-i18n="print_preview">معاينة الطباعة</h2>
  <div id="printArea"></div>
  <div class="btn-row" style="justify-content:center">
    <button class="btn btn-primary" onclick="doPrint()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg><span data-i18n="print_now">طباعة الآن</span></button>
    <button class="btn btn-secondary" onclick="closePrint()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg><span data-i18n="close">إغلاق</span></button>
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
    <label style="font-size:14px;color:var(--dim);display:block;margin-bottom:8px" data-i18n="perms">الصلاحيات</label>
    <div class="perm-list" id="newPerms">
      <label class="perm-item"><input type="checkbox" data-perm="view" checked> <span data-i18n="p_view">عرض</span></label>
      <label class="perm-item"><input type="checkbox" data-perm="add"> <span data-i18n="p_add">تسجيل</span></label>
      <label class="perm-item"><input type="checkbox" data-perm="edit"> <span data-i18n="p_edit">تعديل</span></label>
      <label class="perm-item"><input type="checkbox" data-perm="delete"> <span data-i18n="p_delete">حذف</span></label>
      <label class="perm-item"><input type="checkbox" data-perm="print"> <span data-i18n="p_print">طباعة</span></label>
      <label class="perm-item"><input type="checkbox" data-perm="lab"> <span data-i18n="p_lab">مجال المختبر</span></label>
    </div>
  </div>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="addUser()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/><path d="M19 8v6"/><path d="M22 11h-6"/></svg><span data-i18n="btn_add_user">إضافة المستخدم</span></button>
    <button class="btn btn-secondary" onclick="closeUsers()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg><span data-i18n="close">إغلاق</span></button>
  </div>
</div></div>

<!-- النسخ الاحتياطي -->
<div class="modal-overlay" id="backupModal"><div class="modal" style="max-width:620px">
  <h2 data-i18n="backup_title">النسخ الاحتياطي</h2>
  <p class="hint" data-i18n="backup_hint"></p>
  <div class="btn-row" style="justify-content:flex-start;margin-top:0">
    <button class="btn btn-primary btn-sm" onclick="createBackup()"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg><span data-i18n="backup_create">إنشاء نسخة الآن</span></button>
  </div>
  <div id="backupList" style="margin-top:16px"></div>
  <div class="btn-row"><button class="btn btn-secondary" onclick="closeBackup()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg><span data-i18n="close">إغلاق</span></button></div>
</div></div>

<!-- تغيير كلمة المرور -->
<div class="modal-overlay" id="passModal"><div class="modal" style="max-width:430px">
  <h2 data-i18n="pass_title">تغيير كلمة المرور</h2>
  <div class="form-group" style="margin-bottom:12px"><label data-i18n="pass_current">كلمة المرور الحالية</label><input type="password" id="passCur" autocomplete="current-password"></div>
  <div class="form-group" style="margin-bottom:12px"><label data-i18n="pass_new">كلمة المرور الجديدة</label><input type="password" id="passNew" autocomplete="new-password"></div>
  <div class="form-group"><label data-i18n="pass_confirm">تأكيد كلمة المرور</label><input type="password" id="passConf" autocomplete="new-password"></div>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="savePassword()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg><span data-i18n="save">حفظ</span></button>
    <button class="btn btn-secondary" onclick="closePass()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg><span data-i18n="cancel">إلغاء</span></button>
  </div>
</div></div>

<div class="toast" id="toast"></div>

<script>
/* ==================== الأيقونات (SVG) ==================== */
const ICON={
 moon:'<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>',
 sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
 login:'<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="M10 17l5-5-5-5"/><path d="M15 12H3"/>',
 eye:'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
 eyeOff:'<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-6.5 0-10-7-10-7a18.4 18.4 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.1 9.1 0 0 1 12 4c6.5 0 10 7 10 7a18.5 18.5 0 0 1-2.16 3.19"/><path d="M14.12 14.12A3 3 0 1 1 9.88 9.88"/><path d="M1 1l22 22"/>',
 pencil:'<path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/>',
 trash:'<path d="M3 6h18"/><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M10 11v6"/><path d="M14 11v6"/>',
 printer:'<path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>',
 restore:'<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>'
};
function sv(n,s){s=s||16;return '<svg viewBox="0 0 24 24" width="'+s+'" height="'+s+'" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(ICON[n]||'')+'</svg>';}
function togglePw(){
  const i=document.getElementById('loginPass');
  const b=document.getElementById('pwEye');
  const show=i.type==='password';
  i.type=show?'text':'password';
  b.innerHTML=sv(show?'eyeOff':'eye',16);
  b.title=t(show?'pw_hide':'pw_show');
  b.setAttribute('aria-pressed',show?'true':'false');
}
/* ==================== الترجمة / i18n ==================== */
const I18N={
ar:{
 brand:"مستشفى الشيخ برير الشيخ الصديق",brand_sub:"نظام تسجيل بيانات المرضى",
 username:"اسم المستخدم",password:"كلمة المرور",
 ph_username:"اسم المستخدم",ph_password:"كلمة المرور",
 login:"دخول",logging_in:"جارٍ الدخول...",pw_show:"إظهار كلمة المرور",pw_hide:"إخفاء كلمة المرور",
 role_admin:"مدير",role_user:"مستخدم",
 btn_users:"إدارة المستخدمين",btn_backup:"النسخ الاحتياطي",btn_pass:"كلمة المرور",btn_logout:"تسجيل الخروج",
 btn_export:"تصدير CSV",header_sub:"أدخل بيانات المريض وسيتم حفظها تلقائياً — يمكنك البحث والرجوع لها في أي وقت",
 card_add:"تسجيل مريض جديد",lbl_name:"الاسم *",ph_name:"اسم المريض",lbl_age:"العمر",ph_age:"العمر بالسنوات",
 lbl_gender:"الجنس",choose:"-- اختر --",male:"ذكر",female:"أنثى",
 lbl_complaint:"الشكوى",ph_complaint:"اكتب الشكوى / الأعراض",ticket_number:"رقم التذكرة",time_label:"الوقت",print_footer:"وَإِذَا مَرِضْتُ فَهُوَ يَشْفِينِ",lbl_payment_method:"طريقة الدفع",payment_cash:"كاش",payment_transfer:"تحويل",lbl_amount:"المبلغ",ph_amount:"أدخل المبلغ بالأرقام",
 btn_register:"تسجيل",btn_print:"طباعة",btn_register_print:"تسجيل وطباعة",btn_clear:"مسح الحقول",
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
    lab_title:"مجال المختبر",lab_intro:"المحتوى متاح فقط للمستخدمين المصرح لهم — سجل دخولك أو اطلب الصلاحية من المدير",
    lab_need_access:"أنت لست مرخصًا بدخول المختبر",lab_request_tip:"اطلب الصلاحية من المدير",
    lab_denied:"عذراً، لا تملك صلاحية الدخول إلى مجال المختبر",
    lab_load:"جارٍ التحميل…",lab_empty:"لا توجد محتويات في مختبر المختبر بعد",
    lab_access_granted:"تم منحك صلاحية المختبر",
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
 e_no_lab_access:"ليس لديك الصلاحية لدخول مختبر المختبر",
 e_bad_pass:"كلمة المرور الحالية غير صحيحة",e_pass_mismatch:"كلمتا المرور غير متطابقتين",
 e_conn:"تعذّر الاتصال بالبرنامج"
},
en:{
 brand:"Alsheikh Berair Hospital",brand_sub:"Patient Records System",
 username:"Username",password:"Password",
 ph_username:"Username",ph_password:"Password",
 login:"Sign in",logging_in:"Signing in...",pw_show:"Show password",pw_hide:"Hide password",
 role_admin:"Admin",role_user:"User",
 btn_users:"Users",btn_backup:"Backups",btn_pass:"Password",btn_logout:"Sign out",
 btn_export:"Export CSV",header_sub:"Enter patient details — they are saved automatically and can be searched any time",
 card_add:"New patient",lbl_name:"Name *",ph_name:"Patient name",lbl_age:"Age",ph_age:"Age in years",
 lbl_gender:"Gender",choose:"-- Select --",male:"Male",female:"Female",
 lbl_complaint:"Complaint",ph_complaint:"Write the complaint / symptoms",ticket_number:"Ticket number",time_label:"Time",print_footer:"And when I am ill, it is He who cures me",lbl_payment_method:"Payment method",payment_cash:"Cash",payment_transfer:"Transfer",lbl_amount:"Amount",ph_amount:"Enter amount",
 btn_register:"Save",btn_print:"Print",btn_register_print:"Save & print",btn_clear:"Clear fields",
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
 e_generic:"Something went wrong",e_login_required:"Please sign in",e_admin_only:"Admins only",e_no_lab_access:"You do not have permission to enter the Lab",
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
function paymentLabel(v){return v==='cash'?t('payment_cash'):(v==='transfer'?t('payment_transfer'):(v||''));}

/* ==================== المظهر واللغة ==================== */
function applyTheme(){
  document.documentElement.setAttribute('data-theme',THEME);
  const b=document.getElementById('themeBtn');
  if(b) b.innerHTML=sv(THEME==='dark'?'sun':'moon',18);
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
  const pi=document.getElementById('loginPass');
  pi.value='';pi.type='password';
  const pe=document.getElementById('pwEye');
  if(pe){pe.innerHTML=sv('eye',16);pe.setAttribute('aria-pressed','false');}
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
  btn.disabled=true;btn.innerHTML=sv('login',16)+'<span data-i18n="logging_in">'+t('logging_in')+'</span>';
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
    btn.disabled=false;btn.innerHTML=sv('login',16)+'<span data-i18n="login">'+t('login')+'</span>';
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
/* تعيين عرض عنصر بأمان - ما ينهار لو العنصر غير موجود */
function setDisp(id,val){const e=document.getElementById(id);if(e)e.style.display=val;}

function applyPermissions(){
  if(!ME)return;
  const u=document.getElementById('topUserName');
  if(u)u.textContent=ME.name||ME.username;
  const badge=document.getElementById('topUserRole');
  if(badge){
    if(isAdmin()){badge.textContent=t('role_admin');badge.className='role-badge role-admin';}
    else{badge.textContent=t('role_user');badge.className='role-badge role-user';}
  }
  setDisp('btnUsers',isAdmin()?'inline-flex':'none');
  setDisp('btnBackup',isAdmin()?'inline-flex':'none');
  setDisp('btnPass','inline-flex');
  setDisp('btnExport',isAdmin()?'inline-flex':'none');
  setDisp('addCard',can('add')?'block':'none');
  const showLab=!!(ME.perms&&ME.perms['lab'])&&!!document.getElementById('labPage');
  setDisp('btnLab',showLab?'inline-flex':'none');
  setDisp('labAccess',showLab?'block':'none');
  setDisp('labDenied',showLab?'none':'block');
  setDisp('labPage',showLab?'block':'none');
  if(showLab){document.getElementById('labContent').innerHTML='';applyLab();}
}

/* ==================== مختبر المختبر ==================== */
function applyLab(){
  if(!ME||!ME.perms||!ME.perms['lab']){closeLab();return;}
  const labPageEl=document.getElementById('labPage');
  const cl=document.getElementById('labContent');
  if(!labPageEl||!cl)return;
  labPageEl.style.display='block';
  cl.innerHTML='<p>'+esc(t('lab_load'))+'<span id="labLoading"></span></p>';
  api('/api/lab')
    .then(function(j){
      if(j&&j.allowed){
        const items=j.content||[];
        if(items.length){
          cl.innerHTML=items.map(function(x){
            return '<div class="lab-item" style="border:1px solid var(--border2);border-radius:12px;padding:18px;margin:12px 0;background:var(--surface2);break-inside:avoid"><div style="font-weight:700;color:var(--text);margin-bottom:8px">'+esc(x.name)+'</div><pre style="font-size:14px;color:var(--text);background:var(--surface);padding:14px;border-radius:8px;overflow:auto;white-space:pre-wrap" dir="auto">'+esc(x.content)+'</pre></div>';
          }).join('');
          const ll=document.getElementById('labLoading');
          if(ll)ll.textContent='';
        }else{
          cl.innerHTML='<p data-i18n="lab_empty">لا توجد محتويات في مختبر المختبر بعد.</p>';
        }
      }else{
        closeLab();
        showToast(errMsg(j),true);
      }
    })
    .catch(function(){closeLab();showToast(t('e_conn'),true);});
}
function closeLab(){
  setDisp('labPage','none');
  setDisp('labAccess','block');
  setDisp('labGate','block');
  setDisp('labDenied','none');
}
function openLabRequest(){
  if(!ME)return;
  const room=document.getElementById('labRequestRoom');
  const rid=room.value.trim()||('lab-'+Date.now());
  room.value='';
  api('/api/lab',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request:{roomId:rid,status:'requested'}})})
    .then(function(j){
      if(j&&j.granted){closeLab();showToast(t('lab_access_granted'),true);}
      else showToast(errMsg(j),true);
    })
    .catch(function(){showToast(t('e_conn'),true);});
}
function renderLabAccess(){
  if(!ME||!ME.perms||!ME.perms['lab']){closeLab();}
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
    document.getElementById('ticketNumber').value=j.next_ticket_number||'';
    viewPatients=allPatients;
    renderTable(viewPatients);
    if(j.last_edit){LAST_EDIT=j.last_edit;renderLastEdit();}
    if(j.warning==='restored')showToast(t('warn_restored'),true);
    else if(j.warning==='tampered')showToast(t('warn_tampered'),true);
  }catch(e){}
}
async function registerAndPrint(){
  const n=document.getElementById('name').value.trim();
  const a=document.getElementById('age').value.trim();
  const g=document.getElementById('gender').value;
  const c=document.getElementById('complaint').value.trim();
  const pm=document.getElementById('paymentMethod').value;
  const amount=document.getElementById('amount').value.trim();
  if(!n){showToast(t('e_name_required'),true);return;}
  try{
    const j=await api('/api/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n,age:a,gender:g,complaint:c,payment_method:pm,amount:amount})});
    if(j.status==='ok'){
      showToast(t('toast_saved'));
      if(j.last_edit){LAST_EDIT=j.last_edit;renderLastEdit();}
      loadPatients();
      buildPrintCard(j.data||{name:n,age:a,gender:g,complaint:c,payment_method:pm,amount:amount,date:''});
      document.getElementById('printModal').classList.add('show');
      setTimeout(function(){window.print();},150);
      clearForm();
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
    if(can('edit'))acts+='<button class="btn btn-sm btn-warn" onclick="openEdit('+x.id+')">'+sv('pencil',14)+esc(t('edit'))+'</button> ';
    if(can('delete'))acts+='<button class="btn btn-sm btn-del" onclick="del('+x.id+')">'+sv('trash',14)+esc(t('del'))+'</button> ';
    if(can('print'))acts+='<button class="btn btn-sm btn-ok" onclick="printPatient('+x.id+')">'+sv('printer',14)+esc(t('print'))+'</button>';
    if(!acts)acts='<span style="color:var(--mute);font-size:13px">'+esc(t('view_only'))+'</span>';
    return '<tr><td>'+esc(x.ticket_no||x.id)+'</td><td>'+esc(x.name)+'</td><td>'+esc(x.age)+'</td><td>'+esc(genderLabel(x.gender))+'</td><td>'+esc(x.complaint||'')+'</td><td>'+esc(paymentLabel(x.payment_method))+'</td><td>'+esc(x.amount||'')+'</td><td style="font-size:13px;color:var(--mute)" dir="ltr">'+esc(x.date)+'</td><td>'+acts+'</td></tr>';
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
  document.getElementById('editComplaint').value=p.complaint||'';
  document.getElementById('editPaymentMethod').value=p.payment_method||'';
  document.getElementById('editAmount').value=p.amount||'';
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
      complaint:document.getElementById('editComplaint').value.trim(),
      payment_method:document.getElementById('editPaymentMethod').value,
      amount:document.getElementById('editAmount').value.trim()
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
  document.getElementById('paymentMethod').value='';
  document.getElementById('amount').value='';
}

/* ==================== الطباعة ==================== */
function buildPrintCard(p){
  const pa=document.getElementById('printArea');
  pa.setAttribute('dir',LANG==='ar'?'rtl':'ltr');
  const now=new Date();
  const dateText=now.toLocaleDateString(LANG==='ar'?'ar':'en-GB');
  const timeText=now.toLocaleTimeString(LANG==='ar'?'ar':'en-GB',{hour:'2-digit',minute:'2-digit'});
  pa.innerHTML=
    '<div class="ph-title">'+esc(t('brand'))+'</div>'+ 
    '<div class="ph-datetime"><div>'+esc(t('th_date'))+': '+esc(dateText)+'</div><div>'+esc(t('time_label'))+': '+esc(timeText)+'</div></div>'+
    '<div class="ph-patient"><table>'+
    '<tr><th>'+esc(t('ticket_number'))+'</th><td>'+esc(p.ticket_no||p.id||'')+'</td></tr>'+  
    '<tr><th>'+esc(t('lbl_name').replace(' *',''))+'</th><td>'+esc(p.name)+'</td></tr>'+
    '<tr><th>'+esc(t('lbl_age'))+'</th><td>'+esc(p.age)+'</td></tr>'+
    '<tr><th>'+esc(t('lbl_gender'))+'</th><td>'+esc(genderLabel(p.gender))+'</td></tr>'+
    '<tr><th>'+esc(t('lbl_complaint'))+'</th><td>'+esc(p.complaint||'')+'</td></tr>'+ 
    '<tr><th>'+esc(t('lbl_payment_method'))+'</th><td>'+esc(paymentLabel(p.payment_method))+'</td></tr>'+ 
    '<tr><th>'+esc(t('lbl_amount'))+'</th><td>'+esc(p.amount||'')+'</td></tr>'+
    '</table></div>'+
    '<div class="ph-footer">{ '+esc(t('print_footer'))+' }</div>';
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
    payment_method:document.getElementById('paymentMethod').value,
    amount:document.getElementById('amount').value.trim(),
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
    const delBtn=isSelf?'<span class="user-meta">'+esc(t('you'))+'</span>':'<button class="btn btn-sm btn-del" onclick="deleteUser(&quot;'+esc(u.username)+'&quot;)">'+sv('trash',14)+esc(t('del'))+'</button>';
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
      '<button class="btn btn-sm btn-warn" onclick="restoreBackup(&quot;'+esc(b.name)+'&quot;)">'+sv('restore',14)+esc(t('restore'))+'</button></div>';
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

        if path == "/api/ping":
            # فحص صحة بسيط - يُستخدم لمنع تشغيل نسختين في نفس الوقت
            self._json({"status": "ok", "app": APP_TAG, "pid": os.getpid()})
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
                        "next_ticket_number": peek_next_ticket_number(patients),
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
            for u in load_users():
                u["perms"]["lab"] = bool(u.get("perms", {}).get("lab"))
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
            headers = (["Ticket number", "Name", "Age", "Gender", "Complaint", "Payment method", "Amount", "Date"] if lang == "en"
                       else ["رقم التذكرة", "الاسم", "العمر", "الجنس", "الشكوى", "طريقة الدفع", "المبلغ", "التاريخ"])
            lines = [",".join('"%s"' % h for h in headers)]
            for p in load_patients():
                g = p.get("gender", "")
                if lang == "en":
                    g = "Male" if g == "ذكر" else ("Female" if g == "أنثى" else g)
                payment = p.get("payment_method", "")
                if lang == "en":
                    payment = "Cash" if payment == "cash" else ("Transfer" if payment == "transfer" else payment)
                row = [str(p.get("ticket_no", p.get("id", ""))), p.get("name", ""), p.get("age", ""),
                       g, p.get("complaint", ""), payment, p.get("amount", ""), p.get("date", "")]
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

        if path == "/api/users":
            if not self.guard(admin=True):
                return
            for u in load_users():
                u["perms"]["lab"] = bool(u.get("perms", {}).get("lab"))
            self._json({"status": "ok", "data": [public_user(u) for u in load_users()]})
            return

        if path == "/api/export.csv":
            if not self.guard(admin=True):
                return
            lang = parse_qs(parsed.query).get("lang", ["ar"])[0]
            headers = (["Ticket number", "Name", "Age", "Gender", "Complaint", "Payment method", "Amount", "Date"] if lang == "en"
                       else ["رقم التذكرة", "الاسم", "العمر", "الجنس", "الشكوى", "طريقة الدفع", "المبلغ", "التاريخ"])
            lines = [",".join('"%s"' % h for h in headers)]
            for p in load_patients():
                g = p.get("gender", "")
                if lang == "en":
                    g = "Male" if g == "ذكر" else ("Female" if g == "أنثى" else g)
                payment = p.get("payment_method", "")
                if lang == "en":
                    payment = "Cash" if payment == "cash" else ("Transfer" if payment == "transfer" else payment)
                row = [str(p.get("ticket_no", p.get("id", ""))), p.get("name", ""), p.get("age", ""),
                       g, p.get("complaint", ""), payment, p.get("amount", ""), p.get("date", "")]
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

        if path == "/api/reset-sessions":
            # local-only: called when the exe is launched again while already running
            if self.headers.get("X-Local-Reset") == "1" and self.client_address[0] in ("127.0.0.1", "::1"):
                SESSIONS.clear()
                self._json({"status": "ok"}, 200, [("Set-Cookie", "session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")])
            else:
                self._err("forbidden", "forbidden", 403)
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
                "ticket_no": allocate_ticket_number(patients),
                "name": name,
                "age": str(body.get("age", "")).strip(),
                "gender": str(body.get("gender", "")).strip(),
                "complaint": str(body.get("complaint", "")).strip(),
                "payment_method": str(body.get("payment_method", "")).strip(),
                "amount": str(body.get("amount", "")).strip(),
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
                    p["complaint"] = str(body.get("complaint", p.get("complaint", ""))).strip()
                    p["payment_method"] = str(body.get("payment_method", p.get("payment_method", ""))).strip()
                    p["amount"] = str(body.get("amount", p.get("amount", ""))).strip()
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

        # ---------- Lab page: content available only to users with the lab permission ----------
        if path == "/api/lab":
            if not self.guard(admin=True):
                return
            body = self._read_body() or {}
            token = self._session_token()
            user = self.current_user()
            req = body.get("request") or {}
            rid = str(req.get("roomId", "")).strip()
            status = req.get("status", "")
            if rid and status == "granted":
                if user and user.get("role") == "admin":
                    lab_requests = load_requests()
                    if rid in lab_requests:
                        del lab_requests[rid]
                        save_requests(lab_requests)
                    self._json({"status": "ok", "granted": True})
                    return
            if user and user.get("perms", {}).get("lab"):
                self._json({"status": "ok", "allowed": True,
                            "content": load_lab_content()})
                return
            self._json({"status": "denied", "message": t("e_no_lab_access")}, 403)
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
            [("Set-Cookie", f"session={token}; Path=/; HttpOnly; SameSite=Lax")],
        )


def open_browser():
    webbrowser.open(f"http://localhost:{ACTIVE_PORT}")


def _port_is_free(port):
    """
    فحص المنفذ بدون SO_REUSEADDR.
    لازم يكون بدون SO_REUSEADDR لأن ويندوز يسمح بـ hijack لمنفذ مشغول
    إذا الكوكي مفعّل (وهو افتراضي في ThreadingHTTPServer).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        try:
            s.close()
        except OSError:
            pass


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    """
    نفس ThreadingHTTPServer لكنه لا يطبع Traceback عندما يقطع المتصفح الاتصال
    (WinError 10053 / 10054) - وهو أمر طبيعي وليس خطأ.
    """

    daemon_threads = True
    allow_reuse_address = False

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (
            ConnectionAbortedError,
            ConnectionResetError,
            BrokenPipeError,
            TimeoutError,
        )):
            return
        # أخطاء الشبكة المعتادة على ويندوز
        if isinstance(exc, OSError) and getattr(exc, "winerror", None) in (
            10053, 10054, 10038, 10058,
        ):
            return
        super().handle_error(request, client_address)


def _probe_app(port, timeout=0.6):
    """
    يتحقق إن كان المنفذ يخدم نسخة شغّالة من نفس البرنامج.
    يرجع True لو النسخة موجودة وتعمل.
    """
    import urllib.request
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:%d/api/ping" % port, timeout=timeout
        ) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return isinstance(data, dict) and data.get("app") == APP_TAG
    except Exception:
        return False


def _pick_server(preferred):
    """يختار منفذاً متاحاً - مهم عند نقل البرنامج لجهاز فيه برنامج على نفس المنفذ"""
    last_err = None
    for p in range(preferred, preferred + 25):
        srv = None
        try:
            if not _port_is_free(p):
                last_err = OSError("port %d is already in use" % p)
                continue
            srv = QuietThreadingHTTPServer(("127.0.0.1", p), Handler)
            return srv, p
        except OSError as e:
            last_err = e
            if srv is not None:
                try:
                    srv.server_close()
                except Exception:
                    pass
    raise last_err if last_err else OSError("no free port found")


def main():
    global ACTIVE_PORT

    # منع تشغيل نسختين في نفس الوقت:
    # لو في نسخة شغّالة أصلاً على نفس المنفذ، نفتح المتصفح عليها ونخرج بهدوء.
    if _probe_app(PORT):
        msg = [
            "=" * 58,
            "  BADAWI PROJECT  |  النسخة تعمل بالفعل",
            "  العنوان / URL  : http://localhost:%d" % PORT,
            "=" * 58,
        ]
        if sys.stdout is not None:
            try:
                for _line in msg:
                    print(_line)
                sys.stdout.flush()
            except Exception:
                pass
        # force the login page: clear any session left from the previous run
        try:
            import urllib.request
            _rq = urllib.request.Request("http://127.0.0.1:%d/api/reset-sessions" % PORT, data=b"{}", method="POST", headers={"X-Local-Reset": "1", "Content-Type": "application/json"})
            urllib.request.urlopen(_rq, timeout=2).read()
        except Exception:
            pass
        if not _OPTS.get("no_browser"):
            webbrowser.open(f"http://localhost:{PORT}")
        return 0

    seeded = seed_data_files()
    ensure_admin()

    # نسخة احتياطية عند بدء التشغيل (مرة واحدة في اليوم)
    try:
        existing = load_patients()
        day = datetime.now().strftime("%Y-%m-%d")
        if not os.path.exists(os.path.join(BACKUP_DIR, "daily_%s.pmbak" % day)):
            daily_backup(existing)
    except Exception:
        pass

    server, ACTIVE_PORT = _pick_server(PORT)
    server.daemon_threads = True

    banner = [
        "=" * 58,
        "  BADAWI PROJECT  |  مستشفى الشيخ برير الشيخ الصديق - Alsheikh Berair Hospital",
        "  العنوان / URL  : http://localhost:%d" % ACTIVE_PORT,
        "  مجلد البيانات  : %s" % APP_DIR,
    ]
    if seeded:
        banner.append("  تم إنشاء ملفات البيانات: %s" % ", ".join(seeded))
    banner.append("  الدخول / Login : badawi  /  Badawi@2026")
    banner.append("=" * 58)

    if sys.stdout is not None:
        try:
            for _line in banner:
                print(_line)
            sys.stdout.flush()
        except Exception:
            pass

    try:
        with open(os.path.join(APP_DIR, "BADAWI PROJECT.log"), "w", encoding="utf-8") as f:
            for _line in banner:
                f.write(_line + "\n")
    except Exception:
        pass

    if not _OPTS.get("no_browser"):
        threading.Timer(1.0, open_browser).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


# ---------- Lab page content (admin-only API, plain text reports) ----------

def ensure_requests_file():
    path = os.path.join(APP_DIR, "lab_requests.json")
    if not os.path.exists(path):
        _atomic_write(path, json.dumps({}, ensure_ascii=False, indent=2))
    return path


def load_requests():
    ensure_requests_file()
    try:
        data = _read_json(load_requests.path)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


load_requests.path = ensure_requests_file()


def save_requests(reqs):
    _atomic_write(load_requests.path, json.dumps(reqs, ensure_ascii=False, indent=2))


LAP_DIR = os.path.join(APP_DIR, "lab")


def ensure_lab_dir():
    os.makedirs(LAP_DIR, exist_ok=True)
    try:
        _prune("lab_", 8)
    except Exception:
        pass


def load_lab_content():
    """يقرأ ملفات المحتوى السليمة من مجلد lab/ (مملوكة للمدير فقط)"""
    ensure_lab_dir()
    items = []
    try:
        files = sorted(os.listdir(LAP_DIR))
    except OSError:
        return items
    for fn in files:
        if not fn.endswith(".lab"):
            continue
        p = os.path.join(LAP_DIR, fn)
        try:
            raw = open(p, encoding="utf-8").read()
        except Exception:
            continue
        items.append({"name": fn, "content": raw})
    return items


def add_lab_content(name, content):
    ensure_lab_dir()
    if not name.lower().endswith(".lab"):
        name = name + ".lab"
    p = os.path.join(LAP_DIR, name)
    _atomic_write(p, content)
    return name


def delete_lab_content(name):
    ensure_lab_dir()
    if not name.lower().endswith(".lab"):
        name = name + ".lab"
    p = os.path.join(LAP_DIR, name)
    if os.path.exists(p):
        os.remove(p)
        return True
    return False


if __name__ == "__main__":
    main()
