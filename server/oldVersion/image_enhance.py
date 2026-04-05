#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classroom IoT - 摄像头图像增强模块
在保存摄像头照片之前调用，提升黑板/白板内容可读性。

使用方法:
    from image_enhance import enhance_blackboard_image
    enhanced = enhance_blackboard_image(frame)
"""

import cv2
import numpy as np


def _automatic_white_balance(img):
    """
    简易自动白平衡 (Gray World 假设)
    适用于教室日光灯 / 窗户混合光源环境。
    """
    result = img.copy().astype(np.float32)
    b, g, r = result[:, :, 0], result[:, :, 1], result[:, :, 2]
    avg_b, avg_g, avg_r = b.mean(), g.mean(), r.mean()
    avg_gray = (avg_b + avg_g + avg_r) / 3.0
    if avg_gray < 1e-6:
        return img
    scale_b = avg_gray / avg_b
    scale_g = avg_gray / avg_g
    scale_r = avg_gray / avg_r
    # 限制拉伸幅度，避免过曝
    scale_b = np.clip(scale_b, 0.8, 1.2)
    scale_g = np.clip(scale_g, 0.8, 1.2)
    scale_r = np.clip(scale_r, 0.8, 1.2)
    result[:, :, 0] = np.clip(b * scale_b, 0, 255)
    result[:, :, 1] = np.clip(g * scale_g, 0, 255)
    result[:, :, 2] = np.clip(r * scale_r, 0, 255)
    return result.astype(np.uint8)


def _clahe_luminance(img, clip_limit=2.0, grid_size=8):
    """
    在 LAB 色彩空间的 L 通道上做 CLAHE，
    增强局部对比度，使粉笔/白板字迹更清晰。
    """
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(grid_size, grid_size))
    l = clahe.apply(l)
    lab = cv2.merge([l, a, b])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def _sharpen(img, strength=0.6):
    """
    Unsharp Mask 锐化，让文字边缘更锐利。
    strength: 0.0 ~ 1.0，推荐 0.4-0.8
    """
    blurred = cv2.GaussianBlur(img, (0, 0), 3)
    sharpened = cv2.addWeighted(img, 1.0 + strength, blurred, -strength, 0)
    return sharpened


def _light_denoise(img, strength=5):
    """
    轻度去噪，减少传感器噪声但不模糊文字。
    strength: OpenCV fastNlMeansDenoisingColored 的 h 参数，推荐 3-10
    """
    denoised = cv2.fastNlMeansDenoisingColored(img, None, strength, strength, 7, 21)
    return denoised


def enhance_blackboard_image(
    frame,
    enable_white_balance=True,
    enable_clahe=True,
    clahe_clip_limit=2.0,
    enable_sharpen=True,
    sharpen_strength=0.6,
    enable_denoise=False,
    denoise_strength=5,
):
    """
    完整的黑板图像增强管线。
    建议调用顺序: 白平衡 → 去噪 → CLAHE → 锐化

    参数
    ----------
    frame : numpy.ndarray
        BGR 格式的摄像头原始帧 (来自 cv2.VideoCapture.read())
    enable_white_balance : bool
        是否启用自动白平衡
    enable_clahe : bool
        是否启用 CLAHE 对比度增强
    clahe_clip_limit : float
        CLAHE 对比度限制，1.0-4.0，值越大对比度越强
    enable_sharpen : bool
        是否启用锐化
    sharpen_strength : float
        锐化强度 0.0-1.0
    enable_denoise : bool
        是否启用去噪 (会增加处理耗时约 50-100ms)
    denoise_strength : int
        去噪强度 3-10

    返回
    -------
    numpy.ndarray : 增强后的 BGR 图像
    """
    img = frame.copy()

    # 1. 白平衡（最先做，为后续处理提供正确的色彩基准）
    if enable_white_balance:
        img = _automatic_white_balance(img)

    # 2. 轻度去噪（可选，比较耗时）
    if enable_denoise:
        img = _light_denoise(img, strength=denoise_strength)

    # 3. CLAHE 对比度增强（核心步骤）
    if enable_clahe:
        img = _clahe_luminance(img, clip_limit=clahe_clip_limit)

    # 4. 锐化（最后做，避免放大噪声）
    if enable_sharpen:
        img = _sharpen(img, strength=sharpen_strength)

    return img


# ---- 快速测试 ----
if __name__ == "__main__":
    print("image_enhance.py - 黑板图像增强模块")
    print("使用方法:")
    print("  from image_enhance import enhance_blackboard_image")
    print("  enhanced = enhance_blackboard_image(frame)")
