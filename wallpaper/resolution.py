# -*- coding: utf-8 -*-
"""
resolution.py — 显示器分辨率与宽高比探测模块

依赖 PyQt5，通过 QScreen 读取逻辑分辨率与 DPI，
并把真实宽高比归一到标准比例字符串（16:9 / 16:10 / 21:9 等），
供后续图生视频请求使用。

注意：
- 使用 screen.geometry() 获取完整（含任务栏）逻辑分辨率，而非 availableGeometry()。
- 由于存在系统 DPI 缩放，geometry() 返回的是「逻辑像素」，与物理像素不同；
  这里统一以逻辑分辨率作为视频画幅依据，避免重复缩放。
"""
import os
import sys

from PyQt5.QtWidgets import QApplication


# 标准宽高比表：ratio_str -> 宽/高 的浮点值
# 说明：宽屏比例用 宽/高；竖屏比例用 高/宽（即 width/height < 1）
_STANDARD_RATIOS = {
    '21:9': 2.333,
    '16:9': 1.778,
    '16:10': 1.6,
    '4:3': 1.333,
    '1:1': 1.0,
    '9:16': 0.563,
}


def _classify_ratio(width, height):
    """根据 width/height 浮点值，匹配最近的标准比例字符串。"""
    if width <= 0 or height <= 0:
        return '16:9'
    actual = width / height
    best_str = '16:9'
    best_diff = float('inf')
    for name, std in _STANDARD_RATIOS.items():
        diff = abs(actual - std)
        if diff < best_diff:
            best_diff = diff
            best_str = name
    return best_str


class ResolutionDetector:
    """封装 PyQt5 屏幕信息读取，单实例即可，内部持有一个 QApplication。"""

    def __init__(self):
        # QApplication 在一个进程中只能有一个实例；
        # 若外部已创建则复用，否则创建一个无窗口的离屏实例。
        self._app = QApplication.instance()
        if self._app is None:
            # 带参数启动，避免部分平台告警
            self._app = QApplication(sys.argv)

    def _screen_to_dict(self, screen):
        """把一个 QScreen 转换成统一的分辨率字典。"""
        # geometry() 返回完整逻辑分辨率（含任务栏区域）
        geo = screen.geometry()
        width = geo.width()
        height = geo.height()

        # logicalDotsPerInch：逻辑 DPI（默认 96，受缩放影响时仍为逻辑值）
        try:
            dpi = int(round(screen.logicalDotsPerInch()))
        except Exception:
            dpi = 96

        ratio_str = _classify_ratio(width, height)
        is_portrait = width < height

        return {
            'width': width,
            'height': height,
            'dpi': dpi,
            'ratio_str': ratio_str,
            'is_portrait': is_portrait,
        }

    def get_primary(self):
        """获取主屏分辨率信息。"""
        screen = self._app.primaryScreen()
        if screen is None:
            # 兜底：没有主屏时返回一个默认值
            return {
                'width': 1920,
                'height': 1080,
                'dpi': 96,
                'ratio_str': '16:9',
                'is_portrait': False,
            }
        return self._screen_to_dict(screen)

    def get_all_monitors(self):
        """获取所有显示器的分辨率信息列表。"""
        screens = self._app.screens()
        return [self._screen_to_dict(s) for s in screens]

    def get_target_ratio(self):
        """返回主屏的标准比例字符串，用于图生视频请求。"""
        return self.get_primary().get('ratio_str', '16:9')


# 简单自测：直接运行本文件时打印主屏与所有显示器信息
if __name__ == '__main__':
    det = ResolutionDetector()
    print('主屏：', det.get_primary())
    print('所有显示器：')
    for i, m in enumerate(det.get_all_monitors()):
        print(f'  [{i}] {m}')
    print('目标比例：', det.get_target_ratio())
