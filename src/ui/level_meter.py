"""
Vertical LED-style level meter widget.
Segments are colored green → yellow → red with peak hold.
"""

import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPainter, QColor, QPen


SEGMENT_COLORS = [
    # (threshold_db, r, g, b)
    (-60, 30, 160, 80),
    (-36, 40, 200, 80),
    (-18, 80, 220, 60),
    (-12, 180, 220, 40),
    (-6,  220, 180, 30),
    (-3,  220, 100, 20),
    (0,   220,  40, 30),
]


class LevelMeter(QWidget):
    N_SEGMENTS = 40
    DB_MIN = -60.0
    DB_MAX = 0.0

    def __init__(self, label: str = "", parent=None):
        super().__init__(parent)
        self.label = label
        self.setFixedWidth(24)
        self.setMinimumHeight(120)
        self._level_db = -60.0
        self._peak_db = -60.0
        self._peak_hold_frames = 0
        self.PEAK_HOLD_FRAMES = 30

    def set_level(self, db: float):
        self._level_db = max(self.DB_MIN, min(self.DB_MAX, db))
        if self._level_db >= self._peak_db:
            self._peak_db = self._level_db
            self._peak_hold_frames = self.PEAK_HOLD_FRAMES
        else:
            self._peak_hold_frames -= 1
            if self._peak_hold_frames <= 0:
                self._peak_db = max(self.DB_MIN, self._peak_db - 0.5)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        seg_h = max(2, (h - 4) // self.N_SEGMENTS - 1)
        gap = 1

        p.fillRect(0, 0, w, h, QColor(10, 13, 15))

        level_norm = (self._level_db - self.DB_MIN) / (self.DB_MAX - self.DB_MIN)
        peak_norm  = (self._peak_db  - self.DB_MIN) / (self.DB_MAX - self.DB_MIN)
        lit_count  = int(level_norm * self.N_SEGMENTS)
        peak_seg   = int(peak_norm * self.N_SEGMENTS)

        for i in range(self.N_SEGMENTS):
            seg_db = self.DB_MIN + (i / self.N_SEGMENTS) * (self.DB_MAX - self.DB_MIN)
            color = self._color_for_db(seg_db)
            y = h - 2 - (i + 1) * (seg_h + gap)
            rect = QRect(2, y, w - 4, seg_h)

            if i < lit_count:
                p.fillRect(rect, QColor(*color))
            elif i == peak_seg:
                p.fillRect(rect, QColor(*color))
            else:
                p.fillRect(rect, QColor(color[0] // 6, color[1] // 6, color[2] // 6))

        # Label
        if self.label:
            p.setPen(QPen(QColor(90, 130, 160)))
            p.setFont(self.font())
            p.drawText(0, h - 1, self.label)

    def _color_for_db(self, db):
        color = SEGMENT_COLORS[0][1:]
        for threshold, r, g, b in SEGMENT_COLORS:
            if db >= threshold:
                color = (r, g, b)
        return color
