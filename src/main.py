"""audioprism — entry point. Phase 1: terminal audio monitor."""

import sys
import time
import argparse

import sounddevice as sd

from src.audio.pipewire import list_sources, AudioSource
from src.audio.capture import AudioCapture
from src.audio.analyzer import AudioAnalyzer


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

            beat_tag = "  ★ BEAT" if data.beat else ""
            bpm_tag = f"  {data.bpm:.0f} BPM" if data.bpm else ""

            lines = [
                "\033[H\033[J",
                f"vol      {_bar(data.volume)} {data.volume:.2f}{beat_tag}{bpm_tag}",
                "",
                *[
                    f"{name:<10} {_bar(v)} {v:.3f}"
                    for name, v in data.bands.items()
                ],
            ]
            print("\n".join(lines), end="", flush=True)
            time.sleep(0.033)

    except KeyboardInterrupt:
        pass
    finally:
        capture.stop()
        print("\nStopped.")


def _select_source() -> AudioSource:
    sources = list_sources()

    if not sources:
        print("No audio sources detected. Is PipeWire/PulseAudio running?")
        sys.exit(1)

    print("=== audioprism — source selection ===\n")
    for i, src in enumerate(sources):
        print(f"[{i}] {src}")

    print()
    raw = input(f"Select source (default 0): ").strip() or "0"
    return sources[int(raw)]


def _list_devices() -> None:
    print("Available input devices:\n")
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            print(f"  [{i:2d}] {dev['name']}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="audioprism")
    parser.add_argument("--system", action="store_true", help="Auto-select system output monitor")
    parser.add_argument("--list-devices", action="store_true", help="List input devices and exit")
    args = parser.parse_args()

    if args.list_devices:
        _list_devices()
        return

    if args.system:
        sources = list_sources()
        system = next((s for s in sources if s.kind == "system"), None)
        if not system:
            print("No system output monitor found.")
            sys.exit(1)
        source = system
    else:
        source = _select_source()

    print(f"\nUsing: {source}  (device index {source.device_index})\n")
    _run_terminal(source.device_index)


if __name__ == "__main__":
    main()
