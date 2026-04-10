#!/usr/bin/env python3
"""Classroom IoT - UDP 发现服务模块（多网段优化版）"""
import socket
import json
import time
import re
import platform
import subprocess

def get_local_ip():
    """获取本机默认局域网 IP（仅作兜底用）"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def _calculate_broadcast(ip, mask):
    """通过 IP 和子网掩码计算广播地址"""
    try:
        ip_int = sum([int(x) << (8 * i) for i, x in enumerate(reversed(ip.split(".")))])
        mask_int = sum([int(x) << (8 * i) for i, x in enumerate(reversed(mask.split(".")))])
        bcast_int = (ip_int & mask_int) | (~mask_int & 0xFFFFFFFF)
        return ".".join([str((bcast_int >> (8 * i)) & 0xFF) for i in reversed(range(4))])
    except Exception:
        return "255.255.255.255"

def get_all_broadcasts():
    """零依赖获取本机所有网卡的 (本地IP, 广播地址) 列表"""
    broadcasts = []
    system = platform.system()
    
    try:
        if system == "Windows":
            result = subprocess.check_output(["ipconfig"], text=True, errors="ignore")
            # 匹配 IPv4 地址和子网掩码
            ip_pattern = re.compile(
                r"IPv4 Address[\. ]*: ([\d\.]+)\s+Subnet Mask[\. ]*: ([\d\.]+)", 
                re.IGNORECASE
            )
            for match in ip_pattern.finditer(result):
                ip = match.group(1)
                mask = match.group(2)
                if ip.startswith("127.") or mask == "0.0.0.0":
                    continue
                bcast = _calculate_broadcast(ip, mask)
                broadcasts.append((ip, bcast))
        else:
            # Linux / macOS 兼容
            try:
                result = subprocess.check_output(["ifconfig"], text=True, errors="ignore")
                iface_pattern = re.compile(
                    r"^([a-zA-Z0-9]+):.*?(?:inet\s+addr:|inet\s+)([\d\.]+).*?(?:Bcast:|broadcast\s+)([\d\.]+)", 
                    re.IGNORECASE | re.DOTALL | re.MULTILINE
                )
                for match in iface_pattern.finditer(result):
                    ip = match.group(2)
                    bcast = match.group(3)
                    if ip.startswith("127.") or bcast == "0.0.0.0": continue
                    broadcasts.append((ip, bcast))
            except FileNotFoundError:
                # 如果没有 ifconfig，尝试解析 ip addr
                result = subprocess.check_output(["ip", "addr"], text=True, errors="ignore")
                ip_pattern = re.compile(r"inet ([\d\.]+)/(\d+)", re.IGNORECASE)
                for match in ip_pattern.finditer(result):
                    ip = match.group(1)
                    prefix = int(match.group(2))
                    if ip.startswith("127.") or prefix == 32: continue
                    mask_int = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
                    mask = ".".join([str((mask_int >> (8 * i)) & 0xFF) for i in reversed(range(4))])
                    bcast = _calculate_broadcast(ip, mask)
                    broadcasts.append((ip, bcast))
                    
    except Exception as e:
        print(f"[发现] 获取网卡信息失败: {e}")
        
    # 兜底：如果什么都没获取到，使用默认的全网广播
    if not broadcasts:
        broadcasts.append((get_local_ip(), "255.255.255.255"))
        
    return broadcasts

def start_discovery(config, stop_flag):
    """UDP 发现服务（多网段广播，动态读取配置）"""
    broadcasts = get_all_broadcasts()
    disc_port = config.discovery_port
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except Exception as e:
        print(f"[发现] 无法创建 UDP 套接字: {e}")
        return

    print(f"[发现] UDP 广播已启动于端口 {disc_port}")
    for ip, bcast in broadcasts:
        print(f"[发现] 监听网段: {ip} -> {bcast}")

    while stop_flag.is_set():
        try:
            current_alias = config.alias
            current_port = config.http_port
            
            # 遍历所有网段，分别发送带有对应 IP 的广播包
            # 这样 App 在任何网段都能收到，并且拿到的是正确的同网段 IP
            for local_ip, bcast_addr in broadcasts:
                msg = json.dumps({
                    "type": "classroom_iot_discovery",
                    "alias": current_alias,
                    "name": current_alias, 
                    "ip": local_ip, 
                    "port": current_port,
                    "version": "1.0",
                }, ensure_ascii=False).encode("utf-8")
                
                sock.sendto(msg, (bcast_addr, disc_port))
        except Exception as e:
            print(f"[发现] 广播异常: {e}")
            
        # 每 3 秒广播一次（拆分为 0.1 秒的小循环，以便快速响应停止信号）
        for _ in range(30):
            if not stop_flag.is_set(): break
            time.sleep(0.1)
            
    sock.close()
    print("[发现] UDP 广播已停止")
