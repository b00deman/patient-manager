# -*- coding: utf-8 -*-
"""
check_no_data_leak.py
حارس أمني: يتأكد إن أي ملف مصمّم للنشر (GitHub) لا يحتوي بيانات مرضى حقيقية.

السبب: مفتاح التشفير _SECRET ثابت داخل الكود، فأي شخص يقرأ الملف
يستطيع فك تشفير بيانات Seed المدمجة. لذلك النسخة المنشورة يجب أن تكون
بدون بيانات مرضى.

الاستخدام:
  python check_no_data_leak.py                 # يفحص كل الملفات المرشحة للنشر
  python check_no_data_leak.py "BADAWI PROJECT.py"   # يفحص ملف محدد
"""
import base64
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "app.py")

# الملفات التي يجب ألا تُرفع أبداً (نسخة التسليم الشخصية + ملفات البيانات)
NEVER_PUBLISH = [
    "patients.json",
    "users.json",
    "settings.json",
    "backups",
    "BADAWI PROJECT/BADAWI PROJECT.py",
]

# الملفات المرشحة للنشر (نتحقق من خلوّها من بيانات المرضى)
CHECK_TARGETS = [
    "BADAWI PROJECT.py",
    "build_portable.py",
    "build_release.py",
    "sign_exe.py",
]


def _load_app_module():
    spec = importlib.util.spec_from_file_location("_pm_app_src", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_B64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


def extract_seed(path):
    """
    يستخرج خرائط _SEED_FILES من ملف مبني.
    يتجاهل القيم التي ليست base64 حقيقي (مثل "%s" في ملفات البناء).
    """
    with open(path, encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"_SEED_FILES = \{(.*?)\n\}", src, re.S)
    if not m:
        return None
    out = {}
    for name, blob in re.findall(r'"([^"]+)": "([^"]*)"', m.group(1)):
        blob = blob.strip()
        if len(blob) < 64 or not _B64_RE.match(blob):
            continue  # قيمة نصية (قالب) وليست بيانات فعلية
        out[name] = blob
    return out


def check_file(path, mod):
    """يفحص ملف واحد — يرجع قائمة مشاكل"""
    problems = []
    rel = os.path.relpath(path, HERE).replace("\\", "/")

    if not os.path.exists(path):
        return ["%s: الملف غير موجود" % rel]

    seed = extract_seed(path)
    if seed is None:
        return []  # ليس ملفاً مبنياً — لا مشكلة

    for name in ("patients.json", "users.json"):
        blob = seed.get(name)
        if not blob:
            continue
        try:
            raw = base64.b64decode(blob)
            data = mod.decrypt_store(json.loads(raw.decode("utf-8")))
        except Exception as e:
            problems.append("%s: فشل فك تشفير %s (%s)" % (rel, name, e))
            continue

        if name == "patients.json":
            if isinstance(data, list) and len(data) > 0:
                names = ", ".join(str(p.get("name", "?")) for p in data[:5])
                problems.append(
                    "%s: يحتوي على %d سجل مريض حقيقي (%s...)" % (rel, len(data), names))
        elif name == "users.json":
            if isinstance(data, list):
                extra = [u for u in data
                         if u.get("username") != mod.DEFAULT_ADMIN_USER]
                if extra:
                    problems.append("%s: يحتوي على مستخدمين إضافيين: %s"
                                    % (rel, ", ".join(u.get("username", "?") for u in extra)))
    return problems


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    mod = _load_app_module()

    if len(sys.argv) > 1:
        targets = sys.argv[1:]
    else:
        targets = [os.path.join(HERE, t) for t in CHECK_TARGETS if os.path.exists(os.path.join(HERE, t))]

    if not targets:
        print("لا توجد ملفات للفحص.")
        return 0

    all_problems = []
    print("=" * 62)
    print("  فحص تسريب البيانات / Data-leak check")
    print("=" * 62)

    for t in targets:
        path = t if os.path.isabs(t) else os.path.join(HERE, t)
        rel = os.path.relpath(path, HERE).replace("\\", "/")
        problems = check_file(path, mod)
        if problems:
            all_problems.extend(problems)
            print("  [FAIL] %s" % rel)
            for p in problems:
                print("         - %s" % p)
        else:
            print("  [ OK ] %s" % rel)

    print("-" * 62)
    if all_problems:
        print("  RESULT: FAILED — يوجد بيانات مرضى في ملفات النشر")
        print("  استخدم 'python build_portable.py' (بدون --with-data)")
        print("=" * 62)
        return 1
    print("  RESULT: PASSED — لا توجد بيانات مرضى في ملفات النشر")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
