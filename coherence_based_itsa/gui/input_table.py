# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from pathlib import Path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QHBoxLayout,
                                QHeaderView, QLabel, QPushButton, QTableWidget,
                                QTableWidgetItem, QVBoxLayout, QWidget)
from qgis.core import QgsProject, QgsRasterLayer

from ..core.naming import describe
from ..core.options import Observation

PHASES = (("PRE", "pre"), ("EVENT", "event"), ("POST", "post"))
COLUMNS = ("Phase", "Start date", "End date (pairs)", "Looks", "Band", "Raster")
EXTENSIONS = (".tif", ".tiff", ".img", ".vrt")
ROLE = Qt.ItemDataRole.UserRole


class InputTable(QWidget):
    """One table for every coherence raster; phase and dates are read from file names."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setWordWrap(False)
        self.table.setMinimumHeight(220)
        layout.addWidget(self.table)
        controls = QHBoxLayout()
        for label, callback in (("Add files…", self.add_files), ("Add folder…", self.add_folder),
                                ("Add open raster layers", self.add_layers),
                                ("Remove selected", self.remove), ("Clear", self.clear)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            controls.addWidget(button)
        controls.addStretch(1)
        layout.addLayout(controls)
        self.summary = QLabel()
        layout.addWidget(self.summary)
        self.refresh()

    def paths(self):
        return {self.table.item(row, 5).data(ROLE) for row in range(self.table.rowCount())}

    def append(self, path, phase=None):
        path = str(path)
        if path in self.paths():
            return
        guessed, start, end = describe(path)
        row = self.table.rowCount()
        self.table.insertRow(row)
        combo = QComboBox()
        for label, value in PHASES:
            combo.addItem(label, value)
        combo.setCurrentIndex(max(0, combo.findData(phase or guessed or "pre")))
        combo.currentIndexChanged.connect(self.refresh)
        self.table.setCellWidget(row, 0, combo)
        for column, value in ((1, start), (2, end), (3, "4"), (4, "1")):
            self.table.setItem(row, column, QTableWidgetItem(value))
        item = QTableWidgetItem(Path(path).name)
        item.setData(ROLE, path)
        item.setToolTip(path)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 5, item)
        self.refresh()

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add coherence rasters", "",
            "Rasters (*.tif *.tiff *.img *.vrt);;All files (*)")
        for path in sorted(paths):
            self.append(path)
        self.sort()

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Folder of coherence rasters")
        if folder:
            for path in sorted(Path(folder).iterdir()):
                if path.suffix.lower() in EXTENSIONS:
                    self.append(path)
            self.sort()

    def add_layers(self):
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer) and layer.providerType() == "gdal":
                self.append(layer.source().split("|")[0])
        self.sort()

    def remove(self):
        for row in sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)
        self.refresh()

    def clear(self):
        self.table.setRowCount(0)
        self.refresh()

    def sort(self):
        """Order rows by date when every row has one, keeping the phase order otherwise."""
        records = self.observations()
        if not records:
            return
        order = {"pre": 0, "event": 1, "post": 2}
        dated = all(o.date for o in records)
        records.sort(key=(lambda o: (o.date, o.end_date)) if dated
                     else (lambda o: order[o.phase]))
        self.table.setRowCount(0)
        for o in records:
            self.append(o.path, o.phase)
            row = self.table.rowCount() - 1
            for column, value in ((1, o.date), (2, o.end_date), (3, f"{o.looks:g}"),
                                  (4, str(o.band))):
                self.table.item(row, column).setText(value)
        self.refresh()

    def observations(self):
        records = []
        for row in range(self.table.rowCount()):
            text = [self.table.item(row, column).text().strip() for column in range(1, 5)]
            try:
                looks, band = float(text[2] or 4), int(text[3] or 1)
            except ValueError:
                raise ValueError(f"Row {row + 1}: looks and band must be numbers.") from None
            records.append(Observation(self.table.item(row, 5).data(ROLE),
                                       self.table.cellWidget(row, 0).currentData(),
                                       text[0], looks, band, text[1]))
        return records

    def refresh(self):
        counts = {value: 0 for _, value in PHASES}
        for row in range(self.table.rowCount()):
            counts[self.table.cellWidget(row, 0).currentData()] += 1
        self.summary.setText(
            f"{counts['pre']} PRE, {counts['event']} EVENT, {counts['post']} POST. "
            "At least 2 PRE and 2 POST are required; 3 or more of each give standard errors.")
