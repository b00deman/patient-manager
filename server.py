# -*- coding: utf-8 -*-
"""
Patient Data Manager - Server
يسجل بيانات المرضى ويحفظها محلياً ويمكن البحث فيها
"""
import json
import os
import sys
import threading
import urllib.request
import urllib.parse
import re
from http.server import HTTPServer, BaseHTTPRequestHandler

# مسار ملف البيانات - بيتحفظ جنب البرنامج
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patients.json")
HTML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

PORT = 17755


def load_patients():
    """تحميل بيانات المرضى من الملف"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_patients(patients):
    """حفظ بيانات المرضى في الملف"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(patients, f, ensure_ascii=False, indent=2)


def next_id(patients):
    """توليد ID جديد"""
    if not patients:
        return 1
    return max(p["id"] for p in patients) + 1


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # إخفاء سجلات المخدم

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.serve_html()
        elif self.path == "/api/patients":
            self.serve_patients()
        elif self.path.startswith("/api/search?q="):
            query = urllib.parse.unquote(self.path.split("/api/search?q=")[1])
            self.serve_search(query)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/add":
            self.handle_add()
        elif self.path.startswith("/api/delete/"):
            try:
                pid = int(self.path.split("/api/delete/")[1])
                self.handle_delete(pid)
            except ValueError:
                self.send_error(400)
        elif self.path.startswith("/api/update/"):
            try:
                pid = int(self.path.split("/api/update/")[1])
                self.handle_update(pid)
            except ValueError:
                self.send_error(400)
        else:
            self.send_error(404)

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_html(self):
        try:
            with open(HTML_FILE, "r", encoding="utf-8") as f:
                content = f.read().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, "index.html not found")

    def serve_patients(self):
        patients = load_patients()
        self.send_json({"status": "ok", "data": patients, "count": len(patients)})

    def serve_search(self, query):
        patients = load_patients()
        q = query.lower().strip()
        if not q:
            self.send_json({"status": "ok", "data": patients, "count": len(patients)})
            return
        results = []
        for p in patients:
            haystack = " ".join([
                str(p.get("name", "")),
                str(p.get("age", "")),
                str(p.get("gender", "")),
                str(p.get("complaint", "")),
                str(p.get("date", "")),
            ]).lower()
            if q in haystack:
                results.append(p)
        self.send_json({"status": "ok", "data": results, "count": len(results)})

    def handle_add(self):
        try:
            body = self.read_body()
            name = body.get("name", "").strip()
            age = body.get("age", "").strip()
            gender = body.get("gender", "").strip()
            complaint = body.get("complaint", "").strip()

            if not name:
                self.send_json({"status": "error", "message": "الاسم مطلوب"}, 400)
                return

            patients = load_patients()
            from datetime import datetime
            patient = {
                "id": next_id(patients),
                "name": name,
                "age": age,
                "gender": gender,
                "complaint": complaint,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            patients.append(patient)
            save_patients(patients)
            self.send_json({"status": "ok", "message": "تم حفظ بيانات المريض", "data": patient})
        except Exception as e:
            self.send_json({"status": "error", "message": str(e)}, 500)

    def handle_delete(self, pid):
        patients = load_patients()
        new_list = [p for p in patients if p["id"] != pid]
        if len(new_list) == len(patients):
            self.send_json({"status": "error", "message": "المريض غير موجود"}, 404)
            return
        save_patients(new_list)
        self.send_json({"status": "ok", "message": "تم حذف بيانات المريض"})

    def handle_update(self, pid):
        try:
            body = self.read_body()
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
                self.send_json({"status": "error", "message": "المريض غير موجود"}, 404)
                return
            save_patients(patients)
            self.send_json({"status": "ok", "message": "تم تحديث بيانات المريض"})
        except Exception as e:
            self.send_json({"status": "error", "message": str(e)}, 500)


def open_browser():
    """فتح المتصفح تلقائياً بعد تشغيل المخدم"""
    import subprocess
    url = f"http://localhost:{PORT}"
    subprocess.Popen(["cmd", "/c", "start", url], shell=False)


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Server running on http://localhost:{PORT}")
    print(f"Data file: {DATA_FILE}")
    threading.Timer(1.0, open_browser).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
