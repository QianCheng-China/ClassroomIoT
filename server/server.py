#!/usr/bin/env python3
"""Classroom IoT - Web 服务器模块（子进程架构，支持可靠停止）"""
import os
import sys
import subprocess
import json
import uuid
import socket
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, jsonify, request, send_file, abort

# ======================== 独立进程入口 ========================
def _serve(port, base_dir):
    """在独立子进程中运行 waitress 服务器。"""
    os.chdir(base_dir)
    if not getattr(sys, "frozen", False):
        sys.path.insert(0, base_dir)
    from config import Config
    from waitress import serve
    cfg = Config(base_dir=base_dir)
    srv = IoTServer(cfg)
    print(f"[服务器子进程] Waitress 启动于端口 {port} (PID {os.getpid()})")
    try:
        serve(srv.app, host="0.0.0.0", port=port, threads=20)
    except Exception as e:
        print(f"[服务器子进程] 异常退出: {e}")
    print("[服务器子进程] 已退出")

# ======================== 服务器类 ========================
class IoTServer:
    def __init__(self, config):
        self.config = config
        self.app = Flask(__name__)
        self._sessions = {}
        self._process = None
        self.RESOURCE_DIR = os.path.join(self.config.base_dir, "resource")
        self._register_routes()

    def _register_routes(self):
        app = self.app
        RESOURCE_DIR = self.RESOURCE_DIR

        def get_local_ip():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(2)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except Exception:
                return "127.0.0.1"

        def require_auth(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                token = request.headers.get("Authorization", "").replace("Bearer ", "")
                if token and token in self._sessions:
                    request.user = self._sessions[token]
                    return f(*args, **kwargs)
                return jsonify({"success": False, "message": "未授权"}), 401
            return decorated

        def parse_describe(folder_path):
            p = os.path.join(folder_path, "describe.txt")
            if not os.path.exists(p): return {}
            result = {}
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line:
                        k, v = line.split("=", 1)
                        result[k.strip()] = v.strip()
            return result

        def parse_index(folder_path):
            p = os.path.join(folder_path, "index.txt")
            if not os.path.exists(p):
                if not os.path.isdir(folder_path): return []
                return sorted(fn for fn in os.listdir(folder_path) if fn.lower().endswith((".png", ".jpg", ".jpeg")))
            with open(p, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]

        def get_course_state(describe, date_str, is_today):
            if not is_today or not describe: return "finished"
            try:
                now = datetime.now()
                start_dt = datetime.strptime(f"{date_str} {describe.get('start', '00:00')}", "%Y-%m-%d %H:%M")
                end_dt = datetime.strptime(f"{date_str} {describe.get('end', '23:59')}", "%Y-%m-%d %H:%M")
                if now < start_dt: return "future"
                elif now > end_dt: return "finished"
                else: return "running"
            except Exception: return "finished"

        @app.route("/", methods=["GET"])
        def index():
            return jsonify({"service": "Classroom IoT Server", "version": "2.0"})

        @app.route("/api/server/info", methods=["GET"])
        def api_server_info():
            return jsonify({
                "name": self.config.alias,
                "version": "1.0",
                "retention_days": self.config.settings["recorder"]["retention_days"],
                "ip": get_local_ip(),
                "port": self.config.http_port,
            })

        @app.route("/api/login", methods=["POST"])
        @app.route("/api/auth/login", methods=["POST"])
        def api_login():
            data = request.get_json(silent=True) or {}
            username = data.get("username", "").strip()
            pw_hash = data.get("password_hash", "")
            if not username or not pw_hash:
                return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400
            users = self.config.load_users()
            stored = users.get(username)
            if stored and stored == pw_hash:
                token = str(uuid.uuid4())
                self._sessions[token] = {"username": username, "login_time": datetime.now().isoformat()}
                return jsonify({"success": True, "token": token, "alias": self.config.alias})
            return jsonify({"success": False, "message": "用户名或密码错误"}), 401

        @app.route("/api/change_password", methods=["POST"])
        def change_password():
            data = request.get_json(silent=True) or {}
            username = data.get("username")
            old_hash = data.get("old_password")
            new_hash = data.get("new_password")
            if not username or not old_hash or not new_hash:
                return jsonify({"success": False, "msg": "信息不完整"}), 400
            users = self.config.load_users()
            if username not in users: return jsonify({"success": False, "msg": "用户不存在"}), 404
            if users[username] != old_hash: return jsonify({"success": False, "msg": "原密码错误"}), 401
            users[username] = new_hash
            try:
                self.config._save_users_dict(users)
                return jsonify({"success": True, "msg": "密码修改成功"})
            except Exception as e:
                return jsonify({"success": False, "msg": f"保存失败: {str(e)}"}), 500

        @app.route("/api/dates", methods=["GET"])
        @require_auth
        def api_dates():
            dates_set = set()
            for sub in ("multimedia", "blackboardL", "blackboardR"):
                base = os.path.join(RESOURCE_DIR, sub)
                if not os.path.isdir(base): continue
                for entry in os.listdir(base):
                    if os.path.isdir(os.path.join(base, entry)):
                        try: datetime.strptime(entry, "%Y-%m-%d")
                        except ValueError: continue
                        dates_set.add(entry)
            rd = int(self.config.settings["recorder"].get("retention_days", 7))
            cutoff = (date.today() - timedelta(days=rd)).strftime("%Y-%m-%d")
            dates = sorted([d for d in dates_set if d >= cutoff], reverse=True)
            return jsonify({"dates": dates})

        @app.route("/api/dates/<date_str>/courses", methods=["GET"])
        @require_auth
        def api_courses(date_str):
            is_today = (date_str == date.today().strftime("%Y-%m-%d"))
            courses = {}
            for sub in ("multimedia", "blackboardL", "blackboardR"):
                day_path = os.path.join(RESOURCE_DIR, sub, date_str)
                if not os.path.isdir(day_path): continue
                for entry in os.listdir(day_path):
                    slot_path = os.path.join(day_path, entry)
                    if not os.path.isdir(slot_path): continue
                    try: idx = int(entry)
                    except ValueError: continue
                    describe = parse_describe(slot_path)
                    if idx not in courses:
                        state = get_course_state(describe, date_str, is_today)
                        courses[idx] = {
                            "index": idx, "name": describe.get("name", f"时间段 {idx}"),
                            "start": describe.get("start", ""), "end": describe.get("end", ""), "state": state,
                            "multimedia": {"count": 0, "size": "0.00"},
                            "blackboardL": {"count": 0, "size": "0.00"},
                            "blackboardR": {"count": 0, "size": "0.00"},
                        }
                    count = len(parse_index(slot_path))
                    size_str = describe.get("size", "0.00")
                    courses[idx][sub] = {"count": count, "size": size_str}
            course_list = sorted(courses.values(), key=lambda x: x["index"])
            return jsonify({"date": date_str, "courses": course_list})

        @app.route("/api/dates/<date_str>/courses/<int:course_idx>/<type_name>/images", methods=["GET"])
        @require_auth
        def api_images(date_str, course_idx, type_name):
            if type_name not in ("multimedia", "blackboardL", "blackboardR"):
                return jsonify({"error": "无效的类型"}), 400
            slot_path = os.path.join(RESOURCE_DIR, type_name, date_str, str(course_idx))
            if not os.path.isdir(slot_path):
                return jsonify({"date": date_str, "course_index": course_idx, "type": type_name, "images": [], "count": 0})
            files = parse_index(slot_path)
            return jsonify({"date": date_str, "course_index": course_idx, "type": type_name, "images": files, "count": len(files)})

        @app.route("/api/dates/<date_str>/courses/<int:course_idx>/<type_name>/count", methods=["GET"])
        @require_auth
        def api_image_count(date_str, course_idx, type_name):
            if type_name not in ("multimedia", "blackboardL", "blackboardR"):
                return jsonify({"error": "无效的类型"}), 400
            slot_path = os.path.join(RESOURCE_DIR, type_name, date_str, str(course_idx))
            count = len(parse_index(slot_path)) if os.path.isdir(slot_path) else 0
            return jsonify({"count": count})

        @app.route("/resource/<path:filepath>", methods=["GET"])
        @require_auth
        def serve_resource(filepath):
            full = os.path.realpath(os.path.join(RESOURCE_DIR, filepath))
            base = os.path.realpath(RESOURCE_DIR)
            if not full.startswith(base): abort(403)
            if not os.path.isfile(full): abort(404)
            return send_file(full)

        @app.route("/images/<path:filepath>", methods=["GET"])
        @require_auth
        def serve_image(filepath):
            return serve_resource(filepath)

    # ======================== 服务器启停 ========================
    def start(self):
        if self.is_running(): print("[服务器] 已在运行中"); return
        port = self.config.http_port
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
            cmd = [sys.executable, "--_serve_http_only", str(port)]
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            cmd = [sys.executable, os.path.abspath(__file__), "--_serve_http_only", str(port)]
        popen_kwargs = {"cwd": base_dir, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        self._process = subprocess.Popen(cmd, **popen_kwargs)
        print(f"[服务器] 子进程已启动 (PID: {self._process.pid}, 端口: {port})")

    def stop(self):
        if self._process is None: return
        pid = self._process.pid
        try:
            self._process.terminate()
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=3)
        except Exception as e:
            print(f"[服务器] 停止异常: {e}")
        self._process = None
        print(f"[服务器] 子进程 (PID: {pid}) 已终止")

    def is_running(self):
        if self._process is None or self._process.poll() is not None: return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(("127.0.0.1", self.config.http_port))
            s.close()
            return result == 0
        except Exception: return False

if __name__ == "__main__":
    if "--_serve_http_only" in sys.argv:
        idx = sys.argv.index("--_serve_http_only")
        port = int(sys.argv[idx + 1])
        base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        _serve(port, base_dir)
