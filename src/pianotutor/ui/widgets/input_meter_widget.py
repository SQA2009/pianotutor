"""Input level meter panel for live diagnostics."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget


class InputMeterPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._status = QLabel("Input idle")

        row = QHBoxLayout()
        row.addWidget(QLabel("Input"))
        row.addWidget(self._bar, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self._status)

    def set_level(self, level) -> None:
        if level is None:
            self._bar.setValue(0)
            self._status.setText("Input idle")
            return

        rms = float(getattr(level, "rms", 0.0))
        peak = float(getattr(level, "peak", 0.0))
        clipping = bool(getattr(level, "is_clipping", False))

        value = max(0, min(100, int(rms * 220)))
        self._bar.setValue(value)

        if clipping:
            self._status.setText("Clipping detected")
        elif peak < 0.01:
            self._status.setText("Input very low")
        else:
            self._status.setText(f"RMS {rms:.3f} · Peak {peak:.3f}")
