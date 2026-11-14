# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from qgis.PyQt.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QLineEdit,
                                QScrollArea, QSpinBox, QWidget)

from ..core.options import Options

CHOICES = {
    "time_mode": [("Order index (dates blank)", "index"), ("Acquisition dates", "dates")],
    "metric": [("Net effect vs pre counterfactual", "net_effect"), ("Slope change", "slope_change")],
    "covariance": [("Classical OLS", "ols"), ("Newey-West", "newey_west")],
    "bias": [("None", "none"), ("Expectation inversion", "expectation_inversion")],
    "resampling": [(v.capitalize(), v) for v in ("nearest", "bilinear", "cubic", "average")],
}
LABELS = {
    "time_mode": "Time coordinate", "interruption": "Interruption T0 (blank = automatic)",
    "include_event": "Include event-straddling observations in Post fit",
    "metric": "Recovery map metric", "evaluation_time": "Evaluation k (blank = last observation)",
    "min_pre": "Minimum valid Pre observations", "min_post": "Minimum valid Post observations",
    "covariance": "Standard errors", "nw_lags": "Newey-West maximum lag",
    "bias": "Coherence bias correction", "lookup_points": "Lookup table points",
    "low_threshold": "Low-coherence threshold (blank = off)",
    "resample": "Explicitly resample mismatched grids to first Pre grid",
    "resampling": "Resampling method", "block_size": "Block side (pixels)",
    "nodata": "Output nodata", "histogram_bins": "Histogram bins", "dpi": "PNG DPI",
    "aoi_path": "AOI polygon file (blank = full extent)",
    "features_path": "Point/polygon file for feature series (optional)",
    "all_touched": "Include all polygon-touched pixels",
    "pixel_csv": "Export per-pixel coefficient CSV", "pixel_step": "Pixel sampling step",
    "pixel_cap": "Maximum pixel CSV rows",
}
INTEGER_MIN = {"min_pre": 2, "min_post": 2, "nw_lags": 0, "lookup_points": 16,
               "block_size": 1, "histogram_bins": 1, "dpi": 50, "pixel_step": 1, "pixel_cap": 1}
OPTIONAL_FLOAT = {"interruption", "evaluation_time", "low_threshold"}


class OptionFields(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        container = QWidget()
        form = QFormLayout(container)
        self.fields = {}
        defaults = Options([], "")
        for name, label in LABELS.items():
            value = getattr(defaults, name)
            if name in CHOICES:
                widget = QComboBox()
                for text, data in CHOICES[name]:
                    widget.addItem(text, data)
                widget.setCurrentIndex(widget.findData(value))
            elif isinstance(value, bool):
                widget = QCheckBox()
                widget.setChecked(value)
            elif name in INTEGER_MIN:
                widget = QSpinBox()
                widget.setRange(INTEGER_MIN[name],
                                65537 if name == "lookup_points" else 2147483647)
                widget.setValue(value)
            else:
                widget = QLineEdit("" if value is None else str(value))
            widget.setAccessibleName(label)
            form.addRow(label, widget)
            self.fields[name] = widget
        self.setWidget(container)

    def values(self):
        values = {}
        for name, widget in self.fields.items():
            if name in CHOICES:
                values[name] = widget.currentData()
            elif isinstance(widget, QCheckBox):
                values[name] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                values[name] = widget.value()
            elif name in OPTIONAL_FLOAT:
                values[name] = float(widget.text()) if widget.text().strip() else None
            elif name == "nodata":
                values[name] = float(widget.text())
            else:
                values[name] = widget.text().strip()
        return values
