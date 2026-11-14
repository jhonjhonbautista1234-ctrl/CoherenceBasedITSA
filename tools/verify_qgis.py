# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qgis.core import Qgis, QgsApplication, QgsProcessingContext, QgsProcessingFeedback, QgsProject
from qgis.PyQt.QtWidgets import QMainWindow

app = QgsApplication([], True)
app.initQgis()
from coherence_based_itsa.plugin import CoherenceBasedItsa
from tests.fixtures import make_stack


class TestInterface:
    def __init__(self):
        self.window = QMainWindow()
        self.actions = []

    def mainWindow(self):
        return self.window

    def addPluginToRasterMenu(self, name, action):
        self.actions.append(action)

    def removePluginRasterMenu(self, name, action):
        self.actions.remove(action)


root = Path(__file__).resolve().parents[1]
options = make_stack(root / "tmp" / "qgis_verification")
iface = TestInterface()
plugin = CoherenceBasedItsa(iface)
plugin.initGui()
plugin.show_dialog()
algorithm = app.processingRegistry().algorithmById("coherence_itsa:coherence_itsa")
assert algorithm is not None
context = QgsProcessingContext()
context.setProject(QgsProject.instance())
parameters = dict(PRE=[o.path for o in options.observations if o.phase == "pre"],
                  EVENT=[o.path for o in options.observations if o.phase == "event"],
                  POST=[o.path for o in options.observations if o.phase == "post"],
                  OBSERVATIONS="[]", OPTIONS=json.dumps(dict(block_size=2, dpi=50)),
                  OUTPUT=options.output_folder)
result, success = algorithm.run(parameters, context, QgsProcessingFeedback())
assert success, result
assert Path(result["RECOVERY"]).is_file()
from coherence_based_itsa.core.options import RunResult
folder = Path(result["RUN_FOLDER"])
run_result = RunResult(str(folder), result["RASTERS"],
                       [str(folder / "series.csv"), str(folder / "coefficients.csv")],
                       [str(folder / "series_0000.png"), str(folder / "recovery_histogram.png")])
plugin.load_result(run_result)
assert len(QgsProject.instance().mapLayers()) == len(result["RASTERS"]) + 2
assert plugin.dialog.options.values()["metric"] == "net_effect"
plugin.unload()
assert app.processingRegistry().providerById("coherence_itsa") is None
print(json.dumps(dict(status="passed", qgis_version=Qgis.QGIS_VERSION,
                       processing_outputs=result, project_layers=len(QgsProject.instance().mapLayers()))))
QgsProject.instance().clear()
