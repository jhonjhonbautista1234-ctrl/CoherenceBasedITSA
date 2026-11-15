# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from pathlib import Path

from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QIcon
try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsApplication, QgsProject, QgsRasterLayer, QgsVectorLayer

from .processing import ItsaAlgorithm, ItsaProvider


class CoherenceBasedItsa:
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.results = []
        self.provider = None
        self.action = None

    def initGui(self):
        self.action = QAction(QIcon(str(Path(__file__).parent / "icon.png")),
                              "Coherence Based ITSA", self.iface.mainWindow())
        self.action.triggered.connect(self.show_dialog)
        self.iface.addPluginToRasterMenu("Coherence Based ITSA", self.action)
        self.provider = ItsaProvider()
        ItsaAlgorithm.viewer = self.show_results
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):
        if self.dialog:
            self.dialog.cancel()
            self.dialog.hide()
        if self.action:
            self.iface.removePluginRasterMenu("Coherence Based ITSA", self.action)
            self.action.deleteLater()
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
        ItsaAlgorithm.viewer = None

    def show_dialog(self):
        if self.dialog is None:
            from .gui.dialog import ItsaDialog
            self.dialog = ItsaDialog(self.iface, self.load_result)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def load_result(self, result):
        # The two recovery maps go on top and open styled (.qml beside each raster);
        # the remaining model rasters are grouped and switched off.
        project = QgsProject.instance()
        group = project.layerTreeRoot().insertGroup(0, Path(result.folder).name)
        details = group.addGroup("Model details")
        details.setExpanded(False)
        for path in result.rasters:
            name = Path(path).stem
            layer = QgsRasterLayer(path, name.replace("_", " "))
            if not layer.isValid():
                continue
            project.addMapLayer(layer, False)
            if name == "recovery":
                group.insertLayer(0, layer)
            elif name == "recovery_class":
                group.insertLayer(1, layer).setItemVisibilityChecked(False)
            else:
                details.addLayer(layer).setItemVisibilityChecked(False)
        for path in result.tables:
            uri = QUrl.fromLocalFile(path).toString() + "?type=csv&geomType=none&detectTypes=yes"
            layer = QgsVectorLayer(uri, Path(path).stem, "delimitedtext")
            if layer.isValid():
                project.addMapLayer(layer, False)
                group.addLayer(layer)
        self.show_results(result)

    def show_results(self, result):
        from .gui.results import ResultsDialog
        viewer = ResultsDialog(result, self.iface.mainWindow())
        self.results.append(viewer)
        viewer.show()
