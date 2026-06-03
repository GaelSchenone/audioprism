# audioprism

Real-time audio visualizer with GPU particle systems, 3D point clouds, and ASCII rendering — driven by PipeWire/PulseAudio system-wide or per-app audio capture.

## Features

- **Per-app audio capture** via PipeWire node linking — visualize Spotify, Firefox, or any running app independently
- **GPU-accelerated rendering** with OpenGL shaders, bloom post-processing, and glow effects
- **9 visual presets** switchable live with `1-9` or `Tab`
- **Webcam / video input** converted to reactive ASCII art, distorted by audio in real time
- **3D point cloud** — webcam frames projected into 3D space with Z-axis driven by the audio spectrum

## Presets

| # | Name | Description |
|---|------|-------------|
| 1 | `spectrum` | Frequency bars with bloom and per-band coloring |
| 2 | `waveform` | Oscilloscope with glowing trail |
| 3 | `particles` | GPU particle system that explodes on bass hits |
| 4 | `radial` | Circular spectrum with pulsing tentacles |
| 5 | `matrix` | Matrix rain with volume-reactive brightness |
| 6 | `ascii_bars` | Classic ASCII frequency bars via character atlas shader |
| 7 | `ascii_cam` | Webcam/video → ASCII, glitched and distorted by audio bands |
| 8 | `point_cloud_cam` | Webcam frame as 3D point cloud, Z = audio spectrum |
| 9 | `point_cloud_audio` | Pure audio FFT rendered as a 3D particle nebula |

## Tech Stack

- **Audio**: `sounddevice` + PipeWire/PulseAudio monitor sources
- **DSP**: `numpy` FFT, beat detection, band analysis (bass / mid / high)
- **Rendering**: `pygame` (window + input) + `moderngl` (OpenGL 3.3+)
- **Video**: `opencv-python` for webcam and video file capture
- **3D math**: `pyrr` for MVP matrices and arcball camera

## Requirements

- Linux with PipeWire or PulseAudio
- OpenGL 3.3+
- Python 3.11+
- Webcam (optional, for `ascii_cam` and `point_cloud_cam` presets)

## Installation

```bash
pnpm install        # or: pip install -e .
```

## Usage

```bash
# Launch with app selector (choose which app's audio to capture)
python -m src.main

# Use system-wide audio output
python -m src.main --system

# Use a video file instead of webcam
python -m src.main --video path/to/video.mp4

# Start on a specific preset
python -m src.main --preset particles
```

## Controls

| Key | Action |
|-----|--------|
| `1-9` | Switch preset |
| `Tab` | Next preset |
| `Space` | Pause / resume |
| `Mouse drag` | Rotate 3D view (point cloud modes) |
| `Scroll` | Zoom (point cloud modes) |
| `Q` / `Esc` | Quit |

## Project Structure

```
src/
├── audio/
│   ├── pipewire.py       # PipeWire node discovery and loopback linking
│   ├── capture.py        # Audio capture thread with ring buffer
│   └── analyzer.py       # FFT, band analysis, beat detection
├── video/
│   ├── capture.py        # Webcam / video file input (OpenCV)
│   └── ascii_converter.py
├── presets/
│   ├── base.py           # Abstract Preset(update, draw)
│   ├── spectrum.py
│   ├── waveform.py
│   ├── particles.py
│   ├── radial.py
│   ├── matrix.py
│   ├── ascii_bars.py
│   ├── ascii_cam.py
│   ├── point_cloud_cam.py
│   └── point_cloud_audio.py
├── shaders/              # GLSL vertex + fragment shaders
├── renderer.py           # Main loop, FBO pipeline, bloom pass
└── main.py
```
