"""
Main application window for Sentinel Audio.

Layout:
  Top bar    — logo, status pill, arm/disarm button, global level meter
  Left panel — spectrum analyzer (full width)
  Mid panel  — notch filter table | channel grid
  Bottom bar — settings (device, XR16 IP, threshold sliders)
  Status bar — response time, event count, last event
"""

import time
import threading
import numpy as np

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QSlider, QGroupBox,
    QTableWidget, QTableWidgetItem, QSplitter, QLineEdit,
    QCheckBox, QTabWidget, QStatusBar, QFrame, QSizePolicy,
    QHeaderView, QSpacerItem,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QObject
from PyQt6.QtGui import QColor, QFont, QPalette, QIcon

from .spectrum_widget import SpectrumWidget
from .level_meter import LevelMeter
from .channel_strip import ChannelStrip
from .styles import DARK_STYLESHEET, COLOR_SAFE, COLOR_DANGER, COLOR_WARNING, COLOR_ACCENT

from ..audio.capture import AudioCapture
from ..audio.fft_engine import FFTEngine
from ..audio.notch_filter import NotchFilterBank
from ..detection.feedback_detector import FeedbackDetector
from ..osc.xr16_controller import XR16Controller


# ------------------------------------------------------------------ #
# Worker thread signals
# ------------------------------------------------------------------ #

class AudioWorkerSignals(QObject):
    spectrum_ready = pyqtSignal(object, object)  # freqs, magnitudes
    level_updated  = pyqtSignal(float)
    feedback_detected = pyqtSignal(list)          # [freq, ...]
    candidates_updated = pyqtSignal(list)


class AudioWorker(QThread):
    def __init__(self, capture: AudioCapture, fft: FFTEngine,
                 detector: FeedbackDetector, filter_bank: NotchFilterBank):
        super().__init__()
        self.capture = capture
        self.fft = fft
        self.detector = detector
        self.filter_bank = filter_bank
        self.signals = AudioWorkerSignals()
        self._running = False
        self._armed = False
        self._pending_buffers: list[np.ndarray] = []
        self._lock = threading.Lock()

    def push_buffer(self, buf: np.ndarray):
        with self._lock:
            self._pending_buffers.append(buf)

    def set_armed(self, armed: bool):
        self._armed = armed

    def run(self):
        self._running = True
        while self._running:
            buf = None
            with self._lock:
                if self._pending_buffers:
                    buf = self._pending_buffers.pop(0)

            if buf is None:
                self.msleep(5)
                continue

            mag_db = self.fft.process(buf)
            self.signals.spectrum_ready.emit(self.fft.frequencies.copy(), mag_db.copy())
            self.signals.level_updated.emit(self.capture.get_level_db())

            if self._armed:
                confirmed = self.detector.analyze(mag_db)
                self.filter_bank.tick_release(set(confirmed))
                if confirmed:
                    self.signals.feedback_detected.emit(confirmed)
                candidates = [c.frequency for c in self.detector.get_candidates()
                              if not c.confirmed]
                self.signals.candidates_updated.emit(candidates)

    def stop(self):
        self._running = False
        self.wait()


# ------------------------------------------------------------------ #
# Main Window
# ------------------------------------------------------------------ #

class MainWindow(QMainWindow):
    VERSION = "1.0.0"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Sentinel Audio  v{self.VERSION}  —  Live Feedback Destroyer")
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)
        self.setStyleSheet(DARK_STYLESHEET)

        # Core components
        self._capture   = AudioCapture()
        self._fft       = FFTEngine(fft_size=4096, sample_rate=48000, smoothing=0.80)
        self._detector  = FeedbackDetector(sample_rate=48000, fft_size=4096)
        self._filter_bank = NotchFilterBank(sample_rate=48000)
        self._xr16      = XR16Controller()
        self._worker    = AudioWorker(self._capture, self._fft, self._detector, self._filter_bank)

        self._armed = False
        self._event_count = 0
        self._last_event_time = 0.0
        self._session_start = time.time()
        self._response_times: list[float] = []
        self._detect_timestamp: dict[float, float] = {}

        self._build_ui()
        self._connect_signals()
        self._populate_devices()

        # UI refresh timer
        self._ui_timer = QTimer()
        self._ui_timer.setInterval(50)   # 20 fps
        self._ui_timer.timeout.connect(self._refresh_ui)
        self._ui_timer.start()

        self._worker.start()

    # ================================================================ #
    # UI Construction
    # ================================================================ #

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        root.addWidget(self._build_topbar())
        root.addWidget(self._build_spectrum_panel(), stretch=3)
        root.addWidget(self._build_mid_panel(), stretch=2)
        root.addWidget(self._build_settings_panel())

        self._status_bar = QStatusBar()
        self._status_bar.setStyleSheet("color: #5a7f9f; font-size: 11px;")
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready  —  Select audio device and arm to begin")

    # ------------------------------------------------------------------ #

    def _build_topbar(self):
        bar = QWidget()
        bar.setFixedHeight(64)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        # Logo
        logo = QLabel("SENTINEL AUDIO")
        logo.setStyleSheet(
            "font-size: 22px; font-weight: bold; color: #5aafcf; "
            "letter-spacing: 4px; font-family: 'Segoe UI';"
        )
        lay.addWidget(logo)

        tagline = QLabel("Live Feedback Destroyer")
        tagline.setStyleSheet("font-size: 11px; color: #3a6a8a; letter-spacing: 1px;")
        lay.addWidget(tagline)

        lay.addStretch()

        # Stats row
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background: #0f1e2a; border-radius: 6px; padding: 4px;")
        stats_lay = QHBoxLayout(stats_frame)
        stats_lay.setContentsMargins(12, 4, 12, 4)
        stats_lay.setSpacing(24)

        self._lbl_event_count = self._stat_label("EVENTS", "0")
        self._lbl_response_time = self._stat_label("AVG RESPONSE", "—  ms")
        self._lbl_filters_active = self._stat_label("ACTIVE FILTERS", "0")
        self._lbl_uptime = self._stat_label("UPTIME", "00:00")

        for w in [self._lbl_event_count, self._lbl_response_time,
                  self._lbl_filters_active, self._lbl_uptime]:
            stats_lay.addWidget(w)

        lay.addWidget(stats_frame)

        # XR16 status dot
        self._lbl_xr16_status = QLabel("● XR16 OFFLINE")
        self._lbl_xr16_status.setStyleSheet("color: #3a5060; font-size: 11px; font-weight: bold;")
        lay.addWidget(self._lbl_xr16_status)

        # Arm button
        self._btn_arm = QPushButton("ARM PROTECTION")
        self._btn_arm.setObjectName("btn_arm")
        self._btn_arm.setFixedWidth(160)
        self._btn_arm.setFixedHeight(44)
        self._btn_arm.setCheckable(True)
        self._btn_arm.toggled.connect(self._on_arm_toggled)
        lay.addWidget(self._btn_arm)

        # Main level meter
        self._main_meter = LevelMeter("IN")
        lay.addWidget(self._main_meter)

        return bar

    def _stat_label(self, title: str, value: str) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 9px; color: #3a6a8a; letter-spacing: 1px; font-weight: bold;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_val = QLabel(value)
        lbl_val.setStyleSheet("font-size: 14px; color: #5aafcf; font-weight: bold; font-family: 'Consolas';")
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(lbl_title)
        v.addWidget(lbl_val)
        w.value_label = lbl_val
        return w

    # ------------------------------------------------------------------ #

    def _build_spectrum_panel(self):
        box = QGroupBox("SPECTRUM ANALYZER")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(4, 16, 4, 4)
        self._spectrum = SpectrumWidget()
        lay.addWidget(self._spectrum)
        return box

    # ------------------------------------------------------------------ #

    def _build_mid_panel(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: notch filter table
        notch_box = QGroupBox("ACTIVE NOTCH FILTERS")
        notch_lay = QVBoxLayout(notch_box)
        notch_lay.setContentsMargins(4, 16, 4, 4)

        self._notch_table = QTableWidget(0, 5)
        self._notch_table.setHorizontalHeaderLabels(
            ["FREQUENCY", "DEPTH", "CHANNEL", "AGE", "STATUS"]
        )
        self._notch_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._notch_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._notch_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._notch_table.verticalHeader().setVisible(False)
        self._notch_table.setFixedHeight(180)
        notch_lay.addWidget(self._notch_table)

        # Release button
        self._btn_release_all = QPushButton("RELEASE ALL FILTERS")
        self._btn_release_all.clicked.connect(self._release_all_filters)
        notch_lay.addWidget(self._btn_release_all)

        splitter.addWidget(notch_box)

        # Right: channel grid
        ch_box = QGroupBox("CHANNEL MONITOR  (XR16)")
        ch_lay = QHBoxLayout(ch_box)
        ch_lay.setContentsMargins(4, 16, 4, 4)
        ch_lay.setSpacing(2)

        self._channel_strips: list[ChannelStrip] = []
        for i in range(1, 17):
            strip = ChannelStrip(i)
            self._channel_strips.append(strip)
            ch_lay.addWidget(strip)

        splitter.addWidget(ch_box)
        splitter.setSizes([500, 400])
        return splitter

    # ------------------------------------------------------------------ #

    def _build_settings_panel(self):
        tabs = QTabWidget()

        # --- Audio tab ---
        audio_tab = QWidget()
        a_lay = QHBoxLayout(audio_tab)
        a_lay.setContentsMargins(8, 8, 8, 8)
        a_lay.setSpacing(20)

        # Device selector
        dev_group = QGroupBox("INPUT DEVICE")
        dev_lay = QVBoxLayout(dev_group)
        self._combo_device = QComboBox()
        self._combo_device.setMinimumWidth(280)
        dev_lay.addWidget(self._combo_device)
        self._btn_start_audio = QPushButton("START CAPTURE")
        self._btn_start_audio.clicked.connect(self._on_start_audio)
        dev_lay.addWidget(self._btn_start_audio)
        a_lay.addWidget(dev_group)

        # Detection thresholds
        thresh_group = QGroupBox("DETECTION THRESHOLDS")
        t_lay = QGridLayout(thresh_group)

        t_lay.addWidget(QLabel("Threshold (dB):"), 0, 0)
        self._slider_threshold = QSlider(Qt.Orientation.Horizontal)
        self._slider_threshold.setRange(-60, -10)
        self._slider_threshold.setValue(-30)
        self._slider_threshold.valueChanged.connect(self._on_threshold_changed)
        t_lay.addWidget(self._slider_threshold, 0, 1)
        self._lbl_threshold = QLabel("-30 dB")
        t_lay.addWidget(self._lbl_threshold, 0, 2)

        t_lay.addWidget(QLabel("Prominence (dB):"), 1, 0)
        self._slider_prominence = QSlider(Qt.Orientation.Horizontal)
        self._slider_prominence.setRange(5, 30)
        self._slider_prominence.setValue(12)
        self._slider_prominence.valueChanged.connect(self._on_prominence_changed)
        t_lay.addWidget(self._slider_prominence, 1, 1)
        self._lbl_prominence = QLabel("12 dB")
        t_lay.addWidget(self._lbl_prominence, 1, 2)

        t_lay.addWidget(QLabel("Confirm frames:"), 2, 0)
        self._slider_confirm = QSlider(Qt.Orientation.Horizontal)
        self._slider_confirm.setRange(1, 10)
        self._slider_confirm.setValue(3)
        self._slider_confirm.valueChanged.connect(self._on_confirm_changed)
        t_lay.addWidget(self._slider_confirm, 2, 1)
        self._lbl_confirm = QLabel("3")
        t_lay.addWidget(self._lbl_confirm, 2, 2)

        a_lay.addWidget(thresh_group)

        # Notch filter settings
        notch_group = QGroupBox("NOTCH FILTER")
        n_lay = QGridLayout(notch_group)

        n_lay.addWidget(QLabel("Q factor:"), 0, 0)
        self._slider_q = QSlider(Qt.Orientation.Horizontal)
        self._slider_q.setRange(10, 100)
        self._slider_q.setValue(50)
        self._slider_q.valueChanged.connect(lambda v: self._lbl_q.setText(str(v)))
        n_lay.addWidget(self._slider_q, 0, 1)
        self._lbl_q = QLabel("50")
        n_lay.addWidget(self._lbl_q, 0, 2)

        n_lay.addWidget(QLabel("Max depth (dB):"), 1, 0)
        self._slider_depth = QSlider(Qt.Orientation.Horizontal)
        self._slider_depth.setRange(-36, -3)
        self._slider_depth.setValue(-18)
        self._slider_depth.valueChanged.connect(lambda v: self._lbl_depth.setText(f"{v} dB"))
        n_lay.addWidget(self._slider_depth, 1, 1)
        self._lbl_depth = QLabel("-18 dB")
        n_lay.addWidget(self._lbl_depth, 1, 2)

        self._chk_apply_to_main = QCheckBox("Apply to XR16 main EQ")
        self._chk_apply_to_main.setChecked(True)
        n_lay.addWidget(self._chk_apply_to_main, 2, 0, 1, 3)

        self._chk_channel_id = QCheckBox("Smart channel identification")
        self._chk_channel_id.setChecked(True)
        n_lay.addWidget(self._chk_channel_id, 3, 0, 1, 3)

        a_lay.addWidget(notch_group)
        a_lay.addStretch()
        tabs.addTab(audio_tab, "AUDIO")

        # --- XR16 tab ---
        xr_tab = QWidget()
        xr_lay = QHBoxLayout(xr_tab)
        xr_lay.setContentsMargins(8, 8, 8, 8)
        xr_lay.setSpacing(20)

        conn_group = QGroupBox("XR16 CONNECTION")
        c_lay = QGridLayout(conn_group)

        c_lay.addWidget(QLabel("XR16 IP Address:"), 0, 0)
        self._edit_xr16_ip = QLineEdit("—  not found yet")
        self._edit_xr16_ip.setReadOnly(False)
        c_lay.addWidget(self._edit_xr16_ip, 0, 1)

        self._btn_discover = QPushButton("AUTO-DISCOVER")
        self._btn_discover.setToolTip("Broadcast /xinfo to detect the XR16 on your LAN")
        self._btn_discover.clicked.connect(self._on_discover_xr16)
        c_lay.addWidget(self._btn_discover, 0, 2)

        c_lay.addWidget(QLabel("Port:"), 1, 0)
        self._edit_xr16_port = QLineEdit("10024")
        c_lay.addWidget(self._edit_xr16_port, 1, 1)

        self._lbl_discover_status = QLabel("")
        self._lbl_discover_status.setStyleSheet("color: #5aafcf; font-size: 11px;")
        c_lay.addWidget(self._lbl_discover_status, 1, 2)

        self._btn_connect_xr16 = QPushButton("CONNECT TO XR16")
        self._btn_connect_xr16.clicked.connect(self._on_connect_xr16)
        c_lay.addWidget(self._btn_connect_xr16, 2, 0, 1, 3)

        xr_lay.addWidget(conn_group)
        xr_lay.addStretch()
        tabs.addTab(xr_tab, "XR16")

        return tabs

    # ================================================================ #
    # Signal Connections
    # ================================================================ #

    def _connect_signals(self):
        self._worker.signals.spectrum_ready.connect(self._on_spectrum_ready)
        self._worker.signals.level_updated.connect(self._on_level_updated)
        self._worker.signals.feedback_detected.connect(self._on_feedback_detected)
        self._worker.signals.candidates_updated.connect(self._on_candidates_updated)

        self._xr16.on_connected = self._on_xr16_connected
        self._xr16.on_disconnected = self._on_xr16_disconnected

    # ================================================================ #
    # Slots
    # ================================================================ #

    @pyqtSlot(object, object)
    def _on_spectrum_ready(self, freqs, mags):
        self._spectrum.update_spectrum(freqs, mags)

    @pyqtSlot(float)
    def _on_level_updated(self, db):
        self._main_meter.set_level(db)

    @pyqtSlot(list)
    def _on_feedback_detected(self, freqs: list):
        now = time.time()
        for freq in freqs:
            # Record response time
            if freq in self._detect_timestamp:
                rt_ms = (now - self._detect_timestamp[freq]) * 1000
                self._response_times.append(rt_ms)
            self._detect_timestamp[freq] = now

            # Add notch filter
            nf = self._filter_bank.add_or_update(
                freq,
                Q=self._slider_q.value(),
                target_db=self._slider_depth.value(),
            )

            # OSC commands
            if self._xr16.is_connected:
                if self._chk_apply_to_main.isChecked():
                    self._xr16.apply_notch_to_main(freq, self._slider_depth.value())
                if self._chk_channel_id.isChecked():
                    hottest = self._xr16.get_hottest_open_channel()
                    if hottest:
                        self._xr16.apply_notch_to_channel(hottest, freq, self._slider_depth.value())
                        nf.channel = hottest

        self._event_count += len(freqs)
        self._last_event_time = now
        self._update_notch_table()
        self._status_bar.showMessage(
            f"FEEDBACK DETECTED  —  {', '.join(f'{f:.0f} Hz' for f in freqs)}"
            f"  —  Event #{self._event_count}"
        )

    @pyqtSlot(list)
    def _on_candidates_updated(self, freqs: list):
        self._spectrum.set_candidate_markers(freqs)

    def _on_arm_toggled(self, armed: bool):
        self._armed = armed
        self._worker.set_armed(armed)
        self._detector.reset()

        if armed:
            self._btn_arm.setText("PROTECTED  ●")
            self._btn_arm.setProperty("armed", "true")
        else:
            self._btn_arm.setText("ARM PROTECTION")
            self._btn_arm.setProperty("armed", "false")

        self._btn_arm.style().unpolish(self._btn_arm)
        self._btn_arm.style().polish(self._btn_arm)

    def _on_start_audio(self):
        if self._capture.is_running:
            self._capture.stop()
            self._btn_start_audio.setText("START CAPTURE")
            self._status_bar.showMessage("Audio capture stopped")
            return

        idx = self._combo_device.currentData()
        self._capture.device_index = idx
        self._capture.on_buffer = self._worker.push_buffer

        try:
            self._capture.start()
            self._btn_start_audio.setText("STOP CAPTURE")
            self._status_bar.showMessage(
                f"Capturing from: {self._combo_device.currentText()}"
            )
        except Exception as e:
            self._status_bar.showMessage(f"Audio error: {e}")

    def _on_discover_xr16(self):
        self._btn_discover.setText("SCANNING...")
        self._btn_discover.setEnabled(False)
        self._lbl_discover_status.setText("Broadcasting /xinfo...")
        self._lbl_discover_status.setStyleSheet("color: #5aafcf; font-size: 11px;")

        def found(ip, model):
            # Called from background thread — post to Qt main thread via timer
            self._discovered_ip = ip
            self._discovered_model = model
            QTimer.singleShot(0, self._apply_discovered_ip)

        def timed_out():
            self._discovered_ip = None
            QTimer.singleShot(0, self._apply_discovered_ip)

        self._xr16.discover(timeout=3.0, on_found=found, on_timeout=timed_out)

    def _apply_discovered_ip(self):
        self._btn_discover.setText("AUTO-DISCOVER")
        self._btn_discover.setEnabled(True)
        ip = getattr(self, "_discovered_ip", None)
        model = getattr(self, "_discovered_model", "")
        if ip:
            self._edit_xr16_ip.setText(ip)
            self._lbl_discover_status.setText(f"Found: {model}")
            self._lbl_discover_status.setStyleSheet("color: #30c060; font-size: 11px;")
            self._status_bar.showMessage(f"XR16 found at {ip}  ({model})  — click CONNECT")
        else:
            self._lbl_discover_status.setText("Not found on LAN")
            self._lbl_discover_status.setStyleSheet("color: #c04040; font-size: 11px;")
            self._status_bar.showMessage(
                "No XR16 found — check LAN cable and that the mixer is powered on"
            )

    def _on_connect_xr16(self):
        ip = self._edit_xr16_ip.text().strip()
        if ip.startswith("—"):
            self._status_bar.showMessage("Run AUTO-DISCOVER first, or enter the IP manually")
            return
        try:
            port = int(self._edit_xr16_port.text().strip())
        except ValueError:
            port = 10024
        self._xr16.ip = ip
        self._xr16.port = port
        self._btn_connect_xr16.setText("CONNECTING...")
        self._btn_connect_xr16.setEnabled(False)
        threading.Thread(target=self._xr16.connect, daemon=True).start()

    def _on_xr16_connected(self):
        self._lbl_xr16_status.setText("● XR16 ONLINE")
        self._lbl_xr16_status.setStyleSheet("color: #30c060; font-size: 11px; font-weight: bold;")
        self._btn_connect_xr16.setText("DISCONNECT")
        self._btn_connect_xr16.setEnabled(True)

    def _on_xr16_disconnected(self):
        self._lbl_xr16_status.setText("● XR16 OFFLINE")
        self._lbl_xr16_status.setStyleSheet("color: #3a5060; font-size: 11px; font-weight: bold;")
        self._btn_connect_xr16.setText("CONNECT TO XR16")
        self._btn_connect_xr16.setEnabled(True)

    def _on_threshold_changed(self, val):
        self._lbl_threshold.setText(f"{val} dB")
        self._detector.threshold_db = float(val)

    def _on_prominence_changed(self, val):
        self._lbl_prominence.setText(f"{val} dB")
        self._detector.prominence_db = float(val)

    def _on_confirm_changed(self, val):
        self._lbl_confirm.setText(str(val))
        self._detector.confirm_frames = val

    def _release_all_filters(self):
        for f in self._filter_bank.active_filters:
            f.active = False
            if self._xr16.is_connected:
                if f.channel:
                    self._xr16.release_channel_notch(f.channel)
        self._xr16.release_main_notch()
        self._update_notch_table()
        self._spectrum.set_notch_markers([])

    # ================================================================ #
    # UI refresh (timer driven)
    # ================================================================ #

    def _refresh_ui(self):
        # Uptime
        elapsed = int(time.time() - self._session_start)
        m, s = divmod(elapsed, 60)
        self._lbl_uptime.value_label.setText(f"{m:02d}:{s:02d}")

        # Event count
        self._lbl_event_count.value_label.setText(str(self._event_count))

        # Average response time
        if self._response_times:
            avg = np.mean(self._response_times[-20:])
            self._lbl_response_time.value_label.setText(f"{avg:.0f} ms")

        # Active filters
        active = self._filter_bank.active_filters
        self._lbl_filters_active.value_label.setText(str(len(active)))

        # Spectrum notch markers
        self._spectrum.set_notch_markers(
            [(f.frequency, f.depth_db) for f in active]
        )

        # Channel strips (XR16 levels)
        if self._xr16.is_connected:
            levels = self._xr16.channel_levels
            for strip in self._channel_strips:
                ch = strip.channel_num
                if ch in levels:
                    strip.set_level(levels[ch])
                notch_ch = next(
                    (f for f in active if f.channel == ch), None
                )
                strip.set_notch(notch_ch is not None,
                                notch_ch.frequency if notch_ch else 0.0)

    def _update_notch_table(self):
        active = self._filter_bank.active_filters
        self._notch_table.setRowCount(len(active))
        for row, f in enumerate(active):
            freq_str = f"{f.frequency/1000:.2f} kHz" if f.frequency >= 1000 else f"{f.frequency:.0f} Hz"
            ch_str = str(f.channel) if f.channel else "Main"
            age_str = f"{f.age_seconds:.1f}s"
            status_str = f"{f.depth_db:.1f} dB"

            items = [freq_str, f"{f.depth_db:.1f} dB", ch_str, age_str, "ACTIVE"]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 4:
                    item.setForeground(QColor(*COLOR_DANGER))
                self._notch_table.setItem(row, col, item)

    # ================================================================ #
    # Device population
    # ================================================================ #

    def _populate_devices(self):
        self._combo_device.clear()
        try:
            devices = self._capture.get_available_devices()
            for dev in devices:
                label = f"{dev['name']}  ({dev['channels']}ch  {dev['sample_rate']}Hz)"
                self._combo_device.addItem(label, userData=dev["index"])
                # Pre-select UMC if found
                if "umc" in dev["name"].lower() or "behringer" in dev["name"].lower():
                    self._combo_device.setCurrentIndex(self._combo_device.count() - 1)
        except Exception as e:
            self._status_bar.showMessage(f"Could not list audio devices: {e}")

    # ================================================================ #
    # Cleanup
    # ================================================================ #

    def closeEvent(self, event):
        self._ui_timer.stop()
        self._worker.stop()
        self._capture.stop()
        if self._xr16.is_connected:
            self._xr16.disconnect()
        event.accept()
