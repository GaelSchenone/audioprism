"""audioprism — entry point. Launches the Qt GUI (or the terminal monitor)."""

from __future__ import annotations

import sys
import time
import argparse

import sounddevice as sd

from src.audio.pipewire import list_sources, AudioSource
from src.audio.capture import AudioCapture
from src.audio.analyzer import AudioAnalyzer
from src.config.settings import VisualizerSettings
from src.config.theme import default_registry


# ── source selection ───────────────────────────────────────────────────────────

def _pick_source(settings: VisualizerSettings, prefer_system: bool) -> tuple[int | None, list[AudioSource]]:
    sources = list_sources()
    if not sources:
        return None, []
    if not prefer_system and settings.source_index is not None:
        if any(s.device_index == settings.source_index for s in sources):
            return settings.source_index, sources
    system = next((s for s in sources if s.kind == "system"), sources[0])
    return system.device_index, sources


# ── GUI ─────────────────────────────────────────────────────────────────────────

def _run_gui(settings: VisualizerSettings, selftest: bool) -> int:
    from PySide6.QtCore import QTimer
    from src.gui.app import create_app
    from src.gui.controller import Controller
    from src.gui.main_window import MainWindow

    registry = default_registry()
    device, sources = _pick_source(settings, prefer_system=True)
    if device is not None:
        settings.source_index = device

    app = create_app()
    controller = Controller(device, settings, registry)
    window = MainWindow(controller, sources)
    window.show()
    controller.start()

    if selftest:
        QTimer.singleShot(2000, app.quit)

    return app.exec()


# ── terminal monitor ─────────────────────────────────────────────────────────────

def _bar(value: float, width: int = 24) -> str:
    filled = int(value * width)
    return "█" * filled + "░" * (width - filled)


def _run_terminal(device: int) -> None:
    capture = AudioCapture(device=device)
    analyzer = AudioAnalyzer(sample_rate=capture.sample_rate)
    capture.start()
    print("Capturing… Ctrl-C to stop.\n")
    try:
        while True:
            samples = capture.read()
            if samples is None:
                time.sleep(0.01)
                continue
            data = analyzer.analyze(samples)
            beat = "  ★ BEAT" if data.beat else ""
            bpm = f"  {data.bpm:.0f} BPM" if data.bpm else ""
            lines = [
                "\033[H\033[J",
                f"vol      {_bar(data.volume)} {data.volume:.2f}{beat}{bpm}",
                "",
                *[f"{n:<10} {_bar(v)} {v:.3f}" for n, v in data.bands.items()],
            ]
            print("\n".join(lines), end="", flush=True)
            time.sleep(0.033)
    except KeyboardInterrupt:
        pass
    finally:
        capture.stop()
        print("\nStopped.")


def _list_devices() -> None:
    print("Available input devices:\n")
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            print(f"  [{i:2d}] {dev['name']}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(prog="audioprism")
    parser.add_argument("--tui", action="store_true", help="Terminal monitor instead of GUI")
    parser.add_argument("--list-devices", action="store_true", help="List input devices and exit")
    parser.add_argument("--selftest", action="store_true", help="Launch GUI and quit after 2s")
    args = parser.parse_args()

    if args.list_devices:
        _list_devices()
        return

    settings = VisualizerSettings.load()

    if args.tui:
        device, sources = _pick_source(settings, prefer_system=True)
        if device is None:
            print("No audio sources found.")
            sys.exit(1)
        _run_terminal(device)
        return

    sys.exit(_run_gui(settings, selftest=args.selftest))


if __name__ == "__main__":
    main()
