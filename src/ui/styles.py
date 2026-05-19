"""
Dark professional stylesheet for Sentinel Audio.
Uses a near-black background with cyan/amber accent palette.
"""

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0a0d0f;
    color: #c8d8e8;
    font-family: "Segoe UI", "Inter", "Helvetica Neue", sans-serif;
    font-size: 13px;
}

QGroupBox {
    border: 1px solid #1e3a4a;
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    color: #5aafcf;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QPushButton {
    background-color: #0f1e2a;
    border: 1px solid #1e3a4a;
    border-radius: 4px;
    color: #5aafcf;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: bold;
    letter-spacing: 0.8px;
}

QPushButton:hover {
    background-color: #122534;
    border-color: #5aafcf;
    color: #7fcfe8;
}

QPushButton:pressed {
    background-color: #1a3545;
}

QPushButton:disabled {
    color: #2a4555;
    border-color: #142030;
}

QPushButton#btn_arm {
    background-color: #0a2010;
    border-color: #1a6030;
    color: #30c060;
    font-size: 14px;
    padding: 10px 24px;
}

QPushButton#btn_arm:hover {
    background-color: #0f2a18;
    border-color: #30c060;
}

QPushButton#btn_arm[armed="true"] {
    background-color: #300a0a;
    border-color: #c03030;
    color: #e04040;
}

QComboBox {
    background-color: #0f1e2a;
    border: 1px solid #1e3a4a;
    border-radius: 4px;
    color: #c8d8e8;
    padding: 4px 8px;
    min-height: 26px;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #0f1e2a;
    border: 1px solid #1e3a4a;
    selection-background-color: #1a3a5a;
    color: #c8d8e8;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #1e3a4a;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #5aafcf;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QSlider::sub-page:horizontal {
    background: #2a7a9a;
    border-radius: 2px;
}

QLabel {
    color: #c8d8e8;
}

QLabel#label_status_value {
    font-size: 18px;
    font-weight: bold;
}

QLabel#label_big_freq {
    font-size: 36px;
    font-weight: bold;
    color: #e05050;
    font-family: "Consolas", "Courier New", monospace;
}

QLabel#label_resp_time {
    font-size: 22px;
    font-weight: bold;
    color: #5aafcf;
    font-family: "Consolas", "Courier New", monospace;
}

QTableWidget {
    background-color: #0a0d0f;
    border: 1px solid #1e3a4a;
    gridline-color: #111e28;
    selection-background-color: #1a3a5a;
    color: #c8d8e8;
}

QTableWidget::item {
    padding: 4px 8px;
    border: none;
}

QHeaderView::section {
    background-color: #0f1e2a;
    color: #5aafcf;
    border: none;
    border-bottom: 1px solid #1e3a4a;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    text-transform: uppercase;
}

QScrollBar:vertical {
    background: #0a0d0f;
    width: 8px;
    border: none;
}

QScrollBar::handle:vertical {
    background: #1e3a4a;
    border-radius: 4px;
    min-height: 20px;
}

QTabWidget::pane {
    border: 1px solid #1e3a4a;
    border-radius: 4px;
}

QTabBar::tab {
    background: #0f1e2a;
    border: 1px solid #1e3a4a;
    border-bottom: none;
    padding: 6px 16px;
    color: #5a7f9f;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background: #0a0d0f;
    color: #5aafcf;
    border-bottom: 1px solid #0a0d0f;
}

QCheckBox {
    color: #c8d8e8;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #1e3a4a;
    border-radius: 3px;
    background: #0f1e2a;
}

QCheckBox::indicator:checked {
    background: #2a7a9a;
    border-color: #5aafcf;
}

QLineEdit {
    background-color: #0f1e2a;
    border: 1px solid #1e3a4a;
    border-radius: 4px;
    color: #c8d8e8;
    padding: 4px 8px;
}

QLineEdit:focus {
    border-color: #5aafcf;
}

QSplitter::handle {
    background: #1e3a4a;
    width: 1px;
    height: 1px;
}
"""

# Color constants used by custom widgets
COLOR_BG          = (10, 13, 15)
COLOR_GRID        = (30, 58, 74)
COLOR_SPECTRUM_LO = (42, 122, 154)   # cyan-blue (quiet)
COLOR_SPECTRUM_HI = (224, 80, 80)    # red (loud)
COLOR_NOTCH       = (255, 200, 40)   # amber
COLOR_CANDIDATE   = (200, 120, 40)   # orange
COLOR_SAFE        = (48, 192, 96)    # green
COLOR_TEXT        = (200, 216, 232)
COLOR_ACCENT      = (90, 175, 207)
COLOR_DANGER      = (224, 64, 64)
COLOR_WARNING     = (224, 160, 32)
