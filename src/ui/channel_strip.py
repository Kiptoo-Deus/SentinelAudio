"""
Mini channel strip widget showing per-channel level and notch status.
Displayed in the channel grid panel for all 16 XR16 channels.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QFont
from .level_meter import LevelMeter


class ChannelStrip(QWidget):
    def __init__(self, channel_num: int, parent=None):
        super().__init__(parent)
        self.channel_num = channel_num
        self._has_notch = False
        self._notch_freq = 0.0
        self._muted = False

        self.setFixedWidth(36)
        self.setMinimumHeight(140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(2)

        self.meter = LevelMeter(parent=self)
        layout.addWidget(self.meter, stretch=1)

        self.label = QLabel(f"{channel_num:02d}")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 10px; color: #5aafcf; font-weight: bold;")
        layout.addWidget(self.label)

    def set_level(self, db: float):
        self.meter.set_level(db)

    def set_notch(self, active: bool, freq: float = 0.0):
        self._has_notch = active
        self._notch_freq = freq
        self.update()

    def set_muted(self, muted: bool):
        self._muted = muted
        alpha = 80 if muted else 255
        self.label.setStyleSheet(
            f"font-size: 10px; color: rgba(90, 175, 207, {alpha}); font-weight: bold;"
        )

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._has_notch:
            p = QPainter(self)
            p.setPen(QPen(QColor(255, 200, 40), 2))
            p.drawRect(1, 1, self.width() - 2, self.height() - 2)
            # Show frequency in tiny text
            if self._notch_freq > 0:
                p.setFont(QFont("Consolas", 7))
                p.setPen(QColor(255, 200, 40))
                label = f"{int(self._notch_freq/1000)}k" if self._notch_freq >= 1000 else str(int(self._notch_freq))
                p.drawText(2, 12, label)
