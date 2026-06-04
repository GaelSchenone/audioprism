"""Small reusable widgets for the panels."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QSlider, QVBoxLayout, QWidget


class LabeledSlider(QWidget):
    """A slider with a header showing its label and current value."""

    changed = Signal(float)

    def __init__(
        self,
        label: str,
        lo: float,
        hi: float,
        value: float,
        integer: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.lo, self.hi, self.integer = lo, hi, integer
        self._label = label
        self._fmt = "{:.0f}" if integer else "{:.2f}"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.header = QLabel()
        layout.addWidget(self.header)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setValue(self._to_pos(value))
        self.slider.valueChanged.connect(self._on_change)
        layout.addWidget(self.slider)
        self._update_header(value)

    def _to_pos(self, v: float) -> int:
        return int(round((v - self.lo) / (self.hi - self.lo) * 1000))

    def value(self) -> float:
        v = self.lo + (self.slider.value() / 1000.0) * (self.hi - self.lo)
        return int(round(v)) if self.integer else v

    def _on_change(self) -> None:
        v = self.value()
        self._update_header(v)
        self.changed.emit(float(v))

    def _update_header(self, v: float) -> None:
        self.header.setText(f"{self._label}: {self._fmt.format(v)}")
