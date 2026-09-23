# -*- coding: utf-8 -*-
"""
PetFactory 坐标标定工具（高级/调试用）
================================================
作用：处理好素材后，在 idle.png 上点选每个键位和鼠标左右键，
      自动生成可填入角色 config.json 的坐标配置。

用法：
  python tools/calibrate_gui.py <character_dir>
  - 鼠标移动：实时显示帧坐标
  - 左键点击：弹出框输入标签（键盘键输入该字符，如 q/a/1，空格输入 space；
              鼠标输入 mouse_left/mouse_right/mouse_mid）
  - 右键点击：撤销上一个点
  - R 键：清空所有点
  - S 键：把坐标保存为该角色目录下的 config.json（合并已有配置）
"""
import os
import sys
import json

# 确保项目根目录在 sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QMessageBox
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PyQt5.QtCore import Qt, QPoint

from config import load_character_config, save_character_config


class Calibrator(QWidget):
    def __init__(self, char_dir):
        super().__init__()
        self.char_dir = char_dir
        self.cfg = load_character_config(char_dir)
        self.setWindowTitle('坐标标定工具：左键标点并命名，右键撤销，R清空，S保存')
        img_path = os.path.join(self.cfg['_assets_dir'], 'idle.png')
        src = QPixmap(img_path)
        if src.isNull():
            QMessageBox.critical(self, '错误', f'找不到 {img_path}，请先生成素材。')
            sys.exit(1)
        self.fw, self.fh = src.width(), src.height()
        screen = QApplication.primaryScreen().availableGeometry()
        self.disp_scale = min((screen.width() - 120) / self.fw,
                              (screen.height() - 120) / self.fh, 1.0)
        dw, dh = int(self.fw * self.disp_scale), int(self.fh * self.disp_scale)
        self.setFixedSize(dw, dh)
        self.pix = src.scaled(dw, dh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.points = []
        self.setMouseTracking(True)
        self.hover = None

    def _to_frame(self, pos):
        return int(pos.x() / self.disp_scale), int(pos.y() / self.disp_scale)

    def mouseMoveEvent(self, e):
        self.hover = self._to_frame(e.pos())
        self.update()

    def mousePressEvent(self, e):
        fx, fy = self._to_frame(e.pos())
        if e.button() == Qt.LeftButton:
            label, ok = QInputDialog.getText(
                self, '命名该点',
                '坐标 (%d, %d)\n输入标签（键盘键如 q/a/1，空格=space；鼠标=mouse_left/right/mid）：' % (fx, fy))
            if ok and label.strip():
                self.points.append((label.strip(), fx, fy))
                self.update()
        elif e.button() == Qt.RightButton and self.points:
            self.points.pop()
            self.update()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_R:
            self.points.clear()
            self.update()
        elif e.key() == Qt.Key_S:
            self.save()

    def save(self):
        keys, mouse = {}, {}
        for label, x, y in self.points:
            if label.startswith('mouse_'):
                mouse[label] = [x, y]
            else:
                keys[label] = [x, y]
        # 更新 config
        if keys:
            # 重建 key_pos 风格：直接存 special_pos 和 row 信息
            for k, v in keys.items():
                if k == 'space':
                    self.cfg['keyboard']['space_x'] = v[0]
                elif k in ('esc', 'backspace', 'enter', 'shift_l', 'shift_r',
                           'ctrl_l', 'alt_l', 'cmd', 'ctrl_r', 'alt_r',
                           'up', 'down', 'left', 'right'):
                    self.cfg['special_pos'][k] = v
        for name, v in mouse.items():
            key = name.replace('mouse_', '')
            if key in self.cfg['mouse']:
                self.cfg['mouse'][key] = v
        save_character_config(self.char_dir, self.cfg)
        QMessageBox.information(self, '已保存',
                                f'坐标已保存到\n{os.path.join(self.char_dir, "config.json")}')

    def paintEvent(self, e):
        p = QPainter(self)
        p.drawPixmap(0, 0, self.pix)
        pen = QPen(QColor(255, 60, 60), 2)
        p.setPen(pen)
        p.setFont(QFont('Arial', 12, QFont.Bold))
        for i, (label, fx, fy) in enumerate(self.points):
            x, y = int(fx * self.disp_scale), int(fy * self.disp_scale)
            p.drawEllipse(QPoint(x, y), 8, 8)
            p.drawText(x + 10, y - 10, '%d:%s' % (i + 1, label))
        if self.hover:
            p.setPen(QPen(QColor(0, 120, 255), 1))
            p.drawLine(self.hover[0] * self.disp_scale, 0,
                       self.hover[0] * self.disp_scale, self.height())
            p.drawLine(0, self.hover[1] * self.disp_scale,
                       self.width(), self.hover[1] * self.disp_scale)
            p.setPen(QColor(0, 80, 200))
            p.drawText(self.hover[0] * self.disp_scale + 12,
                       self.hover[1] * self.disp_scale + 18,
                       '(%d, %d)' % self.hover)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python calibrate_gui.py <character_dir>')
        print('示例: python calibrate_gui.py ../characters/sample')
        sys.exit(1)
    app = QApplication(sys.argv)
    w = Calibrator(os.path.abspath(sys.argv[1]))
    w.show()
    sys.exit(app.exec_())
