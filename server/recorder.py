#!/usr/bin/env python3
"""Classroom IoT - 录制引擎模块"""

import os
import re
import time
import shutil
import threading
from datetime import datetime, date, timedelta
from PIL import ImageGrab, Image, ImageDraw, ImageChops, ImageStat
import cv2
import numpy as np


class RecorderManager:
    """统一管理多媒体截屏、摄像头录制、自动清理"""

    def __init__(self, config):
        self.config = config
        self.running_flag = threading.Event()
        self._threads = []

    # ======================== 启停控制 ========================

    def start(self):
        if self.running_flag.is_set():
            print("[录制] 已在运行中")
            return
        self.running_flag.set()
        print("[录制] 引擎启动")

        # 多媒体录制线程
        t = threading.Thread(target=self._multimedia_task, daemon=True)
        t.start()
        self._threads.append(t)

        # 各摄像头录制线程
        for name, cam_cfg in self.config.settings["recorder"]["cameras"].items():
            if cam_cfg.get("enabled", True):
                t = threading.Thread(
                    target=self._camera_task,
                    args=(name, cam_cfg),
                    daemon=True
                )
                t.start()
                self._threads.append(t)

        # 清理线程
        t = threading.Thread(target=self._cleanup_task, daemon=True)
        t.start()
        self._threads.append(t)

    def stop(self):
        self.running_flag.clear()
        print("[录制] 引擎停止")

    def is_running(self):
        return self.running_flag.is_set()

    # ======================== 时间表解析 ========================

    @staticmethod
    def parse_timetable(file_path):
        """解析时间表文件，返回 [(start_dt, end_dt, name), ...]"""
        if not os.path.exists(file_path):
            return []
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        matches = list(re.finditer(r'(\d{2}:\d{2})-(\d{2}:\d{2})', content))
        parsed = []
        today = date.today()
        for i, match in enumerate(matches):
            start_str, end_str = match.group(1), match.group(2)
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            name = content[start_pos:end_pos].strip()
            if not name:
                continue
            try:
                start_dt = datetime.strptime(f"{today} {start_str}", "%Y-%m-%d %H:%M")
                end_dt = datetime.strptime(f"{today} {end_str}", "%Y-%m-%d %H:%M")
                parsed.append((start_dt, end_dt, name))
            except ValueError:
                continue
        return parsed

    # ======================== 通用录制循环 ========================

    def _run_recorder(self, label, save_base_folder, slot_record_func):
        """通用录制循环框架"""
        flag = self.running_flag
        print(f"{label} 检查时间表...")

        # 获取当天时间表
        tt_file, is_temp = self.config.get_timetable_file()

        # 防止没有配置时间表时 tt_file 为 None 导致崩溃
        if not tt_file or not os.path.exists(tt_file):
            print(f"{label} 未找到时间表文件")
            return

        if is_temp:
            print(f"{label} 使用临时时间表: {os.path.basename(tt_file)}")

        slots = self.parse_timetable(tt_file)
        if not slots:
            print(f"{label} 未找到有效时间安排")
            return

        today_str = date.today().strftime("%Y-%m-%d")
        day_folder = os.path.join(save_base_folder, today_str)
        os.makedirs(day_folder, exist_ok=True)

        for index, (start_dt, end_dt, slot_name) in enumerate(slots, 1):
            if not flag.is_set():
                break
            slot_folder = os.path.join(day_folder, str(index))
            os.makedirs(slot_folder, exist_ok=True)

            current_time = datetime.now()
            if current_time > end_dt:
                state = "finish"
            elif current_time < start_dt:
                state = "future"
            else:
                state = "running"

            self._update_describe(slot_folder, slot_name, start_dt, end_dt, state, 0, 0)

            if state == "finish":
                continue

            if state == "future":
                # 实时计算剩余时间，防止电脑休眠唤醒后时间错乱
                while flag.is_set():
                    remaining = (start_dt - datetime.now()).total_seconds()
                    if remaining <= 0:
                        break
                    time.sleep(min(1, remaining))

                if not flag.is_set():
                    break

                self._update_describe(slot_folder, slot_name, start_dt, end_dt, "running", 0, 0)

            count, size = slot_record_func(slot_folder, slot_name, start_dt, end_dt)
            self._update_describe(slot_folder, slot_name, start_dt, end_dt, "finish", count, size)

        print(f"{label} 当前时间表处理完毕")

    # ======================== 多媒体录制 ========================

    def _multimedia_task(self):
        cfg = self.config.settings["recorder"]
        interval = max(1, int(cfg["multimedia_interval"]))
        threshold = float(cfg["diff_threshold"])

        def slot_record(slot_folder, name, start_dt, end_dt):
            count = 0
            total_size = 0
            last_image = None
            while self.running_flag.is_set():
                t0 = time.time()
                if datetime.now() >= end_dt:
                    break
                try:
                    cur = ImageGrab.grab()
                except Exception:
                    time.sleep(interval)
                    continue
                if self._is_different(last_image, cur, threshold):
                    fn = f"{datetime.now().strftime('%H.%M.%S')}-{count + 1}.png"
                    fp = os.path.join(slot_folder, fn)
                    try:
                        cur.save(fp)
                        total_size += os.path.getsize(fp)
                        count += 1
                        self._append_index(slot_folder, fn)
                        self._update_describe(
                            slot_folder, name, start_dt, end_dt, "running",
                            count, total_size / (1024 * 1024))
                        last_image = cur
                    except Exception:
                        pass
                elapsed = time.time() - t0
                if elapsed < interval:
                    time.sleep(interval - elapsed)
            return count, total_size

        # 【关键修复】改为循环结构：处理完一轮时间表后，等待 60 秒重新检查
        # 这样既能防止死循环占满 CPU，又能每分钟感知新创建/修改的临时时间表
        while self.running_flag.is_set():
            self._run_recorder(
                "[多媒体]",
                os.path.join(self.config.resource_dir, "multimedia"),
                slot_record
            )
            # 每 60 秒重试一次
            for _ in range(60):
                if not self.running_flag.is_set():
                    break
                time.sleep(1)

    # ======================== 摄像头录制 ========================

    def _camera_task(self, cam_name, cam_cfg):
        rtsp = cam_cfg["rtsp"]
        fmt = self.config.settings["recorder"].get("camera_format", "png")
        jpeg_q = int(self.config.settings["recorder"].get("camera_jpeg_quality", 90))
        interval = max(1, int(self.config.settings["recorder"]["camera_interval"]))
        ext = ".jpg" if fmt == "jpg" else ".png"
        save_folder = os.path.join(self.config.resource_dir, cam_name)

        def slot_record(slot_folder, name, start_dt, end_dt):
            count = 0
            total_size = 0
            cap = cv2.VideoCapture(rtsp)
            if not cap.isOpened():
                self._update_describe(slot_folder, name, start_dt, end_dt, "error", 0, 0)
                return 0, 0
            try:
                while self.running_flag.is_set():
                    t0 = time.time()
                    if datetime.now() >= end_dt:
                        break
                    ret, frame = cap.read()
                    if not ret:
                        cap.release()
                        time.sleep(3)
                        cap = cv2.VideoCapture(rtsp)
                        if not cap.isOpened():
                            time.sleep(5)
                            continue
                    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    fn = f"{datetime.now().strftime('%H.%M.%S')}-{count + 1}{ext}"
                    fp = os.path.join(slot_folder, fn)
                    try:
                        if fmt == "jpg":
                            pil_img.save(fp, "JPEG", quality=jpeg_q)
                        else:
                            pil_img.save(fp, "PNG")
                        total_size += os.path.getsize(fp)
                        count += 1
                        self._append_index(slot_folder, fn)
                        self._update_describe(
                            slot_folder, name, start_dt, end_dt, "running",
                            count, total_size / (1024 * 1024))
                    except Exception:
                        pass
                    elapsed = time.time() - t0
                    if elapsed < interval:
                        time.sleep(interval - elapsed)
            finally:
                cap.release()
            return count, total_size

        # 【关键修复】同样改为循环结构 + 60 秒休眠重试
        while self.running_flag.is_set():
            self._run_recorder(f"[{cam_name}]", save_folder, slot_record)
            for _ in range(60):
                if not self.running_flag.is_set():
                    break
                time.sleep(1)

    # ======================== 自动清理 ========================

    def _cleanup_task(self):
        flag = self.running_flag
        rd = self.config.settings["recorder"]["retention_days"]
        while flag.is_set():
            # 清理过期资源
            cutoff = (date.today() - timedelta(days=rd)).strftime("%Y-%m-%d")
            for sub in ("multimedia", "blackboardL", "blackboardR"):
                base = os.path.join(self.config.resource_dir, sub)
                if not os.path.isdir(base):
                    continue
                for entry in os.listdir(base):
                    dp = os.path.join(base, entry)
                    if not os.path.isdir(dp):
                        continue
                    try:
                        if entry < cutoff:
                            shutil.rmtree(dp)
                            print(f"[清理] 已删除: {dp}")
                    except ValueError:
                        continue

            # 清理过期临时时间表
            n = self.config.cleanup_temp_timetables()
            if n:
                print(f"[清理] 已删除 {n} 个过期临时时间表")

            # 每小时检查一次
            for _ in range(3600):
                if not flag.is_set():
                    return
                time.sleep(1)

    # ======================== 工具方法 ========================

    @staticmethod
    def _update_describe(folder, name, start, end, state, count, size_mb):
        fp = os.path.join(folder, "describe.txt")
        content = (
            f"name={name}\nstart={start.strftime('%H:%M')}\n"
            f"end={end.strftime('%H:%M')}\nstate={state}\n"
            f"count={count}\nsize={size_mb:.2f}\n"
        )
        try:
            with open(fp, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass

    @staticmethod
    def _append_index(folder, filename):
        fp = os.path.join(folder, "index.txt")
        try:
            with open(fp, "a", encoding="utf-8") as f:
                f.write(f"{filename}\n")
        except Exception:
            pass

    @staticmethod
    def _is_different(img1, img2, threshold):
        if img1 is None or img2 is None:
            return True
        try:
            w = 640
            r = w / float(img1.size[0])
            h = int(float(img1.size[1]) * r)
            s1 = img1.resize((w, h), Image.Resampling.LANCZOS)
            s2 = img2.resize((w, h), Image.Resampling.LANCZOS)
            stat = ImageStat.Stat(ImageChops.difference(s1, s2))
            return sum(stat.rms) / len(stat.rms) >= threshold
        except Exception:
            return True
