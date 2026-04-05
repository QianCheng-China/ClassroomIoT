#!/usr/bin/env python3
"""Classroom IoT - UDP 发现服务模块"""

import socket
import json
import time


def get_local_ip():
    """获取本机局域网 IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def start_discovery(config, stop_flag):
    """UDP 发现服务（动态读取配置，支持热更新别名和端口）
    
    Args:
        config: Config 实例
        stop_flag: threading.Event，设置后停止广播
    """
    local_ip = get_local_ip()
    disc_port = config.discovery_port
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except Exception as e:
        print(f"[发现] 无法创建 UDP 套接字: {e}")
        return

    print(f"[发现] UDP 广播已启动于端口 {disc_port}")

    while stop_flag.is_set():
        try:
            # 【关键修复】每次循环都从 config 对象动态读取最新的别名和端口
            # 这样在 GUI 中修改并保存设置后，无需重启服务，下一秒广播就会生效
            current_alias = config.alias
            current_port = config.http_port

            msg = json.dumps({
                "type": "classroom_iot_discovery",
                "alias": current_alias,
                "name": current_alias,  # App 端 ServerListActivity 读取的是 "name" 字段
                "ip": local_ip,
                "port": current_port,
                "version": "1.0",
            }, ensure_ascii=False).encode("utf-8")

            sock.sendto(msg, ("<broadcast>", disc_port))
        except Exception as e:
            print(f"[发现] 广播异常: {e}")

        # 每 3 秒广播一次（拆分为 0.1 秒的小循环，以便快速响应停止信号）
        for _ in range(30):
            if not stop_flag.is_set():
                break
            time.sleep(0.1)

    sock.close()
    print("[发现] UDP 广播已停止")
