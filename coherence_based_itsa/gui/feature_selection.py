# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from datetime import datetime
from pathlib import Path

from qgis.PyQt.QtWidgets import (QCheckBox, QFileDialog, QHBoxLayout, QLineEdit, QPushButton,
                                QWidget)
from qgis.core import QgsProject, QgsVectorFileWriter
from qgis.gui import QgsMapLayerComboBox

try:
    from qgis.core import Qgis
    POLYGONS, POINTS = Qgis.LayerFilter.PolygonLayer, Qgis.LayerFilter.PointLayer
except (ImportError, AttributeError):
    from qgis.core import QgsMapLayerProxyModel
    POLYGONS = QgsMapLayerProxyModel.Filter.PolygonLayer
    POINTS = QgsMapLayerProxyModel.Filter.PointLayer

VECTORS = "Vector files (*.gpkg *.shp *.kml *.kmz *.geojson *.json);;All files (*)"


class VectorInput(QWidget):
    """Pick a vector source: a project layer, or a file on disk."""

    def __init__(self, points=False, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.layer = QgsMapLayerComboBox()
        self.layer.setFilters(POLYGONS | POINTS if points else POLYGONS)
        self.layer.setAllowEmptyLayer(True)
        self.layer.setCurrentIndex(0)
        self.path = QLineEdit()
        self.path.setPlaceholderText("or a file: .gpkg, .shp, .kml, .geojson")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.choose)
        self.selected = QCheckBox("Selected only")
        for widget in (self.layer, self.path, browse, self.selected):
            layout.addWidget(widget)
        layout.setStretch(1, 1)

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose vector file", self.path.text(), VECTORS)
        if path:
            self.path.setText(path)

    def resolve(self, output_folder, label):
        """Return a file path for the engine, or an empty string when nothing is chosen."""
        if self.path.text().strip():
            if not Path(self.path.text().strip()).is_file():
                raise ValueError(f"{label} file does not exist.")
            return self.path.text().strip()
        layer = self.layer.currentLayer()
        if layer is None:
            return ""
        if self.selected.isChecked() and not layer.selectedFeatureCount():
            raise ValueError(f"No features are selected in the {label} layer.")
        directory = Path(output_folder) / "input_snapshots"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = directory / f"{label.lower().replace(' ', '_')}_{stamp}.gpkg"
        settings = QgsVectorFileWriter.SaveVectorOptions()
        settings.driverName = "GPKG"
        # A source field called fid would clash with the GeoPackage key column.
        settings.layerOptions = ["FID=itsa_fid"]
        settings.onlySelectedFeatures = self.selected.isChecked()
        error, message, *_ = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, str(path), QgsProject.instance().transformContext(), settings)
        if error != QgsVectorFileWriter.WriterError.NoError:
            raise ValueError(f"Could not save the {label} layer: {message}")
        return str(path)
