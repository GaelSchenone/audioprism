"""Narrow icon sidebar: ⚙ opens the options flyout, ⧉ opens the output window."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget


class Sidebar(QWidget):
    options_clicked = Signal()
    output_clicked = Signal()
    reset_clicked = Signal()
    recording_clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setFixedWidth(48)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 8, 5, 8)
        layout.setSpacing(8)

        self.options_btn = QPushButton("⚙")
        self.options_btn.setFixedSize(38, 38)
        self.options_btn.setToolTip("Options")
        self.options_btn.clicked.connect(self.options_clicked.emit)

        self.reset_btn = QPushButton("⟲")
        self.reset_btn.setFixedSize(38, 38)
        self.reset_btn.setToolTip("Reset 3D view (R)")
        self.reset_btn.clicked.connect(self.reset_clicked.emit)

        self.output_btn = QPushButton("⧉")
        self.output_btn.setFixedSize(38, 38)
        self.output_btn.setToolTip("Open output window (drag to a monitor, then fullscreen)")
        self.output_btn.clicked.connect(self.output_clicked.emit)

        self.record_btn = QPushButton("⏺")
        self.record_btn.setFixedSize(38, 38)
        self.record_btn.setToolTip("Record video (Ctrl+R)")
        self.record_btn.clicked.connect(self.recording_clicked.emit)

        layout.addWidget(self.options_btn)
        layout.addWidget(self.reset_btn)
        layout.addWidget(self.output_btn)
        layout.addWidget(self.record_btn)
        layout.addStretch(1)

    def set_recording(self, active: bool) -> None:
        self.record_btn.setText("⏹" if active else "⏺")
        self.record_btn.setToolTip("Stop recording" if active else "Record video (Ctrl+R)")
