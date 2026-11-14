# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from datetime import datetime, timezone
from pathlib import Path

from qgis.PyQt.QtWidgets import QCheckBox, QFormLayout, QGroupBox
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorFileWriter
from qgis.gui import QgsMapLayerComboBox


class FeatureSelection(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Optional project feature series", parent)
        layout = QFormLayout(self)
        self.enabled = QCheckBox("Use a project layer instead of the feature file")
        self.layer = QgsMapLayerComboBox()
        self.layer.setFilters(QgsMapLayerProxyModel.PointLayer | QgsMapLayerProxyModel.PolygonLayer)
        self.layer.setAllowEmptyLayer(True)
        self.selected = QCheckBox("Selected features only")
        layout.addRow(self.enabled)
        layout.addRow("Layer", self.layer)
        layout.addRow(self.selected)

    def snapshot(self, output_folder):
        if not self.enabled.isChecked():
            return None
        layer = self.layer.currentLayer()
        if layer is None:
            raise ValueError("Choose a point or polygon layer for feature series.")
        if self.selected.isChecked() and not layer.selectedFeatureCount():
            raise ValueError("No features are selected in the chosen layer.")
        directory = Path(output_folder) / "input_snapshots"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = directory / ("features_" + stamp + ".gpkg")
        settings = QgsVectorFileWriter.SaveVectorOptions()
        settings.driverName = "GPKG"
        settings.onlySelectedFeatures = self.selected.isChecked()
        error, message, *_ = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, str(path), QgsProject.instance().transformContext(), settings)
        if error != QgsVectorFileWriter.NoError:
            raise ValueError("Could not save feature snapshot: " + message)
        return str(path)
