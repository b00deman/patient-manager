# -*- coding: utf-8 -*-
"""
build_portable.py
يبني الملف الواحد "BADAWI PROJECT.py" من app.py + بيانات المشروع.

الملف الناتج مستقل تماماً: لا يحتاج index.html ولا server.py ولا ملفات JSON خارجية.
يُنشئ بيانات Seed مدمجة ليعمل على جهاز جديد من أول تشغيل.

الاستخدام:
  python build_portable.py                       # نسخة بدون بيانات مرضى (الافتراضي — آمنة للنشر)
  python build_portable.py --with-data           # نسخة مع بيانات المرضى الحالية (لنقلها لجهاز آخر)
  python build_portable.py --out "D:/x/BADAWI PROJECT.py"
"""
import base64
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "app.py")
OUT = os.path.join(HERE, "BADAWI PROJECT.py")


# ------------------------------------------------------------------
#  خيارات سطر الأوامر
# ------------------------------------------------------------------
def _parse_args(argv):
    """
      --out PATH / -o PATH : مسار ملف الإخراج (افتراضياً BADAWI PROJECT.py)
      --with-data          : دمج بيانات المرضى والمستخدمين الحقيقية داخل الملف
                             (مفيد لنقل البيانات لجهاز آخر — لا يُرفع على GitHub)
    الافتراضي: نسخة بدون أي بيانات مرضى — آمنة للرفع على GitHub.
    """
    out = OUT
    with_data = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--out", "-o") and i + 1 < len(argv):
            out = os.path.abspath(argv[i + 1])
            i += 2
            continue
        if a.startswith("--out=") or a.startswith("-o="):
            out = os.path.abspath(a.split("=", 1)[1])
            i += 1
            continue
        if a in ("--with-data", "--full", "--data"):
            with_data = True
            i += 1
            continue
        i += 1
    return out, with_data


OUT_PATH, WITH_DATA = _parse_args(sys.argv[1:])


# ------------------------------------------------------------------
#  تجهيز بيانات Seed (تُدمج داخل الملف الواحد)
# ------------------------------------------------------------------
def seed_b64(name):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return ""
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _load_app_module():
    """يستورد app.py لاستخدام دوال التشفير نفسها — بدون تشغيل السيرفر"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_pm_app_src", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_blank_seeds():
    """
    يبني بيانات Seed فارغة (بدون أي بيانات مرضى حقيقية).
    تُستخدم للنسخة التي تُرفع على GitHub حتى لا تتسرب بيانات المرضى.
    - patients.json : قائمة مشفّرة فارغة []
    - users.json    : مستخدم المدير الافتراضي فقط
    - settings.json : اللغة والثيم الافتراضيان
    """
    mod = _load_app_module()
    env = mod.encrypt_store([])
    seed_patients = base64.b64encode(
        json.dumps(env, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("ascii")

    admin = {
        "username": mod.DEFAULT_ADMIN_USER,
        "name": "بدوي",
        "password": mod.hash_password(mod.DEFAULT_ADMIN_PASS),
        "role": "admin",
        "perms": {p: True for p in mod.PERMS},
        "active": True,
        "created": mod.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    env_u = mod.encrypt_store([admin])
    seed_users = base64.b64encode(
        json.dumps(env_u, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("ascii")

    seed_settings = base64.b64encode(
        json.dumps({"lang": "ar", "theme": "dark", "last_edit": ""},
                   ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("ascii")
    return seed_patients, seed_users, seed_settings


if WITH_DATA:
    seed_patients = seed_b64("patients.json")
    seed_users = seed_b64("users.json")

    settings_path = os.path.join(HERE, "settings.json")
    settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            settings = {}
    settings["last_edit"] = ""
    seed_settings = base64.b64encode(
        json.dumps(settings, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("ascii")
else:
    seed_patients, seed_users, seed_settings = build_blank_seeds()


NEW_DOC = '''"""
مستشفى الخيري - نظام تسجيل بيانات المرضى   |   BADAWI PROJECT
Al-Khairi Hospital - Patient Records System |   BADAWI PROJECT

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
"""'''

NEW_CONSOLE = '''

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

'''

NEW_PATHS = '''PORT_DEFAULT = 17755


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
BACKUP_DIR = os.path.join(APP_DIR, "backups")'''

NEW_SEED = '''# ------------------------------------------------------------------
#  بيانات Seed مدمجة داخل الملف (تعمل على جهاز جديد من أول تشغيل)
# ------------------------------------------------------------------

_SEED_FILES = {
    "patients.json": "%s",
    "users.json": "%s",
    "settings.json": "%s",
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
# ------------------------------------------------------------------''' % (seed_patients, seed_users, seed_settings)

NEW_BROWSER = '''def open_browser():
    webbrowser.open(f"http://localhost:{ACTIVE_PORT}")'''

NEW_MAIN = r'''def _port_is_free(port):
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


def _pick_server(preferred):
    """يختار منفذاً متاحاً - مهم عند نقل البرنامج لجهاز فيه برنامج على نفس المنفذ"""
    last_err = None
    for p in range(preferred, preferred + 25):
        srv = None
        try:
            if not _port_is_free(p):
                last_err = OSError("port %d is already in use" % p)
                continue
            srv = ThreadingHTTPServer(("127.0.0.1", p), Handler)
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
        "  BADAWI PROJECT  |  مستشفى الخيري - Al-Khairi Hospital",
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
        server.shutdown()'''


def patch(src, pattern, repl, label, flags=re.S):
    out, n = re.subn(pattern, lambda m: repl, src, count=1, flags=flags)
    if n != 1:
        raise SystemExit("FAILED to patch: %s (matches=%d)" % (label, n))
    return out


def main_build():
    with open(SRC, encoding="utf-8") as f:
        src = f.read()

    src = patch(src, r'"""\nمستشفى الخيري.*?\n"""', NEW_DOC, "docstring")
    src = patch(
        src,
        r'import secrets\nimport sys',
        "import secrets\nimport socket\nimport sys" + NEW_CONSOLE,
        "socket_import",
    )
    src = patch(
        src,
        r'PORT = 17755\n\nif getattr\(sys, .frozen., False\):.*?BACKUP_DIR = os\.path\.join\(APP_DIR, "backups"\)',
        NEW_PATHS,
        "paths",
    )
    src = patch(
        src,
        r'# -+\n#  التشفير  /  Encryption \(stdlib only, encrypt-then-MAC\)\n# -+',
        NEW_SEED,
        "seed",
    )
    src = patch(
        src,
        r'def open_browser\(\):\n    webbrowser\.open\(f"http://localhost:\{PORT\}"\)',
        NEW_BROWSER,
        "open_browser",
    )
    src = patch(
        src,
        r'def main\(\):.*?\n        server\.shutdown\(\)',
        NEW_MAIN,
        "main",
    )

    out_dir = os.path.dirname(OUT_PATH)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    mode = ("FULL (مع بيانات المرضى)" if WITH_DATA
            else "BLANK (بدون بيانات مرضى — آمن للنشر)")
    print("built -> %s (%d bytes)" % (OUT_PATH, len(src.encode("utf-8"))))
    print("seed mode -> %s" % mode)


if __name__ == "__main__":
    main_build()
