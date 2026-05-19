# Sentinel Audio — Live Feedback Destroyer

> Software-based automatic feedback suppression for live sound engineers.  
> Works with any audio interface and controls the Behringer XR16 via OSC.

---

## What It Does

Sentinel Audio listens to your main mix in real time, detects feedback as it begins to build, and kills it automatically — before the audience hears it.

- Real-time FFT spectrum analysis at 48 kHz
- Three-stage feedback detection (peak finder → onset velocity → confidence accumulation)
- Biquad IIR notch filters with high Q (surgical, transparent cuts)
- OSC control of XR16 channel EQ and main bus EQ
- Smart channel identification (finds the hottest open channel)
- Learns per-venue frequency profiles over time
- Full visual spectrum analyzer with peak hold, notch markers, and candidate warnings

---

## System Architecture

```
Microphone → XR16 → PA Speakers       ← direct signal path (no latency added)
               │
               └── XR16 Alt Out ──→ UMC402 ──→ Sentinel Audio (monitoring)
                                                       │
                                          OSC commands back to XR16 EQ
```

The software **monitors** the signal — it never sits in the main audio path, so it adds zero latency to the PA.

---

## Requirements

- Windows 10/11 (tested), macOS/Linux should work
- Python 3.11+
- Behringer UMC402 (or any ASIO/WASAPI audio interface)
- Behringer XR16 (or XR18, X32) on the same network
- XR16 connected to your PC via ethernet or Wi-Fi

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/SentinelAudio.git
cd SentinelAudio
```

### 2. Create a virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
python main.py
```

---

## Setup & Usage

### Step 1 — Connect your UMC402
- Plug UMC402 USB into your PC
- Connect XR16 **Alt Out** (or **Aux Out**) to UMC402 input 1

### Step 2 — Start audio capture
1. In the **AUDIO** tab, select your UMC402 from the device list
2. Click **START CAPTURE**
3. You should see the spectrum analyzer respond to audio

### Step 3 — Connect to XR16 (optional but recommended)
1. Go to the **XR16** tab
2. Enter your XR16's IP address (find it in the X Air app)
3. Click **CONNECT TO XR16**
4. The status dot turns green when connected

### Step 4 — Tune detection thresholds
| Setting | Recommended | Description |
|---|---|---|
| Threshold | -30 dB | Minimum level to consider as a feedback candidate |
| Prominence | 12 dB | How much a spike must stand out from neighbors |
| Confirm frames | 3 | Frames of growth needed before acting |
| Q factor | 50 | Notch width — higher = narrower = more transparent |
| Max depth | -18 dB | How deep the notch cuts |

### Step 5 — ARM
Click **ARM PROTECTION**. The button turns red. Sentinel Audio is now actively protecting your show.

---

## Detection Algorithm

```
Audio buffer (1024 samples @ 48kHz = ~21ms)
    │
    ▼
FFT (4096 point, Hann window, smoothed)
    │
    ▼
Peak finder  →  narrow peaks above threshold with high prominence
    │
    ▼
Onset velocity  →  is the peak GROWING? (delta > 1.5 dB/frame)
    │
    ▼
Confidence  →  growing for N consecutive frames?
    │
    ▼
CONFIRMED FEEDBACK  →  place notch filter + OSC command
```

A snare hit spikes sharply but **decays**. Feedback spikes and **grows**. The three-stage check eliminates false positives from drum transients, plosives, and loud musical peaks.

---

## OSC Commands Sent to XR16

| Event | OSC Address | Value |
|---|---|---|
| Feedback detected (main) | `/main/eq/3/f` | frequency Hz |
| Feedback detected (main) | `/main/eq/3/g` | depth dB (negative) |
| Feedback detected (main) | `/main/eq/3/q` | Q factor |
| Feedback on channel N | `/ch/NN/eq/3/f` | frequency Hz |
| Feedback on channel N | `/ch/NN/eq/3/g` | depth dB |
| Keepalive | `/xremote` | (every 8 seconds) |
| Meter poll | `/meters` | `/meters/1` |

---

## Project Structure

```
SentinelAudio/
├── main.py                     ← entry point
├── requirements.txt
├── README.md
└── src/
    ├── audio/
    │   ├── capture.py          ← sounddevice audio capture + ring buffer
    │   ├── fft_engine.py       ← Hann-windowed FFT with smoothing
    │   └── notch_filter.py     ← biquad IIR notch filter bank (up to 32 filters)
    ├── detection/
    │   └── feedback_detector.py ← 3-stage feedback detection engine
    ├── osc/
    │   └── xr16_controller.py  ← OSC client/server for XR16 control
    └── ui/
        ├── main_window.py      ← main application window
        ├── spectrum_widget.py  ← real-time log-scale spectrum analyzer
        ├── level_meter.py      ← LED-style vertical level meter
        ├── channel_strip.py    ← per-channel level + notch indicator
        └── styles.py           ← dark theme stylesheet + color constants
```

---

## Troubleshooting

**No audio devices listed**
- Make sure UMC402 drivers are installed
- Try running as administrator

**Spectrum is flat / not responding**
- Check UMC402 input gain — there needs to be signal coming in
- Verify the XR16 Alt Out is patched

**XR16 won't connect**
- Confirm XR16 is on the same network as your PC
- Check the IP in the X Air Edit app (Info screen)
- Disable Windows Firewall temporarily to test

**Too many false positives**
- Raise the Threshold slider (less sensitive)
- Raise Prominence (spikes must stand out more)
- Raise Confirm frames (require more sustained growth)

**Missing feedback events (too slow)**
- Lower Threshold (more sensitive)
- Lower Confirm frames (act faster)

---

## Roadmap

- [ ] Venue profile save/load (JSON)
- [ ] Per-mic frequency fingerprinting
- [ ] AI pre-emptive mode (predict feedback before it starts)
- [ ] VST/AU plugin version (JUCE)
- [ ] Multi-channel monitoring (direct channel feeds)
- [ ] Soundcheck auto-learning mode

---

## License

MIT — use freely, contribute back.
