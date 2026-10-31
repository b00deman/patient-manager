# -*- coding: utf-8 -*-
"""
مستشفى الخيري - نظام تسجيل بيانات المرضى
Patient Data Manager with login & role-based permissions
"""
import json
import os
import sys
import hashlib
import hmac
import secrets
import threading
import webbrowser
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime

PORT = 17755

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(APP_DIR, "patients.json")
USERS_FILE = os.path.join(APP_DIR, "users.json")

# الجلسات: token -> username
SESSIONS = {}

DEFAULT_ADMIN_USER = "badawi"
DEFAULT_ADMIN_PASS = "Badawi@2026"

PERMS = ["view", "add", "edit", "delete", "print"]


# ---------------------------- كلمات المرور ----------------------------

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


# ---------------------------- المستخدمون ----------------------------

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def find_user(username):
    for u in load_users():
        if u["username"].lower() == str(username).lower():
            return u
    return None


def ensure_admin():
    """إنشاء حساب المدير الافتراضي أول مرة فقط"""
    users = load_users()
    if not users:
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


# ---------------------------- المرضى ----------------------------

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


HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>مستشفى الخيري</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Tahoma,Arial,sans-serif;background:#0f1923;color:#e0e6ed;min-height:100vh;padding:20px}
.container{max-width:980px;margin:0 auto}
header{text-align:center;padding:22px 0 18px;border-bottom:1px solid #1e2d3a;margin-bottom:22px}
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
.btn-row{display:flex;gap:12px;margin-top:18px;flex-wrap:wrap}
.btn{padding:11px 28px;border:none;border-radius:8px;font-size:15px;font-family:inherit;cursor:pointer;transition:all .2s;font-weight:600}
.btn-primary{background:#4fc3f7;color:#0f1923}
.btn-primary:hover{background:#29b6f6}
.btn-secondary{background:#263238;color:#90a4ae;border:1px solid #37474f}
.btn-secondary:hover{background:#37474f;color:#e0e6ed}
.btn-danger{background:#ef5350;color:#fff;padding:6px 14px;font-size:13px;border-radius:6px;border:none;cursor:pointer;font-family:inherit;font-weight:600}
.btn-danger:hover{background:#e53935}
.btn-edit{background:#ffa726;color:#0f1923;padding:6px 14px;font-size:13px;border-radius:6px;border:none;cursor:pointer;font-family:inherit;font-weight:600}
.btn-edit:hover{background:#fb8c00}
.btn-print{background:#66bb6a;color:#fff;padding:6px 14px;font-size:13px;border-radius:6px;border:none;cursor:pointer;font-family:inherit;font-weight:600}
.btn-print:hover{background:#43a047}
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
.toast{position:fixed;top:20px;right:50%;transform:translateX(50%);background:#2e7d32;color:#fff;padding:12px 24px;border-radius:8px;font-size:15px;z-index:9999;display:none;box-shadow:0 4px 20px rgba(0,0,0,.4)}
.toast.error{background:#c62828}
.toast.show{display:block;animation:fadeIn .3s}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.modal-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.7);z-index:1000;justify-content:center;align-items:center;padding:20px;overflow:auto}
.modal-overlay.show{display:flex}
.modal{background:#162029;border:1px solid #2a3b4a;border-radius:12px;padding:26px;width:100%;max-width:560px;max-height:90vh;overflow:auto}
.modal h2{color:#4fc3f7;margin-bottom:18px;font-size:19px}
.modal .form-grid{grid-template-columns:1fr 1fr}
.modal .btn-row{justify-content:flex-end}
#printArea{background:#fff;color:#000;padding:24px;border-radius:8px;margin-bottom:16px}
#printArea .ph-title{font-size:26px;font-weight:bold;text-align:center;margin-bottom:6px;color:#000}
#printArea .ph-sub{text-align:center;font-size:14px;color:#333;margin-bottom:20px;border-bottom:2px solid #000;padding-bottom:12px}
#printArea .ph-patient table{width:100%;border-collapse:collapse}
#printArea .ph-patient th,#printArea .ph-patient td{padding:10px 14px;text-align:right;border:1px solid #999;font-size:15px;color:#000}
#printArea .ph-patient th{background:#eee;font-weight:600;width:30%}
@media print{html,body{background:#fff!important}body *{visibility:hidden}.modal-overlay{background:transparent!important}#printArea,#printArea *{visibility:visible}#printArea{position:absolute!important;left:0;top:0;width:100%;padding:20px;margin:0;border-radius:0;box-shadow:none}}

/* ---------- شاشة الدخول ---------- */
#loginView{display:none;min-height:80vh;align-items:center;justify-content:center}
#loginView.show{display:flex}
.login-card{background:#162029;border:1px solid #1e2d3a;border-radius:16px;padding:36px 32px;width:100%;max-width:390px;box-shadow:0 20px 60px rgba(0,0,0,.45)}
.login-logo{text-align:center;font-size:26px;font-weight:700;color:#4fc3f7;margin-bottom:6px}
.login-sub{text-align:center;color:#78909c;font-size:13px;margin-bottom:26px}
.login-field{margin-bottom:16px}
.login-field label{display:block;font-size:13px;color:#90a4ae;margin-bottom:6px}
.login-field input{width:100%;background:#0f1923;border:1px solid #2a3b4a;border-radius:8px;padding:12px 14px;color:#e0e6ed;font-size:15px;font-family:inherit;outline:none}
.login-field input:focus{border-color:#4fc3f7}
.login-btn{width:100%;background:#4fc3f7;color:#0f1923;border:none;border-radius:8px;padding:13px;font-size:16px;font-weight:700;font-family:inherit;cursor:pointer;margin-top:8px}
.login-btn:hover{background:#29b6f6}
.login-btn:disabled{opacity:.6;cursor:wait}
.login-error{color:#ef5350;font-size:13px;text-align:center;min-height:18px;margin-top:12px}
.login-hint{color:#546e7a;font-size:12px;text-align:center;margin-top:18px;line-height:1.7}

/* ---------- الشريط العلوي ---------- */
.topbar{display:flex;justify-content:space-between;align-items:center;gap:12px;background:#162029;border:1px solid #1e2d3a;border-radius:10px;padding:10px 16px;margin-bottom:18px;flex-wrap:wrap}
.topbar-user{display:flex;align-items:center;gap:8px;font-size:14px;color:#b0bec5}
.role-badge{font-size:11px;padding:3px 9px;border-radius:20px;font-weight:700}
.role-admin{background:#4fc3f7;color:#0f1923}
.role-user{background:#37474f;color:#cfd8dc}
.topbar-actions{display:flex;gap:8px;flex-wrap:wrap}
.btn-mini{background:#263238;color:#b0bec5;border:1px solid #37474f;border-radius:7px;padding:7px 14px;font-size:13px;font-family:inherit;cursor:pointer;font-weight:600}
.btn-mini:hover{background:#37474f;color:#e0e6ed}
.btn-logout{background:#3e2723;color:#ff8a80;border-color:#5d4037}
.btn-logout:hover{background:#4e342e;color:#ffab91}
#appView{display:none}
#appView.show{display:block}

/* ---------- إدارة المستخدمين ---------- */
.user-row{border:1px solid #1e2d3a;border-radius:10px;padding:14px;margin-bottom:12px;background:#0f1923}
.user-row-head{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.user-name{font-weight:700;color:#e0e6ed;font-size:15px}
.user-meta{font-size:12px;color:#78909c;margin-top:3px}
.perm-list{display:flex;flex-wrap:wrap;gap:14px}
.perm-item{display:flex;align-items:center;gap:6px;font-size:13px;color:#b0bec5;cursor:pointer;user-select:none}
.perm-item input{width:16px;height:16px;accent-color:#4fc3f7;cursor:pointer}
.perm-item input:disabled{opacity:.45;cursor:not-allowed}
.section-title{font-size:14px;color:#4fc3f7;font-weight:700;margin:22px 0 12px;padding-top:18px;border-top:1px solid #1e2d3a}
</style>
</head>
<body>

<!-- ================= شاشة تسجيل الدخول ================= -->
<div id="loginView">
  <div class="login-card">
    <div class="login-logo">مستشفى الخيري</div>
    <p class="login-sub">نظام تسجيل بيانات المرضى</p>
    <div class="login-field">
      <label>اسم المستخدم</label>
      <input type="text" id="loginUser" autocomplete="username" placeholder="اسم المستخدم">
    </div>
    <div class="login-field">
      <label>كلمة المرور</label>
      <input type="password" id="loginPass" autocomplete="current-password" placeholder="كلمة المرور">
    </div>
    <button class="login-btn" id="loginBtn" onclick="doLogin()">دخول</button>
    <div class="login-error" id="loginError"></div>
    <div class="login-hint">الدخول متاح للمستخدمين المصرح لهم فقط</div>
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
    </div>
    <div class="topbar-actions">
      <button class="btn-mini" id="btnUsers" onclick="openUsers()" style="display:none">إدارة المستخدمين</button>
      <button class="btn-mini btn-logout" onclick="doLogout()">تسجيل الخروج</button>
    </div>
  </div>

  <header><h1>مستشفى الخيري</h1><p>أدخل بيانات المريض وسيتم حفظها تلقائياً — يمكنك البحث والرجوع لها في أي وقت</p></header>

  <div class="card" id="addCard"><h2>تسجيل مريض جديد</h2>
    <div class="form-grid">
      <div class="form-group"><label>الاسم *</label><input type="text" id="name" placeholder="اسم المريض"></div>
      <div class="form-group"><label>العمر</label><input type="number" id="age" placeholder="العمر بالسنوات" min="0" max="150"></div>
      <div class="form-group"><label>الجنس</label><select id="gender"><option value="">-- اختر --</option><option value="ذكر">ذكر</option><option value="أنثى">أنثى</option></select></div>
      <div class="form-group full"><label>الشكوى</label><textarea id="complaint" placeholder="اكتب الشكوى / الأعراض"></textarea></div>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" onclick="addPatient()">تسجيل</button>
      <button class="btn btn-print" onclick="printForm()">طباعة</button>
      <button class="btn btn-secondary" onclick="clearForm()">مسح الحقول</button>
    </div>
  </div>

  <div class="card"><h2>المرضى المسجلين</h2>
    <div class="search-bar"><input type="text" id="searchInput" placeholder="ابحث بالاسم أو العمر أو الجنس أو الشكوى..." oninput="searchPatients()"></div>
    <div class="stats" id="stats">جاري التحميل...</div>
    <table><thead><tr><th>#</th><th>الاسم</th><th>العمر</th><th>الجنس</th><th>الشكوى</th><th>التاريخ</th><th>إجراءات</th></tr></thead><tbody id="patientTable"></tbody></table>
    <div class="empty-msg" id="emptyMsg" style="display:none">لا توجد بيانات مسجلة بعد</div>
  </div>

</div>
</div>

<!-- نافذة تعديل المريض -->
<div class="modal-overlay" id="editModal"><div class="modal"><h2>تعديل بيانات المريض</h2>
  <div class="form-grid">
    <div class="form-group"><label>الاسم</label><input type="text" id="editName"></div>
    <div class="form-group"><label>العمر</label><input type="number" id="editAge" min="0" max="150"></div>
    <div class="form-group full"><label>الجنس</label><select id="editGender"><option value="">-- اختر --</option><option value="ذكر">ذكر</option><option value="أنثى">أنثى</option></select></div>
    <div class="form-group full"><label>الشكوى</label><textarea id="editComplaint"></textarea></div>
  </div>
  <div class="btn-row"><button class="btn btn-primary" onclick="saveEdit()">حفظ التعديل</button><button class="btn btn-secondary" onclick="closeModal()">إلغاء</button></div>
</div></div>

<!-- معاينة الطباعة -->
<div class="modal-overlay" id="printModal"><div class="modal" style="max-width:600px"><h2>معاينة الطباعة</h2><div id="printArea"></div><div class="btn-row" style="justify-content:center"><button class="btn btn-primary" onclick="doPrint()">طباعة الآن</button><button class="btn btn-secondary" onclick="closePrint()">إغلاق</button></div></div></div>

<!-- إدارة المستخدمين -->
<div class="modal-overlay" id="usersModal"><div class="modal" style="max-width:640px"><h2>إدارة المستخدمين</h2>
  <div id="usersList"></div>

  <div class="section-title">إضافة مستخدم جديد</div>
  <div class="form-grid">
    <div class="form-group"><label>اسم المستخدم</label><input type="text" id="newUsername" placeholder="مثال: ahmed" autocomplete="off"></div>
    <div class="form-group"><label>الاسم الظاهر</label><input type="text" id="newDisplayName" placeholder="مثال: أحمد" autocomplete="off"></div>
    <div class="form-group full"><label>كلمة المرور</label><input type="password" id="newPassword" placeholder="6 أحرف على الأقل" autocomplete="new-password"></div>
  </div>
  <div style="margin-top:14px">
    <label style="font-size:13px;color:#90a4ae;display:block;margin-bottom:8px">الصلاحيات</label>
    <div class="perm-list" id="newPerms">
      <label class="perm-item"><input type="checkbox" data-perm="view" checked> عرض</label>
      <label class="perm-item"><input type="checkbox" data-perm="add"> تسجيل</label>
      <label class="perm-item"><input type="checkbox" data-perm="edit"> تعديل</label>
      <label class="perm-item"><input type="checkbox" data-perm="delete"> حذف</label>
      <label class="perm-item"><input type="checkbox" data-perm="print"> طباعة</label>
    </div>
  </div>
  <div class="btn-row">
    <button class="btn btn-primary" onclick="addUser()">إضافة المستخدم</button>
    <button class="btn btn-secondary" onclick="closeUsers()">إغلاق</button>
  </div>
</div></div>

<div class="toast" id="toast"></div>

<script>
let ME=null, allPatients=[], editingId=null, USERS=[];

const PERMS=["view","add","edit","delete","print"];
const PERM_LABELS={view:"عرض",add:"تسجيل",edit:"تعديل",delete:"حذف",print:"طباعة"};

function can(p){ return !!(ME && ME.perms && ME.perms[p]); }
function isAdmin(){ return !!(ME && ME.role==="admin"); }

/* ---------- أدوات ---------- */
function esc(s){if(s===null||s===undefined)return'';return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function showToast(m,e){const t=document.getElementById('toast');t.textContent=m;t.className='toast show'+(e?' error':'');setTimeout(()=>{t.className='toast'},3200)}
async function api(url,opts){
  opts=opts||{};
  const r=await fetch(url,opts);
  if(r.status===401){ showLogin(); throw new Error('unauth'); }
  let j={};
  try{ j=await r.json(); }catch(e){ j={status:'error',message:'خطأ في الاستجابة'}; }
  j._code=r.status;
  return j;
}

/* ---------- الدخول ---------- */
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
  if(!u||!p){ err.textContent='أدخل اسم المستخدم وكلمة المرور'; return; }
  btn.disabled=true; btn.textContent='جارٍ الدخول...';
  try{
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
    const j=await r.json();
    if(j.status==='ok'){
      ME=j.user;
      applyPermissions();
      showApp();
      loadPatients();
    }else{
      err.textContent=j.message||'بيانات الدخول غير صحيحة';
    }
  }catch(e){
    err.textContent='تعذّر الاتصال بالبرنامج';
  }finally{
    btn.disabled=false; btn.textContent='دخول';
  }
}

async function doLogout(){
  try{ await fetch('/api/logout',{method:'POST'}); }catch(e){}
  showLogin();
}

/* ---------- الصلاحيات على الواجهة ---------- */
function applyPermissions(){
  if(!ME) return;
  document.getElementById('topUserName').textContent=ME.name||ME.username;
  const badge=document.getElementById('topUserRole');
  if(isAdmin()){ badge.textContent='مدير'; badge.className='role-badge role-admin'; }
  else{ badge.textContent='مستخدم'; badge.className='role-badge role-user'; }
  document.getElementById('btnUsers').style.display=isAdmin()?'inline-block':'none';
  document.getElementById('addCard').style.display=can('add')?'block':'none';
}

/* ---------- المرضى ---------- */
async function loadPatients(){
  try{
    const j=await api('/api/patients');
    allPatients=j.data||[];
    renderTable(allPatients);
  }catch(e){}
}

async function addPatient(){
  const n=document.getElementById('name').value.trim();
  const a=document.getElementById('age').value.trim();
  const g=document.getElementById('gender').value;
  const c=document.getElementById('complaint').value.trim();
  if(!n){ showToast('الاسم مطلوب',true); return; }
  try{
    const j=await api('/api/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n,age:a,gender:g,complaint:c})});
    if(j.status==='ok'){ showToast('تم حفظ بيانات المريض'); clearForm(); loadPatients(); }
    else showToast(j.message||'خطأ',true);
  }catch(e){}
}

async function searchPatients(){
  const q=document.getElementById('searchInput').value.trim();
  if(!q){ loadPatients(); return; }
  try{
    const j=await api('/api/search?q='+encodeURIComponent(q));
    renderTable(j.data||[]);
  }catch(e){}
}

function renderTable(p){
  const tb=document.getElementById('patientTable');
  const st=document.getElementById('stats');
  const em=document.getElementById('emptyMsg');
  if(!p||!p.length){
    tb.innerHTML=''; st.textContent='لا يوجد مرضى مسجلين'; em.style.display='block'; return;
  }
  em.style.display='none';
  st.textContent='عدد المرضى: '+p.length;
  tb.innerHTML=p.map(x=>{
    let acts='';
    if(can('edit')) acts+='<button class="btn-edit" onclick="openEdit('+x.id+')">تعديل</button> ';
    if(can('delete')) acts+='<button class="btn-danger" onclick="del('+x.id+')">حذف</button> ';
    if(can('print')) acts+='<button class="btn-print" onclick="printPatient('+x.id+')">طباعة</button>';
    if(!acts) acts='<span style="color:#546e7a;font-size:12px">عرض فقط</span>';
    return '<tr><td>'+x.id+'</td><td>'+esc(x.name)+'</td><td>'+esc(x.age)+'</td><td>'+esc(x.gender)+'</td><td>'+esc(x.complaint)+'</td><td style="font-size:12px;color:#78909c">'+esc(x.date)+'</td><td>'+acts+'</td></tr>';
  }).join('');
}

async function del(id){
  if(!confirm('هل أنت متأكد من حذف بيانات هذا المريض؟')) return;
  try{
    const j=await api('/api/delete/'+id,{method:'POST'});
    if(j.status==='ok'){ showToast('تم حذف بيانات المريض'); loadPatients(); }
    else showToast(j.message||'خطأ',true);
  }catch(e){}
}

function openEdit(id){
  const p=allPatients.find(x=>x.id===id);
  if(!p) return;
  editingId=id;
  document.getElementById('editName').value=p.name;
  document.getElementById('editAge').value=p.age;
  document.getElementById('editGender').value=p.gender;
  document.getElementById('editComplaint').value=p.complaint;
  document.getElementById('editModal').classList.add('show');
}

async function saveEdit(){
  if(editingId===null) return;
  const n=document.getElementById('editName').value.trim();
  if(!n){ showToast('الاسم مطلوب',true); return; }
  try{
    const j=await api('/api/update/'+editingId,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      name:n,
      age:document.getElementById('editAge').value.trim(),
      gender:document.getElementById('editGender').value,
      complaint:document.getElementById('editComplaint').value.trim()
    })});
    if(j.status==='ok'){ showToast('تم تحديث البيانات'); closeModal(); loadPatients(); }
    else showToast(j.message||'خطأ',true);
  }catch(e){}
}

function closeModal(){ document.getElementById('editModal').classList.remove('show'); editingId=null; }

function clearForm(){
  document.getElementById('name').value='';
  document.getElementById('age').value='';
  document.getElementById('gender').value='';
  document.getElementById('complaint').value='';
}

/* ---------- الطباعة ---------- */
function buildPrintCard(p){
  document.getElementById('printArea').innerHTML=
    '<div class="ph-title">مستشفى الخيري</div><div class="ph-sub">بيانات المريض</div>'+
    '<div class="ph-patient"><table>'+
    '<tr><th>الاسم</th><td>'+esc(p.name)+'</td></tr>'+
    '<tr><th>العمر</th><td>'+esc(p.age)+'</td></tr>'+
    '<tr><th>الجنس</th><td>'+esc(p.gender)+'</td></tr>'+
    '<tr><th>الشكوى</th><td>'+esc(p.complaint)+'</td></tr>'+
    '<tr><th>التاريخ</th><td>'+esc(p.date)+'</td></tr>'+
    '</table></div>';
}
function printPatient(id){
  const p=allPatients.find(x=>x.id===id);
  if(!p) return;
  buildPrintCard(p);
  document.getElementById('printModal').classList.add('show');
}
function printForm(){
  const n=document.getElementById('name').value.trim();
  if(!n){ showToast('اكتب الاسم أولاً للطباعة',true); return; }
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
function doPrint(){ window.print(); }
function closePrint(){ document.getElementById('printModal').classList.remove('show'); }

/* ---------- إدارة المستخدمين ---------- */
async function openUsers(){
  if(!isAdmin()) return;
  document.getElementById('usersModal').classList.add('show');
  await loadUsers();
}

function closeUsers(){ document.getElementById('usersModal').classList.remove('show'); }

async function loadUsers(){
  try{
    const j=await api('/api/users');
    USERS=j.data||[];
    renderUsers();
  }catch(e){}
}

function renderUsers(){
  const box=document.getElementById('usersList');
  if(!USERS.length){ box.innerHTML='<div class="empty-msg">لا يوجد مستخدمون</div>'; return; }
  box.innerHTML=USERS.map(u=>{
    const perms=PERMS.map(p=>{
      const checked=u.perms&&u.perms[p]?'checked':'';
      const dis=(u.role==='admin')?'disabled':'';
      return '<label class="perm-item"><input type="checkbox" data-u="'+esc(u.username)+'" data-p="'+p+'" '+checked+' '+dis+' onchange="togglePerm(this)"> '+PERM_LABELS[p]+'</label>';
    }).join('');
    const isSelf=u.username===ME.username;
    return '<div class="user-row">'+
      '<div class="user-row-head">'+
        '<div><div class="user-name">'+esc(u.name)+' '+(u.role==='admin'?'<span class="role-badge role-admin" style="margin-inline-start:6px">مدير</span>':'')+'</div>'+
        '<div class="user-meta">@'+esc(u.username)+' · أُنشئ '+esc(u.created||'-')+'</div></div>'+
        '<div>'+(isSelf?'<span class="user-meta">(أنت)</span>':'<button class="btn-danger" onclick="deleteUser(&quot;'+esc(u.username)+'&quot;)">حذف</button>')+'</div>'+
      '</div>'+
      '<div class="perm-list">'+perms+'</div>'+
      '</div>';
  }).join('');
}

async function togglePerm(cb){
  const username=cb.getAttribute('data-u');
  const perms={};
  document.querySelectorAll('#usersList input[data-u="'+username+'"]').forEach(x=>{
    perms[x.getAttribute('data-p')]=x.checked;
  });
  try{
    const j=await api('/api/users/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username,perms:perms})});
    if(j.status==='ok'){ showToast('تم تحديث صلاحيات '+username); await loadUsers(); }
    else showToast(j.message||'خطأ',true);
  }catch(e){}
}

async function addUser(){
  const username=document.getElementById('newUsername').value.trim();
  const name=document.getElementById('newDisplayName').value.trim();
  const password=document.getElementById('newPassword').value;
  if(!username){ showToast('اسم المستخدم مطلوب',true); return; }
  if(password.length<6){ showToast('كلمة المرور 6 أحرف على الأقل',true); return; }
  const perms={};
  document.querySelectorAll('#newPerms input[data-perm]').forEach(x=>{ perms[x.getAttribute('data-perm')]=x.checked; });
  try{
    const j=await api('/api/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username,name:name||username,password:password,perms:perms})});
    if(j.status==='ok'){
      showToast('تمت إضافة المستخدم '+username);
      document.getElementById('newUsername').value='';
      document.getElementById('newDisplayName').value='';
      document.getElementById('newPassword').value='';
      document.querySelectorAll('#newPerms input[data-perm]').forEach(x=>{ x.checked=(x.getAttribute('data-perm')==='view'); });
      await loadUsers();
    }else showToast(j.message||'خطأ',true);
  }catch(e){}
}

async function deleteUser(username){
  if(!confirm('حذف المستخدم "'+username+'" نهائياً؟')) return;
  try{
    const j=await api('/api/users/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username})});
    if(j.status==='ok'){ showToast('تم حذف المستخدم'); await loadUsers(); }
    else showToast(j.message||'خطأ',true);
  }catch(e){}
}

/* ---------- بدء التشغيل ---------- */
async function boot(){
  try{
    const r=await fetch('/api/me');
    if(r.status===200){
      const j=await r.json();
      ME=j.user;
      applyPermissions();
      showApp();
      loadPatients();
      return;
    }
  }catch(e){}
  showLogin();
}

document.addEventListener('DOMContentLoaded',()=>{
  document.getElementById('loginPass').addEventListener('keydown',e=>{ if(e.key==='Enter') doLogin(); });
  document.getElementById('loginUser').addEventListener('keydown',e=>{ if(e.key==='Enter') document.getElementById('loginPass').focus(); });
  boot();
});
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
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
            self._json({"status": "error", "message": "يجب تسجيل الدخول"}, 401)
            return None
        if admin and user.get("role") != "admin":
            self._json({"status": "error", "message": "هذه العملية للمدير فقط"}, 403)
            return None
        if perm and not user.get("perms", {}).get(perm):
            self._json({"status": "error", "message": "لا تملك صلاحية لهذه العملية"}, 403)
            return None
        return user

    # ---------- GET ----------
    def do_GET(self):
        from urllib.parse import unquote

        if self.path in ("/", "/index.html"):
            body = HTML_CONTENT.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/api/me":
            user = self.current_user()
            if not user:
                self._json({"status": "error", "message": "غير مسجل"}, 401)
                return
            self._json({"status": "ok", "user": public_user(user)})
            return

        if self.path == "/api/patients":
            if not self.guard(perm="view"):
                return
            patients = load_patients()
            self._json({"status": "ok", "data": patients, "count": len(patients)})
            return

        if self.path.startswith("/api/search?q="):
            if not self.guard(perm="view"):
                return
            q = unquote(self.path.split("/api/search?q=")[1]).lower().strip()
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

        if self.path == "/api/users":
            if not self.guard(admin=True):
                return
            self._json({"status": "ok", "data": [public_user(u) for u in load_users()]})
            return

        self.send_error(404)

    # ---------- POST ----------
    def do_POST(self):
        if self.path == "/api/login":
            self.handle_login()
            return

        if self.path == "/api/logout":
            token = self._session_token()
            if token:
                SESSIONS.pop(token, None)
            self._json({"status": "ok"}, 200, [("Set-Cookie", "session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")])
            return

        if self.path == "/api/add":
            if not self.guard(perm="add"):
                return
            body = self._read_body()
            name = str(body.get("name", "")).strip()
            if not name:
                self._json({"status": "error", "message": "الاسم مطلوب"}, 400)
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
            self._json({"status": "ok", "message": "تم حفظ بيانات المريض", "data": patient})
            return

        if self.path.startswith("/api/delete/"):
            if not self.guard(perm="delete"):
                return
            try:
                pid = int(self.path.split("/api/delete/")[1])
            except ValueError:
                self.send_error(400)
                return
            patients = load_patients()
            new_list = [p for p in patients if p["id"] != pid]
            if len(new_list) == len(patients):
                self._json({"status": "error", "message": "غير موجود"}, 404)
                return
            save_patients(new_list)
            self._json({"status": "ok", "message": "تم حذف بيانات المريض"})
            return

        if self.path.startswith("/api/update/"):
            if not self.guard(perm="edit"):
                return
            try:
                pid = int(self.path.split("/api/update/")[1])
            except ValueError:
                self.send_error(400)
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
                self._json({"status": "error", "message": "غير موجود"}, 404)
                return
            save_patients(patients)
            self._json({"status": "ok", "message": "تم تحديث البيانات"})
            return

        if self.path == "/api/users":
            if not self.guard(admin=True):
                return
            body = self._read_body()
            username = str(body.get("username", "")).strip()
            password = str(body.get("password", ""))
            name = str(body.get("name", "")).strip() or username
            perms_in = body.get("perms", {}) or {}

            if not username:
                self._json({"status": "error", "message": "اسم المستخدم مطلوب"}, 400)
                return
            if len(password) < 6:
                self._json({"status": "error", "message": "كلمة المرور 6 أحرف على الأقل"}, 400)
                return
            if find_user(username):
                self._json({"status": "error", "message": "اسم المستخدم موجود بالفعل"}, 400)
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

        if self.path == "/api/users/update":
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
                self._json({"status": "error", "message": "المستخدم غير موجود"}, 404)
                return
            if target.get("role") == "admin":
                self._json({"status": "error", "message": "لا يمكن تعديل صلاحيات المدير"}, 403)
                return

            if "perms" in body and isinstance(body["perms"], dict):
                target["perms"] = {p: bool(body["perms"].get(p)) for p in PERMS}
            if "password" in body and str(body["password"]):
                pw = str(body["password"])
                if len(pw) < 6:
                    self._json({"status": "error", "message": "كلمة المرور 6 أحرف على الأقل"}, 400)
                    return
                target["password"] = hash_password(pw)
            if "active" in body:
                target["active"] = bool(body["active"])
            if "name" in body and str(body["name"]).strip():
                target["name"] = str(body["name"]).strip()

            save_users(users)
            self._json({"status": "ok", "message": "تم التحديث"})
            return

        if self.path == "/api/users/delete":
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
                self._json({"status": "error", "message": "المستخدم غير موجود"}, 404)
                return
            if target.get("role") == "admin":
                self._json({"status": "error", "message": "لا يمكن حذف حساب المدير"}, 403)
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
            self._json({"status": "error", "message": "أدخل اسم المستخدم وكلمة المرور"}, 400)
            return

        user = find_user(username)
        if not user or not verify_password(password, user.get("password", "")):
            self._json({"status": "error", "message": "اسم المستخدم أو كلمة المرور غير صحيحة"}, 401)
            return
        if not user.get("active", True):
            self._json({"status": "error", "message": "هذا الحساب موقوف — راجع المدير"}, 403)
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
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    threading.Timer(1.0, open_browser).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
