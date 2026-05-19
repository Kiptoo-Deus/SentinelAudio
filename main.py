#!/usr/bin/env python3
"""
Sentinel Audio — Live Feedback Destroyer
Entry point.
"""

import sys
import os

# Ensure src is importable when running from project root
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from src.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Sentinel Audio")
    app.setOrganizationName("SentinelAudio")
    app.setApplicationVersion("1.0.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
