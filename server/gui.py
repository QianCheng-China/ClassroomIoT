#!/usr/bin/env python3
"""Classroom IoT - 图形化管理界面"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from datetime import date
import threading


# ======================== 开机自启动工具 ========================

class AutoStart:
    """Windows 开机自启动管理（通过注册表）"""

    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "ClassroomIoT"

    @staticmethod
    def is_available():
        return sys.platform == "win32"

    @staticmethod
    def is_enabled():
        if sys.platform != "win32":
            return False
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, AutoStart.REG_PATH)
            winreg.QueryValueEx(key, AutoStart.APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    @staticmethod
    def _get_command():
        if getattr(sys, "frozen", False):
            exe = sys.executable
            return f'"{exe}" --autostart'
        else:
            exe = sys.executable
            script = os.path.abspath(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "main.py"))
            return f'"{exe}" "{script}" --autostart'

    @staticmethod
    def enable():
        if sys.platform != "win32":
            return False
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, AutoStart.REG_PATH, 0,
                winreg.KEY_SET_VALUE)
            winreg.SetValueEx(
                key, AutoStart.APP_NAME, 0, winreg.REG_SZ,
                AutoStart._get_command())
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    @staticmethod
    def disable():
        if sys.platform != "win32":
            return False
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, AutoStart.REG_PATH, 0,
                winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, AutoStart.APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return True
        except Exception:
            return False


# ======================== 主界面 ========================

class ManagementGUI:

    def __init__(self, root, config, server, recorder):
        self.root = root
        self.config = config
        self.server = server
        self.recorder = recorder

        self.root.title("Classroom IoT 管理平台")
        self.root.geometry("860x620")
        self.root.minsize(750, 500)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self._build_ui()
        self._refresh_user_list()
        self._refresh_update_info()
        self._refresh_timetable()
        self._refresh_autostart()
        self._refresh_status()
        self._poll_status()

    # ======================== 显示/隐藏 ========================

    def show(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self._refresh_status()
        except tk.TclError:
            pass

    def hide(self):
        try:
            self.root.withdraw()
        except tk.TclError:
            pass

    def _on_close(self):
        self.hide()

    # ======================== UI 构建 ========================

    def _build_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        self.tab_server = ttk.Frame(self.notebook, padding=12)
        self.tab_recorder = ttk.Frame(self.notebook, padding=12)
        self.tab_about = ttk.Frame(self.notebook, padding=12)

        self.notebook.add(self.tab_server, text="  服务器管理  ")
        self.notebook.add(self.tab_recorder, text="  录制管理  ")
        self.notebook.add(self.tab_about, text="  关于  ")

        self._build_server_tab()
        self._build_recorder_tab()
        self._build_about_tab()

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(
            self.root, textvariable=self.status_var,
            relief="sunken", anchor="w", padding=(8, 4)
        ).pack(fill="x", padx=8, pady=(4, 8))

    # ---------- 服务器管理页 ----------

    def _build_server_tab(self):
        tab = self.tab_server
        row = 0

        # -- 服务启停 --
        lf1 = ttk.LabelFrame(tab, text="服务状态", padding=10)
        lf1.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        row += 1

        self.server_status_var = tk.StringVar(value="● 未启动")
        ttk.Label(lf1, textvariable=self.server_status_var,
                  font=("", 11)).grid(row=0, column=0, padx=(0, 16))
        self.btn_start_server = ttk.Button(
            lf1, text="启动服务器", command=self._start_server)
        self.btn_start_server.grid(row=0, column=1, padx=4)
        self.btn_stop_server = ttk.Button(
            lf1, text="停止服务器", command=self._stop_server, state="disabled")
        self.btn_stop_server.grid(row=0, column=2, padx=4)

        # -- 基本设置 --
        lf2 = ttk.LabelFrame(tab, text="基本设置", padding=10)
        lf2.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        row += 1

        ttk.Label(lf2, text="服务器别名:").grid(row=0, column=0, sticky="w", pady=3)
        self.entry_alias = ttk.Entry(lf2, width=36)
        self.entry_alias.grid(row=0, column=1, columnspan=2, sticky="ew", pady=3, padx=4)
        self.entry_alias.insert(0, self.config.alias)

        ttk.Label(lf2, text="HTTP 端口:").grid(row=1, column=0, sticky="w", pady=3)
        self.entry_http_port = ttk.Entry(lf2, width=12)
        self.entry_http_port.grid(row=1, column=1, sticky="w", pady=3, padx=4)
        self.entry_http_port.insert(0, str(self.config.http_port))

        ttk.Label(lf2, text="发现端口:").grid(row=2, column=0, sticky="w", pady=3)
        self.entry_disc_port = ttk.Entry(lf2, width=12)
        self.entry_disc_port.grid(row=2, column=1, sticky="w", pady=3, padx=4)
        self.entry_disc_port.insert(0, str(self.config.discovery_port))

        lf2.columnconfigure(1, weight=1)

        ttk.Button(lf2, text="保存服务器设置",
                   command=self._save_server_settings).grid(
            row=3, column=0, columnspan=3, pady=(10, 0))

        # -- 开机自启动 --
        lf_autostart = ttk.LabelFrame(tab, text="开机自启动", padding=10)
        lf_autostart.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        row += 1

        self.var_autostart = tk.BooleanVar(value=False)
        self.chk_autostart = ttk.Checkbutton(
            lf_autostart, text="开机时自动启动程序并运行服务器",
            variable=self.var_autostart,
            command=self._on_autostart_toggle)
        self.chk_autostart.grid(row=0, column=0, sticky="w")

        if not AutoStart.is_available():
            self.chk_autostart.config(state="disabled")
            ttk.Label(lf_autostart, text="（当前系统不支持，仅限 Windows）",
                      foreground="gray").grid(row=1, column=0, sticky="w", pady=(4, 0))

        # -- 用户管理 --
        lf3 = ttk.LabelFrame(tab, text="用户管理", padding=10)
        lf3.grid(row=row, column=0, sticky="nsew", pady=(0, 8))
        row += 1
        tab.rowconfigure(row - 1, weight=1)
        tab.columnconfigure(0, weight=1)

        self.tree_users = ttk.Treeview(
            lf3, columns=("username",), show="headings",
            height=6, selectmode="browse")
        self.tree_users.heading("username", text="用户名")
        self.tree_users.column("username", width=200)
        self.tree_users.pack(fill="both", expand=True, pady=(0, 8))

        bf = ttk.Frame(lf3)
        bf.pack(fill="x")
        ttk.Label(bf, text="新用户名:").pack(side="left")
        self.entry_new_user = ttk.Entry(bf, width=14)
        self.entry_new_user.pack(side="left", padx=4)
        ttk.Button(bf, text="添加用户",
                   command=self._add_user).pack(side="left", padx=4)
        ttk.Button(bf, text="重置选中密码",
                   command=self._reset_password).pack(side="left", padx=4)
        ttk.Button(bf, text="删除选中",
                   command=self._delete_user).pack(side="left", padx=4)

        # -- 软件更新 --
        lf4 = ttk.LabelFrame(tab, text="软件更新管理", padding=10)
        lf4.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        row += 1

        f_ver = ttk.Frame(lf4)
        f_ver.pack(fill="x", pady=(0, 6))
        ttk.Label(f_ver, text="最新版本:").pack(side="left")
        self.entry_update_ver = ttk.Entry(f_ver, width=14)
        self.entry_update_ver.pack(side="left", padx=4)
        ttk.Button(f_ver, text="选择 APK 文件",
                   command=self._select_apk).pack(side="left", padx=4)
        self.lbl_apk = ttk.Label(f_ver, text="(未选择)")
        self.lbl_apk.pack(side="left", padx=4)

        ttk.Label(lf4, text="更新说明:").pack(anchor="w")
        self.text_changelog = scrolledtext.ScrolledText(
            lf4, width=60, height=5, wrap="word")
        self.text_changelog.pack(fill="x", pady=(0, 6))

        ttk.Button(lf4, text="保存更新信息",
                   command=self._save_update_info).pack()

    # ---------- 录制管理页 ----------

    def _build_recorder_tab(self):
        tab = self.tab_recorder
        row = 0

        lf1 = ttk.LabelFrame(tab, text="录制状态", padding=10)
        lf1.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        row += 1

        self.rec_status_var = tk.StringVar(value="● 未启动")
        ttk.Label(lf1, textvariable=self.rec_status_var,
                  font=("", 11)).grid(row=0, column=0, padx=(0, 16))
        self.btn_start_rec = ttk.Button(
            lf1, text="启动录制", command=self._start_recorder)
        self.btn_start_rec.grid(row=0, column=1, padx=4)
        self.btn_stop_rec = ttk.Button(
            lf1, text="停止录制", command=self._stop_recorder, state="disabled")
        self.btn_stop_rec.grid(row=0, column=2, padx=4)

        lf2 = ttk.LabelFrame(tab, text="录制参数", padding=10)
        lf2.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        row += 1

        rec = self.config.settings["recorder"]
        params = [
            ("多媒体截屏间隔 (秒):", "multimedia_interval",
             rec["multimedia_interval"]),
            ("摄像头拍照间隔 (秒):", "camera_interval",
             rec["camera_interval"]),
            ("差异阈值 (RMS):", "diff_threshold",
             rec["diff_threshold"]),
            ("保留天数 (天):", "retention_days",
             rec["retention_days"]),
            ("JPEG 质量 (仅 jpg):", "camera_jpeg_quality",
             rec.get("camera_jpeg_quality", 90)),
        ]
        self.rec_entries = {}
        for i, (label, key, default) in enumerate(params):
            ttk.Label(lf2, text=label).grid(
                row=i, column=0, sticky="w", pady=3)
            e = ttk.Entry(lf2, width=12)
            e.grid(row=i, column=1, sticky="w", pady=3, padx=4)
            e.insert(0, str(default))
            self.rec_entries[key] = e

        i_fmt = len(params)
        ttk.Label(lf2, text="图片格式:").grid(
            row=i_fmt, column=0, sticky="w", pady=3)
        self.combo_format = ttk.Combobox(
            lf2, values=["png", "jpg"], width=8, state="readonly")
        self.combo_format.grid(row=i_fmt, column=1, sticky="w",
                               padx=4, pady=3)
        self.combo_format.set(rec.get("camera_format", "png"))

        ttk.Button(lf2, text="保存录制参数",
                   command=self._save_rec_settings).grid(
            row=i_fmt + 1, column=0, columnspan=2, pady=(10, 0))

        lf3 = ttk.LabelFrame(tab, text="摄像头配置", padding=10)
        lf3.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        row += 1

        self.cam_entries = {}
        cams = rec.get("cameras", {})
        for i, (name, cfg) in enumerate(cams.items()):
            ttk.Label(lf3, text=f"{name}:").grid(
                row=i, column=0, sticky="w", pady=3)
            e = ttk.Entry(lf3, width=70)
            e.grid(row=i, column=1, sticky="ew", pady=3, padx=4)
            e.insert(0, cfg.get("rtsp", ""))
            self.cam_entries[name] = e

        ttk.Button(lf3, text="保存摄像头配置",
                   command=self._save_cam_settings).grid(
            row=len(cams), column=0, columnspan=2, pady=(10, 0))
        lf3.columnconfigure(1, weight=1)

        lf4 = ttk.LabelFrame(tab, text="录制时间表", padding=10)
        lf4.grid(row=row, column=0, sticky="nsew", pady=(0, 8))
        row += 1
        tab.rowconfigure(row - 1, weight=1)
        tab.columnconfigure(0, weight=1)

        f_day = ttk.Frame(lf4)
        f_day.pack(fill="x", pady=(0, 4))

        days_cn = ["monday", "tuesday", "wednesday", "thursday",
                   "friday", "saturday", "sunday"]
        self.combo_day = ttk.Combobox(
            f_day, values=days_cn, width=12, state="readonly")
        self.combo_day.set(days_cn[date.today().weekday()])
        self.combo_day.pack(side="left")
        self.combo_day.bind(
            "<<ComboboxSelected>>", lambda e: self._refresh_timetable())

        self.lbl_tt_type = ttk.Label(f_day, text="", foreground="orange")
        self.lbl_tt_type.pack(side="left", padx=(12, 0))

        self.text_timetable = scrolledtext.ScrolledText(
            lf4, width=60, height=10, wrap="none", font=("Consolas", 10))
        self.text_timetable.pack(fill="both", expand=True, pady=(0, 6))

        bf = ttk.Frame(lf4)
        bf.pack(fill="x")
        ttk.Button(bf, text="保存时间表",
                   command=self._save_timetable).pack(side="left", padx=4)
        ttk.Button(bf, text="设为今日临时时间表",
                   command=self._set_temp_timetable).pack(
            side="left", padx=4)

    # ---------- 关于页 ----------

    def _build_about_tab(self):
        tab = self.tab_about
        info = [
            ("程序名称", "Classroom IoT Server"),
            ("版本", "v2.0 (模块化重构版)"),
            ("机器 ID", self.config.machine_id),
            ("配置目录", self.config.config_dir),
            ("资源目录", self.config.resource_dir),
        ]
        for i, (k, v) in enumerate(info):
            ttk.Label(tab, text=k + ":",
                      font=("", 10, "bold")).grid(
                row=i, column=0, sticky="nw", pady=4, padx=(0, 12))
            ttk.Label(tab, text=v).grid(
                row=i, column=1, sticky="nw", pady=4)

    # ======================== 服务器操作 ========================

    def _start_server(self):
        if self.server.is_running():
            return
        self.server.start()
        self.root.after(2000, self._refresh_status)

    def _stop_server(self):
        self.server.stop()
        self.root.after(1500, self._refresh_status)

    def _save_server_settings(self):
        alias = self.entry_alias.get().strip()
        try:
            http_port = int(self.entry_http_port.get())
            disc_port = int(self.entry_disc_port.get())
        except ValueError:
            messagebox.showerror("错误", "端口必须是数字")
            return
        
        # 1. 更新字典（准备写入文件）
        self.config.settings["server"]["alias"] = alias
        self.config.settings["server"]["http_port"] = http_port
        self.config.settings["server"]["discovery_port"] = disc_port
        
        # 2. 写入文件
        self.config.save_settings()
        
        # 【关键修复】3. 强制同步更新内存中的属性，让 UDP 线程能立刻读到新值
        self.config.alias = alias
        self.config.http_port = http_port
        self.config.discovery_port = disc_port
        
        messagebox.showinfo(
            "成功", "服务器设置已保存（部分设置需重启服务生效）")


    # ======================== 自启动操作 ========================

    def _refresh_autostart(self):
        self.var_autostart.set(AutoStart.is_enabled())

    def _on_autostart_toggle(self):
        if self.var_autostart.get():
            if AutoStart.enable():
                messagebox.showinfo(
                    "成功",
                    "开机自启动已开启。\n"
                    "下次开机后程序将自动启动并运行服务器。")
            else:
                messagebox.showerror("失败", "设置自启动失败，请检查系统权限。")
                self.var_autostart.set(False)
        else:
            if AutoStart.disable():
                messagebox.showinfo("成功", "开机自启动已关闭。")
            else:
                messagebox.showerror("失败", "取消自启动失败。")

    # ======================== 用户操作 ========================

    def _refresh_user_list(self):
        self.tree_users.delete(*self.tree_users.get_children())
        users = self.config.load_users()
        for u in users:
            self.tree_users.insert("", "end", values=(u,))

    def _add_user(self):
        name = self.entry_new_user.get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入用户名")
            return
        ok, msg = self.config.add_user(name)
        if ok:
            self.entry_new_user.delete(0, "end")
            self._refresh_user_list()
            messagebox.showinfo("成功", msg)
        else:
            messagebox.showerror("失败", msg)

    def _delete_user(self):
        sel = self.tree_users.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个用户")
            return
        username = self.tree_users.item(sel[0])["values"][0]
        ok, msg = self.config.delete_user(username)
        if ok:
            self._refresh_user_list()
            messagebox.showinfo("成功", msg)
        else:
            messagebox.showerror("失败", msg)

    def _reset_password(self):
        sel = self.tree_users.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个用户")
            return
        username = self.tree_users.item(sel[0])["values"][0]
        ok, msg = self.config.reset_user_password(username)
        if ok:
            messagebox.showinfo("成功", msg)
        else:
            messagebox.showerror("失败", msg)

    # ======================== 更新管理 ========================

    def _refresh_update_info(self):
        desc = self.config.load_update_describe()
        self.entry_update_ver.delete(0, "end")
        self.entry_update_ver.insert(0, desc.get("version", ""))
        self.text_changelog.delete("1.0", "end")
        self.text_changelog.insert("1.0", desc.get("changelog", ""))
        apk = self.config.update_apk
        if os.path.isfile(apk):
            size_mb = os.path.getsize(apk) / (1024 * 1024)
            self.lbl_apk.config(text=f"update.apk ({size_mb:.1f} MB)")
        else:
            self.lbl_apk.config(text="(未选择)")

    def _select_apk(self):
        path = filedialog.askopenfilename(
            title="选择 APK 文件",
            filetypes=[("APK 文件", "*.apk"), ("所有文件", "*.*")])
        if path:
            import shutil
            os.makedirs(self.config.update_dir, exist_ok=True)
            shutil.copy2(path, self.config.update_apk)
            self._refresh_update_info()

    def _save_update_info(self):
        ver = self.entry_update_ver.get().strip()
        changelog = self.text_changelog.get("1.0", "end").strip()
        if not ver:
            messagebox.showwarning("提示", "请输入版本号")
            return
        self.config.save_update_describe(ver, changelog)
        messagebox.showinfo("成功", "更新信息已保存")

    # ======================== 录制操作 ========================

    def _start_recorder(self):
        self.recorder.start()
        self.root.after(500, self._refresh_status)

    def _stop_recorder(self):
        self.recorder.stop()
        self.root.after(500, self._refresh_status)

    def _save_rec_settings(self):
        rec = self.config.settings["recorder"]
        try:
            for key, entry in self.rec_entries.items():
                rec[key] = type(rec.get(key, 1))(entry.get())
            rec["camera_format"] = self.combo_format.get()
            self.config.save_settings()
            messagebox.showinfo("成功", "录制参数已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def _save_cam_settings(self):
        cams = self.config.settings["recorder"]["cameras"]
        for name, entry in self.cam_entries.items():
            if name in cams:
                cams[name]["rtsp"] = entry.get().strip()
        self.config.save_settings()
        messagebox.showinfo("成功", "摄像头配置已保存")

    # ======================== 时间表操作 ========================

    def _refresh_timetable(self):
        day = self.combo_day.get()
        if not day:
            return
        today_str = date.today().strftime("%Y-%m-%d")
        days_cn = ["monday", "tuesday", "wednesday", "thursday",
                   "friday", "saturday", "sunday"]
        if day == days_cn[date.today().weekday()]:
            temp_path = os.path.join(
                self.config.timetable_dir, f"{today_str}.txt")
            if os.path.exists(temp_path):
                self.lbl_tt_type.config(
                    text=f"⚠ 今日有临时时间表 ({today_str}.txt)，"
                         f"将优先使用")
                path = temp_path
            else:
                self.lbl_tt_type.config(text="")
                path = os.path.join(
                    self.config.timetable_dir, f"{day}.txt")
        else:
            self.lbl_tt_type.config(text="")
            path = os.path.join(
                self.config.timetable_dir, f"{day}.txt")
        self.text_timetable.delete("1.0", "end")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.text_timetable.insert("1.0", f.read())
        else:
            self.text_timetable.insert(
                "1.0",
                f"# {day}.txt\n"
                f"# 格式: HH:MM-HH:MM 课程名\n"
                f"# 例如:\n"
                f"# 07:50-08:30 英语\n"
                f"# 08:40-09:20 语文\n")

    def _save_timetable(self):
        day = self.combo_day.get()
        if not day:
            return
        content = self.text_timetable.get("1.0", "end").strip()
        path = self.config.save_timetable(content, day)
        messagebox.showinfo(
            "成功", f"时间表已保存到 {os.path.basename(path)}")

    def _set_temp_timetable(self):
        content = self.text_timetable.get("1.0", "end").strip()
        if not content.strip() or content.strip().startswith("#"):
            messagebox.showwarning("提示", "时间表内容为空")
            return
        today_str = date.today().strftime("%Y-%m-%d")
        path = self.config.save_timetable(content, today_str)
        messagebox.showinfo(
            "成功",
            f"已设置 {today_str} 的临时时间表。\n"
            f"该文件将在明日自动清理。")

    # ======================== 状态刷新 ========================

    def _refresh_status(self):
        try:
            if self.server.is_running():
                self.server_status_var.set(
                    f"● 运行中 (端口 {self.config.http_port})")
                self.btn_start_server.config(state="disabled")
                self.btn_stop_server.config(state="normal")
            else:
                self.server_status_var.set("● 未启动")
                self.btn_start_server.config(state="normal")
                self.btn_stop_server.config(state="disabled")
            if self.recorder.is_running():
                # 【关键修复】智能判断当前到底是在"录制"还是在"待命"
                from datetime import datetime
                is_actually_recording = False
                
                tt_file, _ = self.config.get_timetable_file()
                if tt_file and os.path.exists(tt_file):
                    slots = self.recorder.parse_timetable(tt_file)
                    now = datetime.now()
                    for start_dt, end_dt, _ in slots:
                        if start_dt <= now <= end_dt:
                            is_actually_recording = True
                            break
                            
                if is_actually_recording:
                    cams = self.config.settings["recorder"]["cameras"]
                    active = sum(
                        1 for c in cams.values() if c.get("enabled", True))
                    self.rec_status_var.set(
                        f"● 录制中 (多媒体 + {active}路摄像头)")
                else:
                    self.rec_status_var.set(
                        "● 待命中 (等待上课时间或无时间表)")
                    
                self.btn_start_rec.config(state="disabled")
                self.btn_stop_rec.config(state="normal")
            else:
                self.rec_status_var.set("● 未启动")
                self.btn_start_rec.config(state="normal")
                self.btn_stop_rec.config(state="disabled")


            srv = "运行中" if self.server.is_running() else "已停止"
            rec = "运行中" if self.recorder.is_running() else "已停止"
            self.status_var.set(
                f"服务器: {srv}  |  录制: {rec}  |  "
                f"别名: {self.config.alias}")
        except tk.TclError:
            pass

    def _poll_status(self):
        try:
            self._refresh_status()
            self.root.after(3000, self._poll_status)
        except tk.TclError:
            pass
