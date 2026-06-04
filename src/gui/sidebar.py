"""Narrow icon sidebar: ⚙ opens the options flyout, ⧉ opens the output window."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget


class Sidebar(QWidget):
    options_clicked = Signal()
    output_clicked = Signal()
    reset_clicked = Signal()

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

        layout.addWidget(self.options_btn)
        layout.addWidget(self.reset_btn)
        layout.addWidget(self.output_btn)
        layout.addStretch(1)
