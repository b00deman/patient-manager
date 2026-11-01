# مستشفى الخيري — Patient Data Manager

برنامج تسجيل بيانات المرضى للأستاذ / مستر بدوي.

## النسخة المحمولة — BADAWI PROJECT (ملف واحد)

المشروع كله متوفر في **ملف واحد** اسمه `BADAWI PROJECT.py` — انسخه على أي جهاز
وشغّله، بدون ما تحتاج تنسخ أي ملف ثاني (لا `index.html` ولا `server.py` ولا JSON).

```bash
python "BADAWI PROJECT.py"              # تشغيل عادي
python "BADAWI PROJECT.py" --port 18000 # منفذ مختلف
python "BADAWI PROJECT.py" --datadir "D:/PM"  # مجلد بيانات مخصص
python "BADAWI PROJECT.py" --no-browser # بدون فتح المتصفح
```

الدخول: `badawi` / `Badawi@2026`

### بناء الملف الواحد

```bash
python build_portable.py                    # نسخة بدون بيانات مرضى (الافتراضي — آمنة للنشر)
python build_portable.py --with-data        # نسخة مع بيانات المرضى (لنقلها لجهاز آخر)
python build_portable.py --out "D:/x/BADAWI PROJECT.py"
```

> **مهم:** النسخة المدمجة تشفّر البيانات، لكن **مفتاح التشفير ثابت داخل الكود**.
> لذلك النسخة التي تُرفع على GitHub يجب أن تكون **بدون بيانات مرضى**
> (الوضع الافتراضي). النسخة الشخصية (`--with-data`) تبقى على جهازك فقط.

### فحص التسريب قبل النشر

```bash
python check_no_data_leak.py
```

يفك تشفير بيانات Seed داخل الملفات المرشحة للنشر ويتأكد أنها فارغة.
اختبار سلبي مضمون: `python check_no_data_leak.py "BADAWI PROJECT.py"` يجب أن يفشل
لو الملف اتبنى بـ `--with-data`.

### حزمة التسليم الكاملة (exe + py + شهادة)

```bash
python build_release.py
```

ينتج مجلد `BADAWI PROJECT/` فيه: `BADAWI PROJECT.exe` (موقّع، بدون الحاجة لـ Python)،
`BADAWI PROJECT.py`، `BADAWI PROJECT.cer`، `README.md`، و`start.bat`.
هذا المجلد **لا يُرفع على GitHub** لأنه يحتوي بيانات المرضى الحقيقية.

## المميزات

- **إدخال بيانات المريض**: الاسم، العمر، الجنس، الشكوى
- **حفظ دائم مشفّر**: البيانات تُحفظ في `patients.json` بجانب البرنامج (مشفّرة، غير قابلة للتعديل من الخارج)
- **بحث فوري**: ابحث بالاسم أو العمر أو الجنس أو الشكوى
- **تعديل وحذف**: مع تأكيد قبل الحذف
- **طباعة**: زر طباعة لكل مريض مع ترويسة قابلة للتخصيص (اسم المستشفى، العنوان، رقم الهاتف)
- **نسخ احتياطي**: نسخة يومية تلقائية (آخر 30 يوم) + نسخ يدوية + استرجاع
- **عربي/إنجليزي** + ثيم فاتح/داكن، واللغة والثيم يُحفظان تلقائياً
- **دخول وصلاحيات** حسب الدور (عرض / إضافة / تعديل / حذف / طباعة)

## التقنيات

- Python HTTP server (standard library فقط — بدون أي مكتبة خارجية)
- HTML / CSS / JavaScript مدمجة داخل الملف
- PyInstaller (تجميع في ملف exe)

## طريقة التشغيل من الكود

```bash
python app.py
```
ثم افتح المتصفح على `http://localhost:17755`

## الملفات

| الملف | الوصف |
|---|---|
| `app.py` | الكود الكامل (سيرفر + HTML مدمج) — المصدر الأساسي |
| `BADAWI PROJECT.py` | **الملف الواحد المحمول** (بدون بيانات مرضى) |
| `build_portable.py` | يبني الملف الواحد من `app.py` |
| `build_release.py` | يبني حزمة التسليم كاملة (exe + py + cer) |
| `sign_exe.py` | توقّع ملف exe بشهادة ذاتية التوقيع |
| `check_no_data_leak.py` | حارس يمنع رفع بيانات المرضى على GitHub |
| `server.py` / `index.html` | نسخة منفصلة (للتطوير فقط) |

## بناء ملف exe

```bash
python -m PyInstaller --onefile --noconsole --name PatientManager app.py
```

