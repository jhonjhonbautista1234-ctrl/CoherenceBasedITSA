# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from qgis.PyQt.QtWidgets import (QAbstractItemView, QFileDialog, QHBoxLayout, QHeaderView,
                                QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox

from ..core.options import Observation


class InputGroup(QWidget):
    def __init__(self, phase, parent=None):
        super().__init__(parent)
        self.phase = phase
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Raster path", "Date (YYYY-MM-DD or blank)", "Looks L", "Band"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(160)
        layout.addWidget(self.table)
        controls = QHBoxLayout()
        self.layers = QgsMapLayerComboBox()
        self.layers.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.layers.setAllowEmptyLayer(True)
        controls.addWidget(self.layers)
        for label, callback in (("Add layer", self.add_layer), ("Add files", self.add_files),
                                ("Remove", self.remove), ("Up", lambda: self.move(-1)),
                                ("Down", lambda: self.move(1))):
            button = QPushButton(label)
            button.clicked.connect(callback)
            controls.addWidget(button)
        layout.addLayout(controls)

    def append(self, path):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for column, value in enumerate([path, "", "4", "1"]):
            self.table.setItem(row, column, QTableWidgetItem(value))

    def add_layer(self):
        layer = self.layers.currentLayer()
        if layer:
            self.append(layer.source().split("|")[0])

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add coherence rasters", "",
                                               "Rasters (*.tif *.tiff *.img *.vrt);;All files (*)")
        for path in paths:
            self.append(path)

    def remove(self):
        rows = sorted({item.row() for item in self.table.selectedItems()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def move(self, direction):
        row = self.table.currentRow()
        target = row + direction
        if row < 0 or not 0 <= target < self.table.rowCount():
            return
        for column in range(self.table.columnCount()):
            item = self.table.takeItem(row, column)
            other = self.table.takeItem(target, column)
            self.table.setItem(row, column, other)
            self.table.setItem(target, column, item)
        self.table.selectRow(target)

    def observations(self):
        records = []
        for row in range(self.table.rowCount()):
            values = [self.table.item(row, col).text().strip() for col in range(4)]
            records.append(Observation(values[0], self.phase, values[1],
                                       float(values[2]), int(values[3])))
        return records
