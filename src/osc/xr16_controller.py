"""
OSC controller for the Behringer XR16 (and XR18/X32 compatible).

Handles:
  - Connection and keep-alive (/xremote renewals)
  - Channel EQ cuts for identified feedback frequencies
  - Channel meter polling to identify most likely feedback source
  - Global main EQ safety cut
  - Channel mute/on state queries
"""

import socket
import struct
import threading
import time
import logging
from typing import Optional, Callable
from pythonosc import udp_client, dispatcher, osc_server

log = logging.getLogger(__name__)

# XR16 has 4 EQ bands per channel; we use bands 3 and 4 for auto notching
AUTO_EQ_BANDS = [3, 4]


def _parse_xinfo_response(data: bytes) -> str:
    """Extract model/name string from an OSC /xinfo response packet."""
    try:
        # OSC string is null-terminated, padded to 4-byte boundary
        # /xinfo response layout: /xinfo + type tag + ip + name + model + version
        # We just want any readable ASCII string after the type tag
        text = data.decode("ascii", errors="replace")
        parts = [p.strip("\x00") for p in text.split("\x00") if p.strip("\x00")]
        # Filter out the address and type tag, return first real string
        for part in parts:
            if part.startswith("/"):
                continue
            if part.startswith(","):
                continue
            if len(part) > 1:
                return part
    except Exception:
        pass
    return "XR Series Mixer"


class XR16Controller:
    XREMOTE_INTERVAL = 8.0   # seconds between /xremote keepalives
    METER_POLL_INTERVAL = 0.1

    def __init__(self, ip: str = "192.168.1.1", port: int = 10024, local_port: int = 10025):
        self.ip = ip
        self.port = port
        self.local_port = local_port
        self._connected = False

        self._client: Optional[udp_client.SimpleUDPClient] = None
        self._server: Optional[osc_server.ThreadingOSCUDPServer] = None
        self._server_thread: Optional[threading.Thread] = None

        self._channel_levels: dict[int, float] = {}   # ch 1-16 -> dB
        self._channel_on: dict[int, bool] = {}         # ch 1-16 -> muted?
        self._eq_slots: dict[int, list[int]] = {}      # ch -> list of used band indices
        self._dispatch = dispatcher.Dispatcher()
        self._dispatch.map("/meters/1", self._on_meters)
        self._dispatch.map("/ch/*/mix/on", self._on_channel_on)
        self._dispatch.set_default_handler(self._on_default)

        self._lock = threading.Lock()
        self._keepalive_thread: Optional[threading.Thread] = None
        self._running = False

        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None

    # ------------------------------------------------------------------ #
    # Connection
    # ------------------------------------------------------------------ #

    def connect(self):
        try:
            self._client = udp_client.SimpleUDPClient(self.ip, self.port)

            # Try local_port first, then fall back to any available port
            bound_port = self._bind_server(self.local_port)
            if bound_port is None:
                raise OSError("Could not bind any local UDP port for OSC receive")

            self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._server_thread.start()

            self._running = True
            self._keepalive_thread = threading.Thread(target=self._keepalive_loop, daemon=True)
            self._keepalive_thread.start()

            self._connected = True
            log.info(f"Connected to XR16 at {self.ip}:{self.port} (local OSC port {bound_port})")
            if self.on_connected:
                self.on_connected()
        except Exception as e:
            log.error(f"XR16 connection failed: {e}")
            self._connected = False
            if self.on_disconnected:
                self.on_disconnected()

    def _bind_server(self, preferred_port: int) -> Optional[int]:
        """Try preferred_port, then any free port. Returns bound port or None."""
        for port in [preferred_port, 0]:  # 0 = OS picks a free port
            try:
                self._server = osc_server.ThreadingOSCUDPServer(
                    ("0.0.0.0", port), self._dispatch
                )
                # Enable address reuse so rapid restarts don't conflict
                self._server.socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
                )
                return self._server.server_address[1]
            except OSError:
                continue
        return None

    def disconnect(self):
        self._running = False
        self._connected = False
        if self._server:
            self._server.shutdown()
        log.info("Disconnected from XR16")
        if self.on_disconnected:
            self.on_disconnected()

    # ------------------------------------------------------------------ #
    # Auto-discovery
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_xinfo_packet() -> bytes:
        """Build a minimal OSC /xinfo message (no arguments)."""
        addr = b"/xinfo\x00\x00"          # padded to 8 bytes
        type_tag = b",\x00\x00\x00"       # no args
        return addr + type_tag

    def discover(self, timeout: float = 3.0,
                 on_found: Optional[Callable[[str, str], None]] = None,
                 on_timeout: Optional[Callable[[], None]] = None):
        """
        Broadcast /xinfo to the LAN and listen for the mixer's response.
        Calls on_found(ip, model_name) if found, on_timeout() otherwise.
        Runs in a background thread — safe to call from the UI.
        """
        def _run():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(timeout)
            try:
                sock.bind(("", self.port))
                packet = self._build_xinfo_packet()
                sock.sendto(packet, ("255.255.255.255", self.port))
                log.info("Discovery broadcast sent")

                deadline = time.time() + timeout
                while time.time() < deadline:
                    try:
                        data, addr = sock.recvfrom(512)
                        ip = addr[0]
                        # /xinfo response contains the mixer name after the type tag
                        model = _parse_xinfo_response(data)
                        log.info(f"Mixer found: {model} at {ip}")
                        if on_found:
                            on_found(ip, model)
                        return
                    except socket.timeout:
                        break
                    except OSError:
                        break

                log.info("Discovery timed out — no mixer found")
                if on_timeout:
                    on_timeout()
            finally:
                sock.close()

        threading.Thread(target=_run, daemon=True).start()

    # ------------------------------------------------------------------ #
    # Feedback EQ control
    # ------------------------------------------------------------------ #

    def apply_notch_to_channel(self, channel: int, frequency: float, depth_db: float,
                                Q: float = 8.0):
        """Apply a narrow EQ cut on a specific channel (1-based)."""
        if not self._connected:
            return
        band = self._get_auto_band(channel)
        ch_str = f"{channel:02d}"

        self._send(f"/ch/{ch_str}/eq/{band}/type", 5)      # type 5 = notch on XR
        self._send(f"/ch/{ch_str}/eq/{band}/f", frequency)
        self._send(f"/ch/{ch_str}/eq/{band}/g", depth_db)
        self._send(f"/ch/{ch_str}/eq/{band}/q", Q)
        log.debug(f"Notch on ch{channel} band{band}: {frequency:.0f}Hz {depth_db:.1f}dB Q={Q}")

    def apply_notch_to_main(self, frequency: float, depth_db: float, Q: float = 8.0):
        """Apply a narrow EQ cut on the main L/R bus."""
        if not self._connected:
            return
        self._send("/main/eq/3/type", 5)
        self._send("/main/eq/3/f", frequency)
        self._send("/main/eq/3/g", depth_db)
        self._send("/main/eq/3/q", Q)
        log.debug(f"Main notch: {frequency:.0f}Hz {depth_db:.1f}dB")

    def release_channel_notch(self, channel: int):
        if not self._connected:
            return
        band = self._get_auto_band(channel)
        ch_str = f"{channel:02d}"
        self._send(f"/ch/{ch_str}/eq/{band}/g", 0.0)

    def release_main_notch(self):
        if not self._connected:
            return
        self._send("/main/eq/3/g", 0.0)

    # ------------------------------------------------------------------ #
    # Channel identification
    # ------------------------------------------------------------------ #

    def get_hottest_open_channel(self) -> Optional[int]:
        """Return channel number with highest level among unmuted channels."""
        with self._lock:
            candidates = {
                ch: lvl for ch, lvl in self._channel_levels.items()
                if self._channel_on.get(ch, True)
            }
        if not candidates:
            return None
        return max(candidates, key=candidates.get)

    def poll_meters(self):
        if self._connected:
            self._send("/meters", "/meters/1")

    def poll_channel_states(self):
        if not self._connected:
            return
        for ch in range(1, 17):
            self._send(f"/ch/{ch:02d}/mix/on", None)

    # ------------------------------------------------------------------ #
    # OSC receive handlers
    # ------------------------------------------------------------------ #

    def _on_meters(self, address, *args):
        if args:
            raw = args[0]
            with self._lock:
                for i, val in enumerate(raw[:16]):
                    self._channel_levels[i + 1] = float(val)

    def _on_channel_on(self, address, *args):
        # address like /ch/02/mix/on
        parts = address.split("/")
        try:
            ch = int(parts[2])
            with self._lock:
                self._channel_on[ch] = bool(args[0]) if args else True
        except (IndexError, ValueError):
            pass

    def _on_default(self, address, *args):
        pass

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _send(self, address: str, *args):
        try:
            if args and args[0] is not None:
                self._client.send_message(address, list(args))
            else:
                self._client.send_message(address, [])
        except Exception as e:
            log.warning(f"OSC send failed: {e}")

    def _get_auto_band(self, channel: int) -> int:
        used = self._eq_slots.get(channel, [])
        for band in AUTO_EQ_BANDS:
            if band not in used:
                used.append(band)
                self._eq_slots[channel] = used
                return band
        return AUTO_EQ_BANDS[0]

    def _keepalive_loop(self):
        while self._running:
            self._send("/xremote")
            self.poll_meters()
            time.sleep(self.XREMOTE_INTERVAL)

    @property
    def is_connected(self):
        return self._connected

    @property
    def channel_levels(self) -> dict:
        with self._lock:
            return dict(self._channel_levels)
