# -*- coding: utf-8 -*-
"""
build_release.py
يبني حزمة BADAWI PROJECT كاملة:

  1) BADAWI PROJECT.py   -> الملف الواحد (Python) مع كل شيء مدمج
  2) BADAWI PROJECT.exe  -> ملف تنفيذي واحد موقّع (يعمل بدون Python)
  3) BADAWI PROJECT.cer  -> الشهادة العامة (اختياري: للثقة على جهاز آخر)
  4) README.md           -> التعليمات

الاستخدام:  python build_release.py
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RELEASE = os.path.join(HERE, "BADAWI PROJECT")

PY_FILE = os.path.join(HERE, "BADAWI PROJECT.py")
EXE_FILE = os.path.join(HERE, "dist", "BADAWI PROJECT.exe")

README = """# BADAWI PROJECT — مستشفى الخيري

نظام تسجيل بيانات المرضى في **ملف واحد**. انسخ المجلد كله للجهاز الجديد وشغّله.

## الملفات

| الملف | الوصف |
|---|---|
| `BADAWI PROJECT.exe` | البرنامج جاهز — **دبل كlick** ويفتح في المتصفح. لا يحتاج Python. |
| `BADAWI PROJECT.py` | نفس البرنامج كملف Python — للتعديل على الكود أو للتشغيل بدون exe. |
| `BADAWI PROJECT.cer` | شهادة توقيع الملف exe (اختياري — لو ويندوز طلب "Unknown publisher"). |
| `README.md` | هذا الملف. |

## طريقة التشغيل

### الأسهل
دبل كليك على `BADAWI PROJECT.exe` → يفتح المتصفح على `http://localhost:17755`

### من سطر الأوامر (اختياري)
```
"BADAWI PROJECT.exe" --port 18000          # منفذ مختلف
"BADAWI PROJECT.exe" --datadir "D:/PM"     # مجلد بيانات مخصص
"BADAWI PROJECT.exe" --no-browser          # بدون فتح المتصفح تلقائياً
"BADAWI PROJECT.exe" --windowed            # بدون نافذة الكونسول
```

وللنسخة Python:
```
python "BADAWI PROJECT.py"
```

## الدخول

- المستخدم: `badawi`
- كلمة المرور: `Badawi@2026`

> يُفضّل تغيير كلمة المرور من زر **كلمة المرور** بعد أول دخول.

## وين تُحفظ البيانات؟

في نفس مجلد البرنامج — عشان البيانات تسير معاه على أي جهاز:

```
BADAWI PROJECT.exe
patients.json      <- بيانات المرضى (مشفّرة)
users.json         <- المستخدمين والصلاحيات (مشفّرة)
settings.json      <- اللغة والثيم
backups\\           <- النسخ الاحتياطية
BADAWI PROJECT.log <- العنوان ورقم المنفذ
```

لو نُقل البرنامج إلى مجلد غير قابل للكتابة (مثل `Program Files`)، ينتقل تلقائياً إلى:
`%APPDATA%\\BadawiPatientManager`

## نقل البيانات بين الأجهزة

- **من داخل البرنامج:** زر **النسخ الاحتياطي** ← نسخة يدوية داخل مجلد `backups`.
- **لنسخ كل البيانات:** انسخ `patients.json` + `users.json` + مجلد `backups` إلى الجهاز الجديد.
- الملفات **مشفّرة** — لا تُعدّلها يدوياً.

## لو ويندوز منع التشغيل

بعض أجهزة ويندوز 11 فيها **Smart App Control** يمنع تشغيل أي ملف exe جديد غير موقّع.
الحل: ثبّت الشهادة المرفقة مرة واحدة (تحتاج صلاحية مدير):

```powershell
Import-Certificate -FilePath "BADAWI PROJECT.cer" -CertStoreLocation Cert:\\LocalMachine\\TrustedPublisher
```

أو شغّل نسخة Python مباشرة (تحتاج Python مثبّت):
```
python "BADAWI PROJECT.py"
```

## ملاحظات

- البرنامج يعمل **محلياً على جهازك فقط** (127.0.0.1) — لا يُعرَض على الإنترنت.
- لو المنفذ 17755 مشغول، يختار البرنامج منفذاً التالي تلقائياً.
- الواجهة: عربي/إنجليزي + ثيم فاتح/داكن.
"""


def run(cmd, label):
    print("\n>>> %s" % label)
    r = subprocess.run(cmd, cwd=HERE, shell=isinstance(cmd, str))
    if r.returncode != 0:
        raise SystemExit("FAILED: %s (exit=%s)" % (label, r.returncode))
    return r


def main():
    # 1) بناء الملف الواحد (مع بيانات المرضى — هذه نسخة التسليم الشخصية)
    run([sys.executable, "build_portable.py", "--with-data"], "build portable .py")

    # 2) بناء الـ exe
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "BADAWI PROJECT.spec"], "build exe")

    # 3) توقيع الـ exe (لتفادي Smart App Control)
    run([sys.executable, "sign_exe.py"], "sign exe")

    # 4) تجميع مجلد التسليم
    print("\n>>> assemble release folder")
    if os.path.isdir(RELEASE):
        shutil.rmtree(RELEASE)
    os.makedirs(RELEASE)

    shutil.copy2(EXE_FILE, RELEASE)
    shutil.copy2(PY_FILE, RELEASE)
    shutil.copy2(os.path.join(HERE, "dist", "BADAWI PROJECT.cer"), RELEASE)

    with open(os.path.join(RELEASE, "README.md"), "w", encoding="utf-8") as f:
        f.write(README)

    print("\n" + "=" * 58)
    print("  BADAWI PROJECT release ready")
    print("  -> %s" % RELEASE)
    for name in sorted(os.listdir(RELEASE)):
        p = os.path.join(RELEASE, name)
        print("     %-28s %10d bytes" % (name, os.path.getsize(p)))
    print("=" * 58)


if __name__ == "__main__":
    main()
