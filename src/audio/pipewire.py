"""PipeWire/PulseAudio source discovery.

PipeWire natively exposes each app's audio stream as a capture source in
sounddevice, so no null-sink loopback is needed. We enumerate sources directly
from sounddevice and enrich the list with process names from pactl.
"""

import json
import subprocess
from dataclasses import dataclass


# ── pactl helpers ─────────────────────────────────────────────────────────────

def _pactl_sink_inputs() -> list[dict]:
    try:
        out = subprocess.check_output(
            ["pactl", "--format=json", "list", "sink-inputs"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return json.loads(out)
    except Exception:
        return []


def _pactl_app_names() -> dict[str, str]:
    """Return {app_name: binary} for apps currently playing audio."""
    result: dict[str, str] = {}
    for item in _pactl_sink_inputs():
        props = item.get("properties", {})
        name = props.get("application.name") or props.get("media.name") or ""
        binary = props.get("application.process.binary", "?")
        if name:
            result[name] = binary
    return result


# ── AudioSource ────────────────────────────────────────────────────────────────

@dataclass
class AudioSource:
    device_index: int   # sounddevice device index
    name: str           # display name shown to the user
    kind: str           # 'system' | 'app'

    def __str__(self) -> str:
        tag = "System output" if self.kind == "system" else "App"
        return f"{tag}: {self.name}"


# ── Source enumeration ─────────────────────────────────────────────────────────

def list_sources() -> list[AudioSource]:
    """
    Return all capturable audio sources:
      - System output monitors (speaker / headphone outputs)
      - Per-app streams exposed by PipeWire as capture sources
    """
    import sounddevice as sd

    app_names = _pactl_app_names()
    sources: list[AudioSource] = []
    seen_apps: set[str] = set()

    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] == 0:
            continue
        name: str = dev["name"]
        lower = name.lower()

        # System output monitors
        is_output_monitor = (
            ("headphone" in lower or "speaker" in lower)
            and "microphone" not in lower
            and "mic" not in lower
        )
        if is_output_monitor:
            sources.append(AudioSource(device_index=i, name=name, kind="system"))
            continue

        # Per-app streams (PipeWire exposes them with the app's name)
        if name in app_names and name not in seen_apps:
            seen_apps.add(name)
            binary = app_names[name]
            display = f"{name} ({binary})" if binary != name else name
            sources.append(AudioSource(device_index=i, name=display, kind="app"))

    # Fallback: if no system monitor found, add 'pulse' as catch-all
    if not any(s.kind == "system" for s in sources):
        for i, dev in enumerate(sd.query_devices()):
            if dev["name"] in ("pulse", "pipewire") and dev["max_input_channels"] > 0:
                sources.append(AudioSource(device_index=i, name=dev["name"], kind="system"))
                break

    return sources


# ── Legacy AppMonitor (PulseAudio fallback, not used on PipeWire) ─────────────

@dataclass
class _LegacyApp:
    index: int
    name: str
    binary: str

    def __str__(self) -> str:
        return f"{self.name} ({self.binary})"


class AppMonitor:
    """
    PulseAudio fallback: routes an app through a null sink so we can capture
    its audio. Not needed on PipeWire where apps are native capture sources.
    """

    def __init__(self, app: _LegacyApp) -> None:
        self.app = app
        self.monitor_source: str = ""
        self._modules: list[int] = []
        self._original_sink: str | None = None

    def __enter__(self) -> "AppMonitor":
        sink_name = f"audioprism_{self.app.index}"

        for item in _pactl_sink_inputs():
            if item.get("index") == self.app.index:
                raw = item.get("sink")
                self._original_sink = str(raw) if raw is not None else None
                break

        mod_id = int(subprocess.check_output(
            ["pactl", "load-module", "module-null-sink",
             f"sink_name={sink_name}",
             "sink_properties=device.description=audioprism_monitor"],
            text=True,
        ).strip())
        self._modules.append(mod_id)

        if self._original_sink:
            try:
                mod_id = int(subprocess.check_output(
                    ["pactl", "load-module", "module-loopback",
                     f"source={sink_name}.monitor",
                     f"sink={self._original_sink}"],
                    text=True,
                ).strip())
                self._modules.append(mod_id)
            except Exception:
                pass

        subprocess.run(
            ["pactl", "move-sink-input", str(self.app.index), sink_name],
            check=True, stderr=subprocess.DEVNULL,
        )
        self.monitor_source = f"{sink_name}.monitor"
        return self

    def __exit__(self, *_) -> None:
        if self._original_sink:
            subprocess.run(
                ["pactl", "move-sink-input", str(self.app.index), self._original_sink],
                check=False, stderr=subprocess.DEVNULL,
            )
        for mod_id in reversed(self._modules):
            subprocess.run(
                ["pactl", "unload-module", str(mod_id)],
                check=False, stderr=subprocess.DEVNULL,
            )
