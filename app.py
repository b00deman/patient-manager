# -*- coding: utf-8 -*-
"""
Patient Data Manager - Standalone Executable
برنامج تسجيل بيانات المرضى - ملف تنفيذي مستقل
"""
import json
import os
import sys
import threading
import subprocess
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

PORT = 17755

# مسار ملف البيانات - بيتحفظ جنب ملف exe
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(APP_DIR, "patients.json")

HTML_CONTENT = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>مستشفى الخيري</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Tahoma,Arial,sans-serif;background:#0f1923;color:#e0e6ed;min-height:100vh;padding:20px}
.container{max-width:900px;margin:0 auto}
header{text-align:center;padding:30px 0 20px;border-bottom:1px solid #1e2d3a;margin-bottom:25px}
header h1{font-size:28px;color:#4fc3f7;font-weight:600}
header p{color:#78909c;margin-top:8px;font-size:14px}
.card{background:#162029;border:1px solid #1e2d3a;border-radius:12px;padding:24px;margin-bottom:20px}
.card h2{font-size:18px;color:#4fc3f7;margin-bottom:18px;font-weight:600}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.form-group{display:flex;flex-direction:column}
.form-group.full{grid-column:1/-1}
.form-group label{font-size:13px;color:#90a4ae;margin-bottom:6px}
.form-group input,.form-group select,.form-group textarea{background:#0f1923;border:1px solid #2a3b4a;border-radius:8px;padding:10px 14px;color:#e0e6ed;font-size:15px;font-family:inherit;outline:none;transition:border-color .2s}
.form-group input:focus,.form-group select:focus,.form-group textarea:focus{border-color:#4fc3f7}
.form-group textarea{resize:vertical;min-height:60px}
.btn-row{display:flex;gap:12px;margin-top:18px}
.btn{padding:11px 28px;border:none;border-radius:8px;font-size:15px;font-family:inherit;cursor:pointer;transition:all .2s;font-weight:600}
.btn-primary{background:#4fc3f7;color:#0f1923}
.btn-primary:hover{background:#29b6f6}
.btn-secondary{background:#263238;color:#90a4ae;border:1px solid #37474f}
.btn-secondary:hover{background:#37474f;color:#e0e6ed}
.btn-danger{background:#ef5350;color:#fff;padding:6px 14px;font-size:13px;border-radius:6px}
.btn-danger:hover{background:#e53935}
.btn-edit{background:#ffa726;color:#0f1923;padding:6px 14px;font-size:13px;border-radius:6px}
.btn-edit:hover{background:#fb8c00}
.search-bar{display:flex;gap:10px;margin-bottom:16px}
.search-bar input{flex:1;background:#0f1923;border:1px solid #2a3b4a;border-radius:8px;padding:10px 14px;color:#e0e6ed;font-size:15px;outline:none}
.search-bar input:focus{border-color:#4fc3f7}
.stats{font-size:13px;color:#78909c;margin-bottom:14px}
table{width:100%;border-collapse:collapse}
th,td{padding:12px 10px;text-align:right;border-bottom:1px solid #1e2d3a}
th{color:#4fc3f7;font-size:13px;font-weight:600}
td{font-size:14px}
tr:hover{background:#1a2632}
.empty-msg{text-align:center;padding:40px;color:#546e7a;font-size:15px}
.toast{position:fixed;top:20px;right:50%;transform:translateX(50%);background:#2e7d32;color:#fff;padding:12px 24px;border-radius:8px;font-size:15px;z-index:999;display:none;box-shadow:0 4px 20px rgba(0,0,0,.4)}
.toast.error{background:#c62828}
.toast.show{display:block;animation:fadeIn .3s}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.modal-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.7);z-index:1000;justify-content:center;align-items:center}
.modal-overlay.show{display:flex}
.modal{background:#162029;border:1px solid #2a3b4a;border-radius:12px;padding:28px;width:90%;max-width:500px}
.modal h2{color:#4fc3f7;margin-bottom:20px}
.modal .form-grid{grid-template-columns:1fr 1fr}
.modal .btn-row{justify-content:flex-end}
.btn-print{background:#66bb6a;color:#fff;padding:6px 14px;font-size:13px;border-radius:6px;border:none;cursor:pointer;font-family:inherit;font-weight:600}
.btn-print:hover{background:#43a047}
.settings-row{display:flex;gap:12px;align-items:flex-end;margin-bottom:16px}
.settings-row .form-group{flex:1}
.print-header-config{background:#0f1923;border:1px solid #2a3b4a;border-radius:8px;padding:16px;margin-bottom:16px}
.print-header-config label{font-size:13px;color:#90a4ae;margin-bottom:6px;display:block}
.print-header-config input{width:100%;background:#0f1923;border:1px solid #2a3b4a;border-radius:6px;padding:8px 12px;color:#e0e6ed;font-size:14px;font-family:inherit;outline:none}
.print-header-config input:focus{border-color:#4fc3f7}
.print-header-config .cfg-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media print{body *{visibility:hidden}#printArea,#printArea *{visibility:visible}#printArea{position:absolute;left:0;top:0;width:100%;background:#fff;color:#000}#printArea .ph-title{font-size:24px;font-weight:bold;text-align:center;margin-bottom:4px;color:#000}#printArea .ph-address{text-align:center;font-size:15px;color:#000;margin-bottom:2px}#printArea .ph-phone{text-align:center;font-size:14px;color:#333;margin-bottom:20px;border-bottom:2px solid #000;padding-bottom:10px}#printArea .ph-patient{padding:10px 20px}#printArea .ph-patient h3{font-size:18px;margin-bottom:12px;color:#000}#printArea .ph-patient table{width:100%;border-collapse:collapse}#printArea .ph-patient th,#printArea .ph-patient td{padding:8px 12px;text-align:right;border:1px solid #999;font-size:14px;color:#000}#printArea .ph-patient th{background:#eee;font-weight:600}}
</style>
</head>
<body>
<div class="container">
<header><h1>مستشفى الخيري</h1><p>أدخل بيانات المريض وسيتم حفظها تلقائياً — يمكنك البحث والرجوع لها في أي وقت</p></header>
<div class="card"><h2>إضافة مريض جديد</h2>
<div class="form-grid">
<div class="form-group"><label>الاسم *</label><input type="text" id="name" placeholder="اسم المريض"></div>
<div class="form-group"><label>العمر</label><input type="number" id="age" placeholder="العمر بالسنوات" min="0" max="150"></div>
<div class="form-group"><label>الجنس</label><select id="gender"><option value="">-- اختر --</option><option value="ذكر">ذكر</option><option value="أنثى">أنثى</option></select></div>
<div class="form-group full"><label>الشكوى</label><textarea id="complaint" placeholder="اكتب الشكوى / الأعراض"></textarea></div>
</div>
<div class="btn-row"><button class="btn btn-primary" onclick="addPatient()">حفظ البيانات</button><button class="btn btn-secondary" onclick="clearForm()">مسح الحقول</button></div>
</div>
<div class="card"><h2>بيانات الطباعة (تظهر في أعلى الورقة)</h2>
<div class="print-header-config">
<div class="cfg-grid">
<div><label>العنوان (اسم المستشفى)</label><input type="text" id="cfgHospital" value="مستشفى الخيري"></div>
<div><label>العنوان - اختار أي عنوان</label><input type="text" id="cfgAddress" placeholder="اكتب العنوان هنا" value=""></div>
</div>
<div style="margin-top:12px"><label>رقم الهاتف</label><input type="text" id="cfgPhone" placeholder="اكتب رقم الهاتف" value=""></div>
</div>
</div>
<div class="card"><h2>المرضى المسجلين</h2>
<div class="search-bar"><input type="text" id="searchInput" placeholder="ابحث بالاسم أو العمر أو الجنس أو الشكوى..." oninput="searchPatients()"></div>
<div class="stats" id="stats">جاري التحميل...</div>
<table><thead><tr><th>#</th><th>الاسم</th><th>العمر</th><th>الجنس</th><th>الشكوى</th><th>التاريخ</th><th>إجراءات</th></tr></thead><tbody id="patientTable"></tbody></table>
<div class="empty-msg" id="emptyMsg" style="display:none">لا توجد بيانات مسجلة بعد</div>
</div>
</div>
<div class="modal-overlay" id="editModal"><div class="modal"><h2>تعديل بيانات المريض</h2>
<div class="form-grid">
<div class="form-group"><label>الاسم</label><input type="text" id="editName"></div>
<div class="form-group"><label>العمر</label><input type="number" id="editAge" min="0" max="150"></div>
<div class="form-group full"><label>الجنس</label><select id="editGender"><option value="">-- اختر --</option><option value="ذكر">ذكر</option><option value="أنثى">أنثى</option></select></div>
<div class="form-group full"><label>الشكوى</label><textarea id="editComplaint"></textarea></div>
</div>
<div class="btn-row"><button class="btn btn-primary" onclick="saveEdit()">حفظ التعديل</button><button class="btn btn-secondary" onclick="closeModal()">إلغاء</button></div>
</div></div>
<div class="toast" id="toast"></div>
<div id="printArea"></div>
<script>
let allPatients=[],editingId=null;
async function loadPatients(){try{const r=await fetch('/api/patients');const j=await r.json();allPatients=j.data||[];renderTable(allPatients)}catch(e){showToast('خطأ',true)}}
async function addPatient(){const n=document.getElementById('name').value.trim(),a=document.getElementById('age').value.trim(),g=document.getElementById('gender').value,c=document.getElementById('complaint').value.trim();if(!n){showToast('الاسم مطلوب',true);return}try{const r=await fetch('/api/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n,age:a,gender:g,complaint:c})});const j=await r.json();if(j.status==='ok'){showToast('تم حفظ بيانات المريض');clearForm();loadPatients()}else showToast(j.message||'خطأ',true)}catch(e){showToast('خطأ',true)}}
async function searchPatients(){const q=document.getElementById('searchInput').value.trim();if(!q){loadPatients();return}try{const r=await fetch('/api/search?q='+encodeURIComponent(q));const j=await r.json();renderTable(j.data||[])}catch(e){showToast('خطأ',true)}}
function renderTable(p){const tb=document.getElementById('patientTable'),st=document.getElementById('stats'),em=document.getElementById('emptyMsg');if(!p||!p.length){tb.innerHTML='';st.textContent='لا يوجد مرضى مسجلين';em.style.display='block';return}em.style.display='none';st.textContent='عدد المرضى: '+p.length;tb.innerHTML=p.map(x=>'<tr><td>'+x.id+'</td><td>'+esc(x.name)+'</td><td>'+esc(x.age)+'</td><td>'+esc(x.gender)+'</td><td>'+esc(x.complaint)+'</td><td style="font-size:12px;color:#78909c">'+esc(x.date)+'</td><td><button class="btn-edit" onclick="openEdit('+x.id+')">تعديل</button> <button class="btn-danger" onclick="del('+x.id+')">حذف</button> <button class="btn-print" onclick="printPatient('+x.id+')">طباعة</button></td></tr>').join('')}
async function del(id){if(!confirm('هل أنت متأكد من حذف بيانات هذا المريض؟'))return;try{const r=await fetch('/api/delete/'+id,{method:'POST'});const j=await r.json();if(j.status==='ok'){showToast('تم حذف البيانات');loadPatients()}else showToast(j.message||'خطأ',true)}catch(e){showToast('خطأ',true)}}
function openEdit(id){const p=allPatients.find(x=>x.id===id);if(!p)return;editingId=id;document.getElementById('editName').value=p.name;document.getElementById('editAge').value=p.age;document.getElementById('editGender').value=p.gender;document.getElementById('editComplaint').value=p.complaint;document.getElementById('editModal').classList.add('show')}
async function saveEdit(){if(editingId===null)return;const n=document.getElementById('editName').value.trim(),a=document.getElementById('editAge').value.trim(),g=document.getElementById('editGender').value,c=document.getElementById('editComplaint').value.trim();if(!n){showToast('الاسم مطلوب',true);return}try{const r=await fetch('/api/update/'+editingId,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n,age:a,gender:g,complaint:c})});const j=await r.json();if(j.status==='ok'){showToast('تم التحديث');closeModal();loadPatients()}else showToast(j.message||'خطأ',true)}catch(e){showToast('خطأ',true)}}
function closeModal(){document.getElementById('editModal').classList.remove('show');editingId=null}
function clearForm(){document.getElementById('name').value='';document.getElementById('age').value='';document.getElementById('gender').value='';document.getElementById('complaint').value=''}
function showToast(m,e){const t=document.getElementById('toast');t.textContent=m;t.className='toast show'+(e?' error':'');setTimeout(()=>{t.className='toast'},3000)}
function esc(s){if(!s)return'';return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function printPatient(id){const p=allPatients.find(x=>x.id===id);if(!p)return;const h=document.getElementById('cfgHospital').value||'مستشفى الخيري';const a=document.getElementById('cfgAddress').value||'';const ph=document.getElementById('cfgPhone').value||'';const pa=document.getElementById('printArea');pa.innerHTML='<div class="ph-title">'+esc(h)+'</div>'+(a?'<div class="ph-address">'+esc(a)+'</div>':'')+(ph?'<div class="ph-phone">هاتف: '+esc(ph)+'</div>':'<div class="ph-phone"></div>')+'<div class="ph-patient"><h3>بيانات المريض</h3><table><tr><th style="width:25%">الاسم</th><td style="width:75%">'+esc(p.name)+'</td></tr><tr><th>العمر</th><td>'+esc(p.age)+'</td></tr><tr><th>الجنس</th><td>'+esc(p.gender)+'</td></tr><tr><th>الشكوى</th><td>'+esc(p.complaint)+'</td></tr><tr><th>التاريخ</th><td>'+esc(p.date)+'</td></tr></table></div>';document.body.classList.add('printing');window.print();setTimeout(()=>{pa.innerHTML=''},500)}
window.onload=loadPatients;
</script>
</body>
</html>"""


def load_patients():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_patients(patients):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(patients, f, ensure_ascii=False, indent=2)


def next_id(patients):
    if not patients:
        return 1
    return max(p["id"] for p in patients) + 1


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        from urllib.parse import unquote
        if self.path in ("/", "/index.html"):
            body = HTML_CONTENT.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/patients":
            patients = load_patients()
            self._json({"status": "ok", "data": patients, "count": len(patients)})
        elif self.path.startswith("/api/search?q="):
            q = unquote(self.path.split("/api/search?q=")[1]).lower().strip()
            patients = load_patients()
            if not q:
                self._json({"status": "ok", "data": patients, "count": len(patients)})
                return
            results = [p for p in patients if q in " ".join([
                str(p.get("name", "")), str(p.get("age", "")),
                str(p.get("gender", "")), str(p.get("complaint", "")),
                str(p.get("date", ""))
            ]).lower()]
            self._json({"status": "ok", "data": results, "count": len(results)})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/add":
            body = self._read_body()
            name = body.get("name", "").strip()
            if not name:
                self._json({"status": "error", "message": "الاسم مطلوب"}, 400)
                return
            patients = load_patients()
            patient = {
                "id": next_id(patients),
                "name": name,
                "age": body.get("age", "").strip(),
                "gender": body.get("gender", "").strip(),
                "complaint": body.get("complaint", "").strip(),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            patients.append(patient)
            save_patients(patients)
            self._json({"status": "ok", "message": "تم حفظ بيانات المريض", "data": patient})
        elif self.path.startswith("/api/delete/"):
            try:
                pid = int(self.path.split("/api/delete/")[1])
                patients = load_patients()
                new = [p for p in patients if p["id"] != pid]
                if len(new) == len(patients):
                    self._json({"status": "error", "message": "غير موجود"}, 404)
                    return
                save_patients(new)
                self._json({"status": "ok", "message": "تم حذف بيانات المريض"})
            except ValueError:
                self.send_error(400)
        elif self.path.startswith("/api/update/"):
            try:
                pid = int(self.path.split("/api/update/")[1])
                body = self._read_body()
                patients = load_patients()
                found = False
                for p in patients:
                    if p["id"] == pid:
                        p["name"] = body.get("name", p["name"]).strip()
                        p["age"] = body.get("age", p["age"]).strip()
                        p["gender"] = body.get("gender", p["gender"]).strip()
                        p["complaint"] = body.get("complaint", p["complaint"]).strip()
                        found = True
                        break
                if not found:
                    self._json({"status": "error", "message": "غير موجود"}, 404)
                    return
                save_patients(patients)
                self._json({"status": "ok", "message": "تم تحديث البيانات"})
            except ValueError:
                self.send_error(400)
        else:
            self.send_error(404)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def open_browser():
    webbrowser.open(f"http://localhost:{PORT}")


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    threading.Timer(1.0, open_browser).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
