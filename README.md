# audioprism

Real-time audio visualizer with GPU shaders, 3D point clouds, ASCII rendering and
live monocular depth — driven by PipeWire/PulseAudio system-wide or per-app audio
capture, plus optional webcam input.

## Features

- **Per-app or system audio capture** via PipeWire/PulseAudio — visualize Spotify,
  a browser, or everything that's playing
- **10 visual presets** including GPU particles, a 3D FFT nebula, Matrix rain, and
  typographic ASCII
- **Webcam → ASCII** and **webcam → 3D point cloud with real depth** (MiDaS monocular
  depth estimation, running on a background thread)
- **GPU rendering** (OpenGL 3.3 core via moderngl) with a global bloom pipeline
- **16 themes** with independent **UI** and **graphics** palettes, plus a custom
  palette editor (create / save / delete your own)
- **Detachable output window** you can drag to any monitor, then fullscreen
- Live, persisted settings; everything tweakable while watching

## Presets

| # | Name | Description |
|---|------|-------------|
| 1 | `spectrum` | Log-frequency bars with bloom and per-band color |
| 2 | `waveform` | Oscilloscope line traced from the raw audio |
| 3 | `particles` | Audio-reactive GPU particle system (bass emits, beats burst) |
| 4 | `radial` | Circular spectrum that pulses with volume |
| 5 | `matrix` | Digital rain, fall speed/brightness from volume |
| 6 | `ascii_bars` | Frequency bars rendered as ASCII glyphs |
| 7 | `ascii_cam` | Live webcam/video → ASCII, glitched/flashed by audio |
| 8 | `depth` | Live monocular depth map (MiDaS), palette-colored |
| 9 | `point_cloud_audio` | 3D nebula of points driven by the FFT spectrum |
| 10 | `point_cloud_cam` | Webcam as a true-color 3D point cloud, Z from real depth |

## Tech stack

- **GUI / windowing**: PySide6 (Qt 6)
- **Rendering**: moderngl (OpenGL 3.3 core) + a bloom post-process pipeline
- **Audio**: sounddevice + numpy FFT (bands, beat detection, BPM)
- **Video**: opencv-python (webcam / video files)
- **Depth**: onnxruntime — MiDaS small (CPU, ~6–8 fps) or Depth Anything V2 small
- **Fonts / 3D math**: Pillow (ASCII atlas), pyrr (orbit camera)

## Requirements

- Linux with PipeWire or PulseAudio
- OpenGL 3.3+ (tested on Mesa)
- Python 3.11+
- `libxcb-cursor0` (required by Qt 6.5+): `sudo apt-get install -y libxcb-cursor0`
- A webcam (optional, for `ascii_cam` / `depth` / `point_cloud_cam`)

Depth models download on first use to a gitignored `models/` directory.

## Installation

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Usage

```bash
.venv/bin/python -m src.main                 # launch the GUI
.venv/bin/python -m src.main --tui           # terminal audio monitor
.venv/bin/python -m src.main --list-devices  # list input devices
.venv/bin/python -m src.main --video clip.mp4  # use a video file (starts on ascii_cam)
```

## Interface

- **Sidebar** (narrow, left): `⚙` opens a small flyout with **Configuración**
  (UI theme + audio: source, sensitivity, smoothing, FPS) and **Save**; `⧉` opens
  the **output window**.
- **Main panel**: shows only what the active preset uses — preset + palette, the
  effect's parameters, rendering (bloom, background dim), and Camera/Depth (only for
  camera presets, with detected cameras).
- **Output window**: a normal draggable window — move it to a monitor, then
  double-click (or `F` / `F11`) to go fullscreen.

## Controls

| Input | Action |
|-------|--------|
| `1`–`9`, `0` | Select preset (`0` = 10th) |
| `Tab` / `Shift+Tab` | Cycle presets |
| `Space` | Pause / resume |
| `F` | Open the output window |
| Mouse drag | Orbit (3D presets) |
| Scroll | Zoom (3D presets) |
| Double-click (output window) | Toggle fullscreen |
| `Esc` (output window) | Leave fullscreen / close |

## Project structure

```
src/
├── audio/        capture (per-app/system), FFT analyzer (bands, beat, BPM)
├── video/        webcam/file capture, monocular depth (ONNX, threaded)
├── presets/      the 10 visual presets + shared helpers
├── config/       theme/palette model + persisted settings
├── gui/          Qt app: panel, sidebar flyout, config + output windows, viewport
├── camera3d.py   orbit camera (MVP, rotate, zoom)
├── engine.py     render targets, palette LUT, preset registry, bloom
├── postprocess.py bloom (bright-pass → blur → composite)
└── main.py
```
