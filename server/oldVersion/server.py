#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classroom IoT Server v1.1
已修复：与 Android App 端 ApiClient.kt 完全对齐的所有接口兼容问题。
"""

import os
import json
import hashlib
import uuid
import socket
import threading
import time
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, jsonify, request, send_file, abort

# ======================== 可配置项 ========================
SERVER_ALIAS = "Classroom IoT"
HTTP_PORT = 8080
DISCOVERY_PORT = 48899
RESOURCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resource")
USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "users.json")
RETENTION_DAYS = 7

app = Flask(__name__)

# 内存会话
_sessions = {}

# ======================== 工具函数 ========================

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

def load_users():
    if not os.path.exists(USERS_FILE):
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        default = {"admin": hashlib.sha256("admin".encode("utf-8")).hexdigest()}
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2, ensure_ascii=False)
        print("[用户] 已创建默认管理员 admin / admin")
        return default
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def require_auth(f):
    """认证装饰器 —— 但为兼容当前 App，改为可选认证（有 token 就验证，没有也放行）"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token and token in _sessions:
            request.user = _sessions[token]
        # 不管有没有 token 都放行（教室局域网环境）
        return f(*args, **kwargs)
    return decorated

def parse_describe(folder_path):
    p = os.path.join(folder_path, "describe.txt")
    if not os.path.exists(p):
        return {}
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
        # 回退：直接扫描目录中的图片文件
        if not os.path.isdir(folder_path):
            return []
        images = []
        for fn in os.listdir(folder_path):
            if fn.lower().endswith((".png", ".jpg", ".jpeg")):
                images.append(fn)
        return sorted(images)
    with open(p, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def get_course_state(describe, date_str, is_today):
    if not is_today or not describe:
        return "finished"
    try:
        start_str = describe.get("start", "00:00")
        end_str = describe.get("end", "23:59")
        now = datetime.now()
        start_dt = datetime.strptime(f"{date_str} {start_str}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{date_str} {end_str}", "%Y-%m-%d %H:%M")
        if now < start_dt:
            return "future"
        elif now > end_dt:
            return "finished"
        else:
            return "running"
    except Exception:
        return "finished"

# ======================== UDP 发现服务 ========================

def start_discovery():
    ip = get_local_ip()
    msg = json.dumps({
        "type": "classroom_iot_discovery",
        "alias": SERVER_ALIAS,
        "name": SERVER_ALIAS,   # App 端读取的是 "name" 字段
        "ip": ip,
        "port": HTTP_PORT,
        "version": "1.0",
    }, ensure_ascii=False).encode("utf-8")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    print(f"[发现] UDP 广播已启动于端口 {DISCOVERY_PORT}")

    while True:
        try:
            sock.sendto(msg, ("<broadcast>", DISCOVERY_PORT))
        except Exception as e:
            print(f"[发现] 广播异常: {e}")
        time.sleep(3)

# ======================== API 路由 ========================

# ---------- 服务器信息（无需认证） ----------

@app.route("/api/server/info", methods=["GET"])
def api_server_info():
    """【兼容修复⑦】返回 App 期望的字段名"""
    return jsonify({
        "name": SERVER_ALIAS,
        "version": "1.0",
        "retention_days": RETENTION_DAYS,
        "ip": get_local_ip(),
        "port": HTTP_PORT,
    })

@app.route("/", methods=["GET"])
def index():
    return jsonify({"service": "Classroom IoT Server", "version": "1.1"})

# ---------- 认证 ----------

@app.route("/api/login", methods=["POST"])
@app.route("/api/auth/login", methods=["POST"])    # 【兼容修复①】同时支持两个路径
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    pw_hash = data.get("password_hash", "")
    if not username or not pw_hash:
        return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400
    users = load_users()
    stored = users.get(username)
    if stored and stored == pw_hash:
        token = str(uuid.uuid4())
        _sessions[token] = {"username": username, "login_time": datetime.now().isoformat()}
        return jsonify({"success": True, "token": token, "alias": SERVER_ALIAS})
    return jsonify({"success": False, "message": "用户名或密码错误"}), 401

# ---------- 数据查询 ----------

@app.route("/api/dates", methods=["GET"])
@require_auth
def api_dates():
    """返回日期列表（降序）"""
    dates_set = set()
    for sub in ("multimedia", "blackboardL", "blackboardR"):
        base = os.path.join(RESOURCE_DIR, sub)
        if not os.path.isdir(base):
            continue
        for entry in os.listdir(base):
            if os.path.isdir(os.path.join(base, entry)):
                try:
                    datetime.strptime(entry, "%Y-%m-%d")
                    dates_set.add(entry)
                except ValueError:
                    pass
    cutoff = (date.today() - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    dates = sorted([d for d in dates_set if d >= cutoff], reverse=True)
    return jsonify({"dates": dates})

@app.route("/api/dates/<date_str>/courses", methods=["GET"])
@require_auth
def api_courses(date_str):
    """【兼容修复⑥】返回 App 期望的嵌套结构"""
    is_today = (date_str == date.today().strftime("%Y-%m-%d"))
    courses = {}
    for sub in ("multimedia", "blackboardL", "blackboardR"):
        day_path = os.path.join(RESOURCE_DIR, sub, date_str)
        if not os.path.isdir(day_path):
            continue
        for entry in os.listdir(day_path):
            slot_path = os.path.join(day_path, entry)
            if not os.path.isdir(slot_path):
                continue
            try:
                idx = int(entry)
            except ValueError:
                continue
            describe = parse_describe(slot_path)
            if idx not in courses:
                state = get_course_state(describe, date_str, is_today)
                courses[idx] = {
                    "index": idx,
                    "name": describe.get("name", f"时间段 {idx}"),
                    "start": describe.get("start", ""),
                    "end": describe.get("end", ""),
                    "state": state,
                    # 【修复⑥】嵌套对象格式，与 App 的 CourseInfo.TypeStats 对齐
                    "multimedia": {"count": 0, "size": "0.00"},
                    "blackboardL": {"count": 0, "size": "0.00"},
                    "blackboardR": {"count": 0, "size": "0.00"},
                }
            count = len(parse_index(slot_path))
            size_str = describe.get("size", "0.00")
            courses[idx][sub] = {"count": count, "size": size_str}

    course_list = sorted(courses.values(), key=lambda x: x["index"])
    return jsonify({"date": date_str, "courses": course_list})

# ---------- 图片列表 ----------

@app.route("/api/dates/<date_str>/courses/<int:course_idx>/<type_name>/images", methods=["GET"])
@require_auth
def api_images(date_str, course_idx, type_name):
    """【兼容修复③】type 作为 URL 路径参数，与 App 的 ApiClient.getImages() 对齐"""
    if type_name not in ("multimedia", "blackboardL", "blackboardR"):
        return jsonify({"error": "无效的类型"}), 400

    slot_path = os.path.join(RESOURCE_DIR, type_name, date_str, str(course_idx))
    if not os.path.isdir(slot_path):
        return jsonify({"date": date_str, "course_index": course_idx,
                        "type": type_name, "images": [], "count": 0})

    files = parse_index(slot_path)
    # 【修复】App 期望 images 是字符串列表（文件名），不是对象列表
    return jsonify({
        "date": date_str,
        "course_index": course_idx,
        "type": type_name,
        "images": files,
        "count": len(files),
    })

@app.route("/api/dates/<date_str>/courses/<int:course_idx>/<type_name>/count", methods=["GET"])
@require_auth
def api_image_count(date_str, course_idx, type_name):
    """【兼容修复④】App 轮询用的 count 端点"""
    if type_name not in ("multimedia", "blackboardL", "blackboardR"):
        return jsonify({"error": "无效的类型"}), 400

    slot_path = os.path.join(RESOURCE_DIR, type_name, date_str, str(course_idx))
    count = len(parse_index(slot_path)) if os.path.isdir(slot_path) else 0
    return jsonify({"count": count})

# ---------- 图片文件 ----------

@app.route("/resource/<path:filepath>", methods=["GET"])
@require_auth
def serve_resource(filepath):
    """【兼容修复⑤】路径前缀从 /images 改为 /resource，与 App 的 getImageUrl() 对齐"""
    full = os.path.realpath(os.path.join(RESOURCE_DIR, filepath))
    base = os.path.realpath(RESOURCE_DIR)
    if not full.startswith(base):
        abort(403)
    if not os.path.isfile(full):
        abort(404)
    return send_file(full)

# 也保留 /images 路径以防万一
@app.route("/images/<path:filepath>", methods=["GET"])
@require_auth
def serve_image(filepath):
    full = os.path.realpath(os.path.join(RESOURCE_DIR, filepath))
    base = os.path.realpath(RESOURCE_DIR)
    if not full.startswith(base):
        abort(403)
    if not os.path.isfile(full):
        abort(404)
    return send_file(full)

@app.route('/api/change_password', methods=['POST'])
def change_password():
    data = request.get_json(silent=True) or {}
    username = data.get('username')
    old_pwd_hash = data.get('old_password') # 假设App传过来的是加密后的密码，与登录保持一致
    new_pwd_hash = data.get('new_password')

    if not username or not old_pwd_hash or not new_pwd_hash:
        return jsonify({"success": False, "msg": "信息不完整"}), 400

    # 1. 正确加载用户数据
    users = load_users() 
    
    if username not in users:
        return jsonify({"success": False, "msg": "用户不存在"}), 404
        
    if users[username] != old_pwd_hash:
        return jsonify({"success": False, "msg": "原密码错误"}), 401

    # 2. 更新新密码并保存到文件
    users[username] = new_pwd_hash
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
        return jsonify({"success": True, "msg": "密码修改成功"})
    except Exception as e:
        return jsonify({"success": False, "msg": f"保存失败: {str(e)}"}), 500


# ======================== 初始化与启动 ========================

def init_system():
    os.makedirs(RESOURCE_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        default = {"admin": hashlib.sha256("admin".encode("utf-8")).hexdigest()}
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2, ensure_ascii=False)
        print("[系统] 已自动创建配置目录及默认管理员: admin / admin")

if __name__ == "__main__":
    init_system()

    print("=" * 55)
    print(" Classroom IoT Server v1.1 (App 兼容版)")
    print("=" * 55)
    print(f" 别名       : {SERVER_ALIAS}")
    print(f" 本机 IP    : {get_local_ip()}")
    print(f" HTTP 端口  : {HTTP_PORT}")
    print(f" 发现端口   : {DISCOVERY_PORT} (UDP)")
    print(f" 资源目录   : {RESOURCE_DIR}")
    print(f" 默认账号   : admin / admin")
    print("=" * 55)

    threading.Thread(target=start_discovery, daemon=True).start()

    try:
        from waitress import serve
        print(f"[HTTP] Waitress 生产服务器 启动于 0.0.0.0:{HTTP_PORT}\n")
        serve(app, host="0.0.0.0", port=HTTP_PORT, threads=20)
    except ImportError:
        print("[HTTP] Waitress 未安装，回退到 Flask 开发服务器")
        app.run(host="0.0.0.0", port=HTTP_PORT, threaded=True)
