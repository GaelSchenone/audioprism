"""Custom graphics-palette editor + gradient swatch preview.

Create a palette from color stops (native color pickers), set its background,
name it, and Save — it's registered and persisted to palettes.json. Custom
palettes can be deleted.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.config.theme import Palette
from src.gui.controller import Controller


class GradientSwatch(QWidget):
    """Paints a palette's gradient as a horizontal bar."""

    def __init__(self, palette: Palette | None = None, height: int = 18) -> None:
        super().__init__()
        self._palette = palette
        self.setFixedHeight(height)

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def paintEvent(self, _event) -> None:
        if self._palette is None:
            return
        painter = QPainter(self)
        grad = QLinearGradient(0, 0, self.width(), 0)
        cols = self._palette.colors
        n = len(cols)
        for i, c in enumerate(cols):
            grad.setColorAt(i / (n - 1) if n > 1 else 0.0, QColor.fromRgbF(*c))
        painter.fillRect(self.rect(), grad)


def _style_color_button(btn: QPushButton, color: QColor) -> None:
    btn.setStyleSheet(f"background:{color.name()}; border:1px solid #888;")


class PaletteEditor(QDialog):
    palette_saved = Signal(str)

    def __init__(self, controller: Controller, current_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Palette editor")
        self.resize(360, 500)
        self.controller = controller
        self.registry = controller.registry
        self.colors: list[QColor] = []
        self.bg = QColor(10, 10, 12)

        lay = QVBoxLayout(self)

        lay.addWidget(QLabel("Start from"))
        self.base = QComboBox()
        self.base.addItems(self.registry.palette_names())
        self.base.setCurrentText(current_name)
        self.base.currentTextChanged.connect(self._load_base)
        lay.addWidget(self.base)

        self.swatch = GradientSwatch(height=26)
        lay.addWidget(self.swatch)

        lay.addWidget(QLabel("Colors (low → high)"))
        self.stops_box = QWidget()
        self.stops_layout = QVBoxLayout(self.stops_box)
        self.stops_layout.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stops_box)
        add = QPushButton("+ Add color")
        add.clicked.connect(self._add_stop)
        lay.addWidget(add)

        bg_row = QHBoxLayout()
        bg_row.addWidget(QLabel("Background"))
        self.bg_btn = QPushButton()
        self.bg_btn.setFixedWidth(70)
        self.bg_btn.clicked.connect(self._pick_bg)
        bg_row.addWidget(self.bg_btn)
        bg_row.addStretch(1)
        lay.addLayout(bg_row)

        lay.addWidget(QLabel("Name"))
        self.name = QLineEdit()
        lay.addWidget(self.name)

        lay.addStretch(1)

        btns = QHBoxLayout()
        save = QPushButton("Save")
        save.clicked.connect(self._save)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        btns.addWidget(save)
        btns.addWidget(self.delete_btn)
        btns.addWidget(close)
        lay.addLayout(btns)

        self._load_base(current_name)

    # ── state ──
    def _load_base(self, name: str) -> None:
        pal = self.registry.get_palette(name)
        self.colors = [QColor.fromRgbF(*c) for c in pal.colors]
        self.bg = QColor.fromRgbF(*pal.background)
        self.name.setText(name if pal.custom else f"{name}_custom")
        self.delete_btn.setEnabled(pal.custom)
        self._rebuild_stops()
        self._refresh()

    def _rebuild_stops(self) -> None:
        while self.stops_layout.count():
            item = self.stops_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, c in enumerate(self.colors):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            btn = QPushButton()
            btn.setFixedHeight(22)
            _style_color_button(btn, c)
            btn.clicked.connect(lambda _=False, idx=i: self._pick_stop(idx))
            rm = QPushButton("✕")
            rm.setFixedWidth(28)
            rm.clicked.connect(lambda _=False, idx=i: self._remove_stop(idx))
            rl.addWidget(btn)
            rl.addWidget(rm)
            self.stops_layout.addWidget(row)

    def _current_palette(self) -> Palette:
        cols = [(c.redF(), c.greenF(), c.blueF()) for c in self.colors]
        return Palette(
            name="_preview",
            colors=cols or [(1, 1, 1)],
            background=(self.bg.redF(), self.bg.greenF(), self.bg.blueF()),
        )

    def _refresh(self) -> None:
        self.swatch.set_palette(self._current_palette())
        _style_color_button(self.bg_btn, self.bg)

    # ── handlers ──
    def _pick_stop(self, idx: int) -> None:
        color = QColorDialog.getColor(self.colors[idx], self, "Pick color")
        if color.isValid():
            self.colors[idx] = color
            self._rebuild_stops()
            self._refresh()

    def _remove_stop(self, idx: int) -> None:
        if len(self.colors) > 2:
            del self.colors[idx]
            self._rebuild_stops()
            self._refresh()

    def _add_stop(self) -> None:
        self.colors.append(QColor(self.colors[-1]) if self.colors else QColor(255, 255, 255))
        self._rebuild_stops()
        self._refresh()

    def _pick_bg(self) -> None:
        color = QColorDialog.getColor(self.bg, self, "Pick background")
        if color.isValid():
            self.bg = color
            self._refresh()

    def _save(self) -> None:
        name = self.name.text().strip()
        if not name:
            return
        pal = self._current_palette()
        pal.name = name
        self.registry.add_palette(pal)            # registers + persists
        if self.base.findText(name) < 0:
            self.base.addItem(name)
        self.palette_saved.emit(name)

    def _delete(self) -> None:
        name = self.base.currentText()
        self.registry.remove_palette(name)
        if name in self.registry.palettes:
            return
        self.base.removeItem(self.base.currentIndex())
        self.palette_saved.emit(self.base.currentText())
