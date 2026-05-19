"""
Real-time spectrum analyzer widget.

Draws:
  - Gradient filled frequency spectrum (cyan → red by amplitude)
  - Peak hold line
  - Notch filter markers (amber triangles + depth lines)
  - Candidate frequency markers (orange)
  - Frequency / dB grid with labeled axes
  - Danger zone threshold line
"""

import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect, QPoint, QTimer
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient,
    QFont, QFontMetrics, QPolygon, QPainterPath,
)
from .styles import (
    COLOR_BG, COLOR_GRID, COLOR_SPECTRUM_LO, COLOR_SPECTRUM_HI,
    COLOR_NOTCH, COLOR_CANDIDATE, COLOR_TEXT, COLOR_ACCENT, COLOR_DANGER,
)


def _lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return QColor(
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


class SpectrumWidget(QWidget):
    # Frequency axis is log-scaled 20 Hz – 20 kHz
    FREQ_MIN = 20.0
    FREQ_MAX = 20000.0
    DB_MIN = -80.0
    DB_MAX = 0.0
    DB_DANGER = -20.0

    GRID_FREQS = [31, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    GRID_DBS = [-72, -60, -48, -36, -24, -12, 0]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 220)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        self._frequencies: np.ndarray = np.array([])
        self._magnitude_db: np.ndarray = np.array([])
        self._peak_hold: np.ndarray = np.array([])
        self._peak_decay_rate = 0.3          # dB per frame
        self._notch_freqs: list[tuple] = []  # (freq_hz, depth_db)
        self._candidate_freqs: list[float] = []

        self._font_small = QFont("Consolas", 8)
        self._font_label = QFont("Segoe UI", 8)

    # ------------------------------------------------------------------ #
    # Public update methods called from main thread via Qt signals
    # ------------------------------------------------------------------ #

    def update_spectrum(self, frequencies: np.ndarray, magnitude_db: np.ndarray):
        self._frequencies = frequencies
        self._magnitude_db = magnitude_db

        if len(self._peak_hold) != len(magnitude_db):
            self._peak_hold = magnitude_db.copy()
        else:
            # Hold peaks, decay slowly
            self._peak_hold = np.where(
                magnitude_db > self._peak_hold,
                magnitude_db,
                self._peak_hold - self._peak_decay_rate,
            )
            np.clip(self._peak_hold, self.DB_MIN, self.DB_MAX, out=self._peak_hold)

        self.update()

    def set_notch_markers(self, notch_list: list[tuple]):
        """notch_list: [(freq_hz, depth_db), ...]"""
        self._notch_freqs = notch_list
        self.update()

    def set_candidate_markers(self, freq_list: list[float]):
        self._candidate_freqs = freq_list
        self.update()

    # ------------------------------------------------------------------ #
    # Paint
    # ------------------------------------------------------------------ #

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        margin_l, margin_r = 52, 16
        margin_t, margin_b = 12, 36
        plot_w = w - margin_l - margin_r
        plot_h = h - margin_t - margin_b

        # Background
        painter.fillRect(0, 0, w, h, QColor(*COLOR_BG))

        # Plot area background
        plot_rect = QRect(margin_l, margin_t, plot_w, plot_h)
        painter.fillRect(plot_rect, QColor(12, 18, 24))

        self._draw_grid(painter, margin_l, margin_t, plot_w, plot_h)
        self._draw_danger_line(painter, margin_l, margin_t, plot_w, plot_h)

        if len(self._frequencies) > 0 and len(self._magnitude_db) > 0:
            self._draw_spectrum(painter, margin_l, margin_t, plot_w, plot_h)
            self._draw_peak_hold(painter, margin_l, margin_t, plot_w, plot_h)

        self._draw_notch_markers(painter, margin_l, margin_t, plot_w, plot_h)
        self._draw_candidate_markers(painter, margin_l, margin_t, plot_w, plot_h)

        # Border
        painter.setPen(QPen(QColor(*COLOR_GRID), 1))
        painter.drawRect(plot_rect)

        self._draw_axes(painter, margin_l, margin_t, plot_w, plot_h)

    def _freq_to_x(self, freq, x0, pw):
        if freq <= 0:
            return x0
        log_pos = (np.log10(freq) - np.log10(self.FREQ_MIN)) / (
            np.log10(self.FREQ_MAX) - np.log10(self.FREQ_MIN)
        )
        return x0 + int(log_pos * pw)

    def _db_to_y(self, db, y0, ph):
        norm = (db - self.DB_MAX) / (self.DB_MIN - self.DB_MAX)
        return y0 + int(norm * ph)

    def _draw_grid(self, p, x0, y0, pw, ph):
        pen = QPen(QColor(*COLOR_GRID), 1, Qt.PenStyle.DotLine)
        p.setPen(pen)
        for f in self.GRID_FREQS:
            x = self._freq_to_x(f, x0, pw)
            p.drawLine(x, y0, x, y0 + ph)
        for db in self.GRID_DBS:
            y = self._db_to_y(db, y0, ph)
            p.drawLine(x0, y, x0 + pw, y)

    def _draw_danger_line(self, p, x0, y0, pw, ph):
        y = self._db_to_y(self.DB_DANGER, y0, ph)
        pen = QPen(QColor(180, 40, 40, 80), 1, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawLine(x0, y, x0 + pw, y)

    def _draw_spectrum(self, p, x0, y0, pw, ph):
        freqs = self._frequencies
        mags = self._magnitude_db
        y_baseline = y0 + ph

        path = QPainterPath()
        path.moveTo(x0, y_baseline)

        xs = []
        ys = []
        for i, (f, m) in enumerate(zip(freqs, mags)):
            if f < self.FREQ_MIN or f > self.FREQ_MAX:
                continue
            x = self._freq_to_x(f, x0, pw)
            y = self._db_to_y(m, y0, ph)
            xs.append(x)
            ys.append(y)

        if not xs:
            return

        path.moveTo(xs[0], y_baseline)
        for x, y in zip(xs, ys):
            path.lineTo(x, y)
        path.lineTo(xs[-1], y_baseline)
        path.closeSubpath()

        grad = QLinearGradient(0, y0, 0, y0 + ph)
        grad.setColorAt(0.0, QColor(*COLOR_SPECTRUM_HI, 220))
        grad.setColorAt(0.5, QColor(60, 140, 180, 180))
        grad.setColorAt(1.0, QColor(*COLOR_SPECTRUM_LO, 60))
        p.fillPath(path, QBrush(grad))

        # Outline
        p.setPen(QPen(QColor(*COLOR_ACCENT, 180), 1))
        outline = QPainterPath()
        outline.moveTo(xs[0], ys[0])
        for x, y in zip(xs[1:], ys[1:]):
            outline.lineTo(x, y)
        p.drawPath(outline)

    def _draw_peak_hold(self, p, x0, y0, pw, ph):
        freqs = self._frequencies
        peaks = self._peak_hold
        pen = QPen(QColor(200, 200, 100, 140), 1)
        p.setPen(pen)
        prev_x, prev_y = None, None
        for f, m in zip(freqs, peaks):
            if f < self.FREQ_MIN or f > self.FREQ_MAX:
                continue
            x = self._freq_to_x(f, x0, pw)
            y = self._db_to_y(m, y0, ph)
            if prev_x is not None and abs(x - prev_x) < 4:
                p.drawLine(prev_x, prev_y, x, y)
            prev_x, prev_y = x, y

    def _draw_notch_markers(self, p, x0, y0, pw, ph):
        for freq, depth_db in self._notch_freqs:
            x = self._freq_to_x(freq, x0, pw)
            # Vertical line from top
            pen = QPen(QColor(*COLOR_NOTCH, 180), 1, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawLine(x, y0, x, y0 + ph)

            # Depth indicator
            y_depth = self._db_to_y(depth_db, y0, ph)
            p.setPen(QPen(QColor(*COLOR_NOTCH), 2))
            p.drawLine(x - 6, y_depth, x + 6, y_depth)

            # Triangle marker at top
            tri = QPolygon([
                QPoint(x, y0 + 4),
                QPoint(x - 5, y0 - 4),
                QPoint(x + 5, y0 - 4),
            ])
            p.setBrush(QBrush(QColor(*COLOR_NOTCH)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPolygon(tri)

            # Label
            p.setPen(QPen(QColor(*COLOR_NOTCH)))
            p.setFont(self._font_small)
            label = f"{freq/1000:.1f}k" if freq >= 1000 else f"{freq:.0f}"
            p.drawText(x - 14, y0 - 8, label)

    def _draw_candidate_markers(self, p, x0, y0, pw, ph):
        pen = QPen(QColor(200, 120, 40, 160), 1, Qt.PenStyle.DotLine)
        p.setPen(pen)
        for freq in self._candidate_freqs:
            x = self._freq_to_x(freq, x0, pw)
            p.drawLine(x, y0, x, y0 + ph)
            # Small triangle
            tri = QPolygon([
                QPoint(x, y0 + ph - 2),
                QPoint(x - 4, y0 + ph + 5),
                QPoint(x + 4, y0 + ph + 5),
            ])
            p.setBrush(QBrush(QColor(200, 120, 40, 160)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPolygon(tri)

    def _draw_axes(self, p, x0, y0, pw, ph):
        p.setFont(self._font_small)

        # Frequency labels
        p.setPen(QPen(QColor(*COLOR_TEXT, 180)))
        for f in self.GRID_FREQS:
            x = self._freq_to_x(f, x0, pw)
            label = f"{f//1000}k" if f >= 1000 else str(f)
            fm = QFontMetrics(self._font_small)
            tw = fm.horizontalAdvance(label)
            p.drawText(x - tw // 2, y0 + ph + 18, label)

        # dB labels
        for db in self.GRID_DBS:
            y = self._db_to_y(db, y0, ph)
            label = f"{db}"
            fm = QFontMetrics(self._font_small)
            tw = fm.horizontalAdvance(label)
            p.drawText(x0 - tw - 6, y + 4, label)

        # Axis unit labels
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(QPen(QColor(*COLOR_ACCENT, 120)))
        p.drawText(x0 + pw // 2 - 20, y0 + ph + 30, "FREQUENCY (Hz)")
        p.save()
        p.translate(12, y0 + ph // 2 + 10)
        p.rotate(-90)
        p.drawText(0, 0, "dBFS")
        p.restore()
