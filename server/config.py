#!/usr/bin/env python3
"""Classroom IoT - 配置管理模块"""

import os
import json
import uuid
import hashlib


class Config:
    """统一配置管理，所有模块共享此实例"""

    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_dir = os.path.join(self.base_dir, "config")
        self.users_file = os.path.join(self.config_dir, "users.json")
        self.settings_file = os.path.join(self.config_dir, "settings.json")
        self.machine_id_file = os.path.join(self.config_dir, "machine_id.txt")
        self.update_dir = os.path.join(self.base_dir, "update")
        self.update_describe = os.path.join(self.update_dir, "describe.txt")
        self.update_apk = os.path.join(self.update_dir, "update.apk")
        self.resource_dir = os.path.join(self.base_dir, "resource")
        self.timetable_dir = os.path.join(self.base_dir, "recordTimetable")

        self._ensure_dirs()
        self.machine_id = self._load_or_create_machine_id()
        self.settings = self._load_settings()

    # ======================== 目录初始化 ========================

    def _ensure_dirs(self):
        for d in [self.config_dir, self.update_dir,
                   self.resource_dir, self.timetable_dir]:
            os.makedirs(d, exist_ok=True)
        for sub in ["multimedia", "blackboardL", "blackboardR"]:
            os.makedirs(os.path.join(self.resource_dir, sub), exist_ok=True)

    # ======================== 机器 UUID ========================

    def _load_or_create_machine_id(self):
        if os.path.exists(self.machine_id_file):
            with open(self.machine_id_file, "r") as f:
                mid = f.read().strip()
            if mid:
                return mid
        mid = str(uuid.uuid4())
        with open(self.machine_id_file, "w") as f:
            f.write(mid)
        return mid

    # ======================== 设置加载/保存 ========================

    def _default_settings(self):
        return {
            "server": {
                "alias": "Classroom IoT",
                "http_port": 8080,
                "discovery_port": 48899,
            },
            "recorder": {
                "multimedia_interval": 1,
                "camera_interval": 10,
                "diff_threshold": 0.5,
                "retention_days": 7,
                "camera_format": "png",
                "camera_jpeg_quality": 90,
                "cameras": {
                    "blackboardL": {
                        "rtsp": "rtsp://admin:password@192.168.1.11:554/"
                               "cam/realmonitor?channel=1&subtype=0",
                        "enabled": True,
                    },
                    "blackboardR": {
                        "rtsp": "rtsp://admin:password@192.168.1.10:554/"
                               "cam/realmonitor?channel=1&subtype=0",
                        "enabled": True,
                    },
                },
            },
        }

    def _load_settings(self):
        default = self._default_settings()
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                for key in default:
                    if key not in loaded:
                        loaded[key] = default[key]
                    elif isinstance(default[key], dict):
                        for sk in default[key]:
                            if sk not in loaded[key]:
                                loaded[key][sk] = default[key][sk]
                return loaded
            except Exception:
                return default
        return default

    def save_settings(self):
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)

    # ======================== 用户管理 ========================

    def load_users(self):
        if not os.path.exists(self.users_file):
            default = {"admin": hashlib.sha256("admin".encode()).hexdigest()}
            self._save_users_dict(default)
            return default
        with open(self.users_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_users_dict(self, users):
        os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
        with open(self.users_file, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)

    def add_user(self, username, password="12345678"):
        users = self.load_users()
        if username in users:
            return False, "用户已存在"
        if not username.strip():
            return False, "用户名不能为空"
        users[username] = hashlib.sha256(password.encode()).hexdigest()
        self._save_users_dict(users)
        return True, f"用户 {username} 创建成功（默认密码 12345678）"

    def delete_user(self, username):
        users = self.load_users()
        if username not in users:
            return False, "用户不存在"
        if username == "admin":
            return False, "不能删除管理员账号"
        del users[username]
        self._save_users_dict(users)
        return True, f"用户 {username} 已删除"

    def reset_user_password(self, username):
        users = self.load_users()
        if username not in users:
            return False, "用户不存在"
        users[username] = hashlib.sha256("12345678".encode()).hexdigest()
        self._save_users_dict(users)
        return True, f"用户 {username} 的密码已重置为 12345678"

    # ======================== 更新描述管理 ========================

    def load_update_describe(self):
        if not os.path.exists(self.update_describe):
            default = {"version": "0.1.0", "changelog": "初始版本"}
            self.save_update_describe("0.1.0", "初始版本")
            return default
        try:
            with open(self.update_describe, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"version": "0.1.0", "changelog": ""}

    def save_update_describe(self, version, changelog):
        os.makedirs(self.update_dir, exist_ok=True)
        with open(self.update_describe, "w", encoding="utf-8") as f:
            json.dump({"version": version, "changelog": changelog},
                      f, indent=2, ensure_ascii=False)

    # ======================== 时间表管理 ========================

    def get_timetable_file(self, target_date=None):
        """返回当天应使用的时间表文件路径。
        优先级：临时时间表（日期.txt） > 默认时间表（星期.txt）
        """
        from datetime import date as _date
        if target_date is None:
            target_date = _date.today()
        date_str = target_date.strftime("%Y-%m-%d")
        days = ["monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday", "sunday"]
        weekday_file = os.path.join(
            self.timetable_dir, f"{days[target_date.weekday()]}.txt")
        temp_file = os.path.join(self.timetable_dir, f"{date_str}.txt")
        if os.path.exists(temp_file):
            return temp_file, True  # True = 临时时间表
        return weekday_file, False

    def save_timetable(self, content, day_key):
        """保存时间表。day_key 可以是 'monday'~'sunday' 或 '2024-01-15'"""
        path = os.path.join(self.timetable_dir, f"{day_key}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
        return path

    def cleanup_temp_timetables(self):
        """删除过期的临时时间表"""
        from datetime import date as _date, timedelta
        cutoff = _date.today() - timedelta(days=1)
        if not os.path.exists(self.timetable_dir):
            return 0
        count = 0
        for fn in os.listdir(self.timetable_dir):
            fp = os.path.join(self.timetable_dir, fn)
            if not os.path.isfile(fp):
                continue
            try:
                file_date = _date.strptime(fn.replace(".txt", ""), "%Y-%m-%d")
                if file_date < cutoff:
                    os.remove(fp)
                    count += 1
            except ValueError:
                continue  # 不是日期格式的文件，跳过
        return count

    # ======================== 便捷属性 ========================

    @property
    def alias(self):
        return self.settings["server"]["alias"]

    @property
    def http_port(self):
        return int(self.settings["server"]["http_port"])

    @property
    def discovery_port(self):
        return int(self.settings["server"]["discovery_port"])
