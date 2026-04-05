#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classroom IoT - 程序入口 (模块化重构版)

启动顺序：隐藏的 tkinter 主窗口 → 后台服务 → 系统托盘
支持参数：
  --_serve_http_only <port>   仅启动 HTTP 服务器（子进程用）
  --autostart                 开机自启动模式，自动启动服务器
"""

import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from PIL import Image, ImageDraw
import pystray


# ======================== 全局异常兜底 ========================

def _global_excepthook(exctype, value, tb):
    import traceback
    log_dir = os.path.dirname(os.path.abspath(__file__))
    if getattr(sys, "frozen", False):
        log_dir = os.path.dirname(sys.executable)
    log_path = os.path.join(log_dir, "error.log")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{__import__('datetime').datetime.now()}]\n")
            f.write("".join(traceback.format_exception(exctype, value, tb)))
            f.write("\n")
    except Exception:
        pass

sys.excepthook = _global_excepthook


# ======================== 子进程入口（PyInstaller 用） ========================

if __name__ == "__main__":
    if "--_serve_http_only" in sys.argv:
        idx = sys.argv.index("--_serve_http_only")
        port = int(sys.argv[idx + 1])
        from server import _serve
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        _serve(port, base_dir)
        sys.exit(0)


# ======================== 托盘图标 ========================

def create_tray_image():
    size = 64
    img = Image.new("RGB", (size, size), (0, 70, 0))
    dc = ImageDraw.Draw(img)
    dc.rectangle((6, 6, size - 6, size - 6),
                 fill=(0, 100, 0), outline=(220, 220, 220))
    dc.text((16, 14), "CIO", fill=(255, 255, 255))
    dc.rectangle((12, 34, 52, 50),
                 fill=(200, 40, 40), outline=(220, 220, 220))
    dc.text((16, 37), "REC", fill=(255, 255, 255))
    return img


# ======================== 程序主入口 ========================

def main():
    print("=" * 55)
    print("  Classroom IoT Server v2.0")
    print("=" * 55)

    # 检测是否为开机自启动模式
    is_autostart = "--autostart" in sys.argv

    print("  [1/4] 加载配置...")
    from config import Config
    config = Config()

    print("  [2/4] 初始化服务组件...")
    from server import IoTServer
    from discovery import start_discovery
    from recorder import RecorderManager
    from gui import ManagementGUI

    server = IoTServer(config)
    recorder = RecorderManager(config)
    discovery_flag = threading.Event()
    discovery_flag.set()

    # 启动 UDP 发现
    threading.Thread(
        target=start_discovery,
        args=(config, discovery_flag),
        daemon=True,
    ).start()
    
    print("  [录制] 自动启动录制引擎...")
    recorder.start()

    # 创建隐藏的 tkinter 根窗口
    print("  [3/4] 创建主窗口...")
    root = tk.Tk()
    root.withdraw()

    # 共享引用
    gui_ref = [None]
    icon_ref = [None]

    # ---- 托盘菜单回调 ----

    def on_open(tray_icon, item):
        try:
            if gui_ref[0] is None:
                gui_ref[0] = ManagementGUI(
                    root, config, server, recorder)
            root.after(0, gui_ref[0].show)
        except tk.TclError:
            pass

    def on_exit(tray_icon, item):
        print("  [退出] 正在停止所有服务...")
        recorder.stop()
        server.stop()
        discovery_flag.clear()
        try:
            root.after_idle(root.quit)
        except tk.TclError:
            pass
        try:
            icon_ref[0].stop()
        except Exception:
            pass

    # 创建并启动系统托盘
    print("  [4/4] 启动系统托盘...")
    tray_icon = pystray.Icon(
        name="classroom_iot",
        icon=create_tray_image(),
        hover_text=f"Classroom IoT - {config.alias}",
        menu=pystray.Menu(
            pystray.MenuItem("打开管理窗口", on_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", on_exit),
        ),
    )
    icon_ref[0] = tray_icon

    tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
    tray_thread.start()

    print("=" * 55)
    print("  程序已启动，最小化到系统托盘")
    print("  右键托盘图标 → 打开管理窗口")
    print("=" * 55)

    # 如果是开机自启动模式，延迟 3 秒后自动启动服务器
    # （等待网络就绪）
    if is_autostart:
        print("  [自启动] 3 秒后将自动启动服务器...")

        def _auto_start_server():
            try:
                server.start()
                print("  [自启动] 服务器已自动启动")
            except Exception as e:
                print(f"  [自启动] 启动失败: {e}")

        root.after(3000, _auto_start_server)

    # 主线程运行 tkinter 事件循环
    root.mainloop()

    # 清理
    print("  [清理] 正在退出...")
    try:
        tray_icon.stop()
    except Exception:
        pass
    try:
        tray_thread.join(timeout=3)
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass
    print("  已退出")


if __name__ == "__main__":
    main()
