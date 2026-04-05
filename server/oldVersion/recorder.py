#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classroom IoT - 智能板书记录系统 v5
同时录制：多媒体屏幕 / 左侧摄像头 / 右侧摄像头
"""

import os
import sys
import time
import threading
import ctypes
import re
import shutil
from datetime import datetime, date, timedelta
from PIL import ImageGrab, Image, ImageDraw, ImageChops, ImageStat
import pystray
import cv2
import numpy as np

# ======================== 可配置项 ========================

TIMETABLE_FOLDER = "recordTimetable"          # 时间表文件夹
BASE_SAVE_FOLDER = "resource"                 # 基础存储路径

MULTIMEDIA_FOLDER  = os.path.join(BASE_SAVE_FOLDER, "multimedia")
BLACKBOARD_L_FOLDER = os.path.join(BASE_SAVE_FOLDER, "blackboardL")
BLACKBOARD_R_FOLDER = os.path.join(BASE_SAVE_FOLDER, "blackboardR")

MULTIMEDIA_INTERVAL = 1        # 多媒体截屏间隔（秒）
CAMERA_INTERVAL     = 10       # 摄像头拍照间隔（秒）
DIFF_THRESHOLD      = 0.5      # 多媒体截屏差异阈值（RMS），建议 0.5-2.0
RETENTION_DAYS      = 7        # 照片保留天数，超过自动删除

# 摄像头配置
CAMERAS = {
    "blackboardL": {
        "rtsp": "rtsp://admin:1q2w3e4r5t@192.168.1.11:554/cam/realmonitor?channel=1&subtype=0",
        "save_folder": BLACKBOARD_L_FOLDER,
    },
    "blackboardR": {
        "rtsp": "rtsp://admin:1q2w3e4r5t@192.168.1.10:554/cam/realmonitor?channel=1&subtype=0",
        "save_folder": BLACKBOARD_R_FOLDER,
    },
}

# 摄像头图像保存格式："png" 与多媒体一致；"jpg" 可大幅节省空间
CAMERA_IMAGE_FORMAT = "png"
CAMERA_JPEG_QUALITY = 90       # 仅 format="jpg" 时生效

# ======================== 全局变量 ========================
running = True

# -----------------------------------------------------------
# 1. 彻底隐藏控制台窗口 (Windows, 必须在最开始执行)
# -----------------------------------------------------------
if sys.platform == 'win32':
    try:
        log_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "recorder_log.txt"
        )
        sys.stdout = open(log_path, 'a', encoding='utf-8')
        sys.stderr = sys.stdout

        whnd = ctypes.windll.kernel32.GetConsoleWindow()
        if whnd:
            ctypes.windll.user32.ShowWindow(whnd, 0)
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


# ======================== 时间表解析 ========================

def get_weekday_filename():
    """根据今天星期几，返回对应的时间表文件名"""
    days = ["monday", "tuesday", "wednesday",
            "thursday", "friday", "saturday", "sunday"]
    return f"{days[date.today().weekday()]}.txt"


def parse_timetable(file_path):
    """
    解析时间表文件。
    支持单行多条记录（如 "07:50-08:30 英语 08:40-09:20 语文"）
    也支持每行一条记录的传统格式。
    返回: [(start_datetime, end_datetime, 课程名称), ...]
    """
    if not os.path.exists(file_path):
        print(f"错误：找不到时间表文件 -> {file_path}")
        return []

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 用正则找出所有 HH:MM-HH:MM 模式
    time_pattern = r'(\d{2}:\d{2})-(\d{2}:\d{2})'
    matches = list(re.finditer(time_pattern, content))

    parsed_slots = []
    today = date.today()

    for i, match in enumerate(matches):
        start_str = match.group(1)
        end_str   = match.group(2)

        # 课程名称 = 本个时间到下一个时间之间的文本
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        name = content[start_pos:end_pos].strip()

        if not name:
            continue

        try:
            start_time = datetime.strptime(
                f"{today} {start_str}", "%Y-%m-%d %H:%M"
            )
            end_time = datetime.strptime(
                f"{today} {end_str}", "%Y-%m-%d %H:%M"
            )
            parsed_slots.append((start_time, end_time, name))
        except ValueError:
            print(f"警告：跳过格式错误 -> {start_str}-{end_str} {name}")
            continue

    return parsed_slots


# ======================== 公共工具函数 ========================

def update_describe_file(folder_path, name, start_dt, end_dt,
                         state, count, total_size_mb):
    """
    写入 / 更新 describe.txt
    字段：name / start / end / state / count / size
    """
    filepath = os.path.join(folder_path, "describe.txt")
    content = (
        f"name={name}\n"
        f"start={start_dt.strftime('%H:%M')}\n"
        f"end={end_dt.strftime('%H:%M')}\n"
        f"state={state}\n"
        f"count={count}\n"
        f"size={total_size_mb:.2f}\n"
    )
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        print(f"写入描述文件失败: {e}")


def append_to_index(folder_path, filename):
    """追加一行文件名到 index.txt"""
    filepath = os.path.join(folder_path, "index.txt")
    try:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(f"{filename}\n")
    except Exception as e:
        print(f"追加索引文件失败: {e}")


def is_image_different(img1, img2, threshold):
    """RMS 算法判断两张图片是否有显著差异"""
    if img1 is None or img2 is None:
        return True
    try:
        base_width = 640
        w_percent = base_width / float(img1.size[0])
        h_size = int(float(img1.size[1]) * w_percent)
        img1_small = img1.resize(
            (base_width, h_size), Image.Resampling.LANCZOS
        )
        img2_small = img2.resize(
            (base_width, h_size), Image.Resampling.LANCZOS
        )
        diff = ImageChops.difference(img1_small, img2_small)
        stat = ImageStat.Stat(diff)
        rms_mean = sum(stat.rms) / len(stat.rms)
        return rms_mean >= threshold
    except Exception:
        return True


def get_image_extension():
    """根据配置返回摄像头图片扩展名"""
    return ".jpg" if CAMERA_IMAGE_FORMAT == "jpg" else ".png"


def save_image(pil_image, filepath):
    """根据配置保存为 PNG 或 JPEG"""
    if CAMERA_IMAGE_FORMAT == "jpg":
        pil_image.save(filepath, "JPEG", quality=CAMERA_JPEG_QUALITY)
    else:
        pil_image.save(filepath, "PNG")


# ======================== 通用录制循环 ========================

def run_recorder(label, save_base_folder, slot_record_func):
    """
    通用录制循环 —— 所有录制器共享同一套时间槽遍历逻辑。

    参数
    ----------
    label : str
        日志前缀，如 "[多媒体]" "[blackboardL]"
    save_base_folder : str
        日期文件夹的父目录，如 resource/multimedia
    slot_record_func : callable(slot_folder, slot_name, start_dt, end_dt) -> (int, int)
        在某个时间槽内执行的具体录制逻辑。
        返回 (photo_count, total_size_bytes)。
        该函数内部自行负责 running 标志判断和超时退出。
    """
    global running
    print(f"{label} 录制任务启动于 {datetime.now()}")

    # ---- 读取时间表 ----
    filename = get_weekday_filename()
    timetable_path = os.path.join(TIMETABLE_FOLDER, filename)
    slots = parse_timetable(timetable_path)
    if not slots:
        print(f"{label} 未找到有效的时间安排。")
        return

    today_str = date.today().strftime("%Y-%m-%d")
    day_folder = os.path.join(save_base_folder, today_str)
    os.makedirs(day_folder, exist_ok=True)

    # ---- 逐个时间槽处理 ----
    for index, (start_dt, end_dt, slot_name) in enumerate(slots, 1):
        if not running:
            break

        slot_folder = os.path.join(day_folder, str(index))
        os.makedirs(slot_folder, exist_ok=True)

        # 判断当前状态
        current_time = datetime.now()
        if current_time > end_dt:
            state = "finish"
        elif current_time < start_dt:
            state = "future"
        else:
            state = "running"

        update_describe_file(
            slot_folder, slot_name, start_dt, end_dt, state, 0, 0.0
        )

        if state == "finish":
            print(f"{label} 时间段 {index} 已结束，跳过。")
            continue

        if state == "future":
            wait_seconds = (start_dt - current_time).total_seconds()
            print(f"{label} 等待 {int(wait_seconds)} 秒，"
                  f"'{slot_name}' 即将开始...")
            while wait_seconds > 0 and running:
                time.sleep(min(1, wait_seconds))
                wait_seconds -= 1
            if not running:
                break

        # ---- 开始录制 ----
        print(f"{label} === 开始记录: {slot_name} ===")
        update_describe_file(
            slot_folder, slot_name, start_dt, end_dt, "running", 0, 0.0
        )

        photo_count, total_size_bytes = slot_record_func(
            slot_folder, slot_name, start_dt, end_dt
        )

        final_size_mb = total_size_bytes / (1024 * 1024)
        update_describe_file(
            slot_folder, slot_name, start_dt, end_dt,
            "finish", photo_count, final_size_mb
        )

    print(f"{label} 所有录制任务结束。")


# ======================== 多媒体录制 ========================

def multimedia_slot_record(slot_folder, slot_name, start_dt, end_dt):
    """
    多媒体截屏 —— 时间槽级别录制逻辑
    每秒截屏一次，与上一张进行 RMS 比较，差异大则保存。
    """
    global running
    photo_count = 0
    total_size_bytes = 0
    last_image = None
    ext = ".png"  # 多媒体固定使用 PNG

    while running:
        loop_start = time.time()
        current_time = datetime.now()
        if current_time >= end_dt:
            break

        # 截屏
        try:
            current_image = ImageGrab.grab()
        except Exception as e:
            print(f"[多媒体] 截屏异常：{e}")
            time.sleep(MULTIMEDIA_INTERVAL)
            continue

        # 差异判断
        if is_image_different(last_image, current_image, DIFF_THRESHOLD):
            now = datetime.now()
            filename_img = f"{now.strftime('%H.%M.%S')}-{photo_count + 1}{ext}"
            filepath_img = os.path.join(slot_folder, filename_img)
            try:
                current_image.save(filepath_img)
                print(f"[多媒体] 已保存：{filename_img}")
                file_size = os.path.getsize(filepath_img)
                total_size_bytes += file_size
                photo_count += 1

                append_to_index(slot_folder, filename_img)
                total_size_mb = total_size_bytes / (1024 * 1024)
                update_describe_file(
                    slot_folder, slot_name, start_dt, end_dt,
                    "running", photo_count, total_size_mb
                )
                last_image = current_image
            except Exception as e:
                print(f"[多媒体] 文件操作失败: {e}")

        elapsed = time.time() - loop_start
        if elapsed < MULTIMEDIA_INTERVAL:
            time.sleep(MULTIMEDIA_INTERVAL - elapsed)

    return photo_count, total_size_bytes


def multimedia_recording_task():
    """多媒体录制主任务（供线程调用）"""
    run_recorder(
        label="[多媒体]",
        save_base_folder=MULTIMEDIA_FOLDER,
        slot_record_func=multimedia_slot_record,
    )


# ======================== 摄像头录制 ========================

def camera_slot_record(rtsp_url, cam_label):
    """
    工厂函数：返回一个时间槽级别的摄像头录制函数。
    每次调用返回的函数闭包捕获了 rtsp_url 和 cam_label。
    """
    def slot_record(slot_folder, slot_name, start_dt, end_dt):
        global running
        photo_count = 0
        total_size_bytes = 0
        ext = get_image_extension()

        # 建立连接
        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            print(f"[{cam_label}] 无法连接摄像头: {rtsp_url}")
            update_describe_file(
                slot_folder, slot_name, start_dt, end_dt, "error", 0, 0.0
            )
            return 0, 0

        print(f"[{cam_label}] 摄像头已连接")

        try:
            while running:
                loop_start = time.time()
                current_time = datetime.now()
                if current_time >= end_dt:
                    break

                # 读取帧
                ret, frame = cap.read()
                if not ret:
                    print(f"[{cam_label}] 读取帧失败，尝试重连...")
                    cap.release()
                    time.sleep(3)
                    cap = cv2.VideoCapture(rtsp_url)
                    if not cap.isOpened():
                        print(f"[{cam_label}] 重连失败，等待后重试")
                        time.sleep(5)
                    continue

                # BGR -> RGB -> PIL Image
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)

                # 保存
                now = datetime.now()
                filename_img = f"{now.strftime('%H.%M.%S')}-{photo_count + 1}{ext}"
                filepath_img = os.path.join(slot_folder, filename_img)
                try:
                    save_image(pil_image, filepath_img)
                    print(f"[{cam_label}] 已保存：{filename_img}")
                    file_size = os.path.getsize(filepath_img)
                    total_size_bytes += file_size
                    photo_count += 1

                    append_to_index(slot_folder, filename_img)
                    total_size_mb = total_size_bytes / (1024 * 1024)
                    update_describe_file(
                        slot_folder, slot_name, start_dt, end_dt,
                        "running", photo_count, total_size_mb
                    )
                except Exception as e:
                    print(f"[{cam_label}] 文件操作失败: {e}")

                elapsed = time.time() - loop_start
                if elapsed < CAMERA_INTERVAL:
                    time.sleep(CAMERA_INTERVAL - elapsed)
        finally:
            cap.release()
            print(f"[{cam_label}] 摄像头连接已释放")

        return photo_count, total_size_bytes

    return slot_record


def camera_recording_task(camera_name, camera_config):
    """摄像头录制主任务（供线程调用）"""
    run_recorder(
        label=f"[{camera_name}]",
        save_base_folder=camera_config["save_folder"],
        slot_record_func=camera_slot_record(
            camera_config["rtsp"], camera_name
        ),
    )


# ======================== 自动清理 ========================

def cleanup_old_files():
    """
    删除超过 RETENTION_DAYS 天的旧文件夹。
    分别扫描 multimedia / blackboardL / blackboardR 三个目录。
    """
    global running
    cutoff = date.today() - timedelta(days=RETENTION_DAYS)
    target_dirs = [MULTIMEDIA_FOLDER, BLACKBOARD_L_FOLDER, BLACKBOARD_R_FOLDER]

    while running:
        for base_dir in target_dirs:
            if not os.path.exists(base_dir):
                continue
            for entry in os.listdir(base_dir):
                dir_path = os.path.join(base_dir, entry)
                if not os.path.isdir(dir_path):
                    continue
                # 文件夹名格式为 YYYY-MM-DD
                try:
                    folder_date = datetime.strptime(entry, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if folder_date < cutoff:
                    try:
                        shutil.rmtree(dir_path)
                        print(f"[清理] 已删除过期目录: {dir_path}")
                    except Exception as e:
                        print(f"[清理] 删除失败: {dir_path}, {e}")

        # 每小时检查一次
        for _ in range(3600):
            if not running:
                return
            time.sleep(1)


# ======================== 系统托盘 ========================

def create_icon_image():
    """生成托盘图标"""
    width, height = 64, 64
    image = Image.new('RGB', (width, height), color=(0, 80, 0))
    dc = ImageDraw.Draw(image)
    dc.rectangle((8, 8, width - 8, height - 8),
                 fill=(0, 80, 0), outline=(255, 255, 255))
    dc.rectangle((14, 14, 50, 30), outline=(255, 255, 255), width=1)
    dc.text((18, 17), "CIO", fill=(255, 255, 255))
    dc.rectangle((14, 34, 50, 50), fill=(200, 0, 0), outline=(255, 255, 255))
    dc.text((18, 37), "REC", fill=(255, 255, 255))
    return image


def exit_program(icon, item):
    """退出程序"""
    global running
    running = False
    icon.stop()
    if sys.stdout and hasattr(sys.stdout, 'close'):
        sys.stdout.close()


def setup_tray():
    """创建托盘图标并启动所有任务线程"""
    icon = pystray.Icon(
        "classroom_iot",
        create_icon_image(),
        "Classroom IoT - 智能板书记录",
        menu=pystray.Menu(
            pystray.MenuItem("退出", exit_program)
        ),
    )

    # ---- 启动多媒体录制线程 ----
    t_multimedia = threading.Thread(target=multimedia_recording_task)
    t_multimedia.daemon = True
    t_multimedia.start()

    # ---- 启动摄像头录制线程 ----
    for cam_name, cam_config in CAMERAS.items():
        t = threading.Thread(
            target=camera_recording_task,
            args=(cam_name, cam_config)
        )
        t.daemon = True
        t.start()

    # ---- 启动清理线程 ----
    t_cleanup = threading.Thread(target=cleanup_old_files)
    t_cleanup.daemon = True
    t_cleanup.start()

    # 阻塞主线程（保持托盘图标运行）
    icon.run()


# ======================== 程序入口 ========================

if __name__ == "__main__":
    print("=" * 50)
    print("Classroom IoT - 智能板书记录系统 v5")
    print(f"启动时间: {datetime.now()}")
    print(f"多媒体截屏间隔: {MULTIMEDIA_INTERVAL}秒")
    print(f"摄像头拍照间隔: {CAMERA_INTERVAL}秒")
    print(f"摄像头图片格式: {CAMERA_IMAGE_FORMAT}")
    print(f"照片保留天数: {RETENTION_DAYS}天")
    print(f"已配置摄像头: {list(CAMERAS.keys())}")
    for name, cfg in CAMERAS.items():
        print(f"  {name}: {cfg['rtsp'][:50]}...")
    print("=" * 50)
    setup_tray()
