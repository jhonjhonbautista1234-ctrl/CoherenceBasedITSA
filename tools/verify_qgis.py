# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

"""Offscreen QGIS check of the plugin: Processing algorithm and the dialog workflow.

python-qgis.bat tools/verify_qgis.py [raster folder] [AOI vector file]

Without arguments the bundled sample rasters are used. With a folder, the dialog is
filled exactly as a user would (Add folder, AOI file, Run) on that real data.
"""

import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from qgis.core import (Qgis, QgsApplication, QgsProcessingContext, QgsProcessingFeedback,
                       QgsProject)
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


def layer_summary():
    project = QgsProject.instance()
    renderers = {layer.name(): layer.renderer().type()
                 for layer in project.mapLayers().values() if hasattr(layer, "renderer")
                 and layer.type() == Qgis.LayerType.Raster}
    return len(project.mapLayers()), renderers


work = root / "tmp" / "qgis_verification"
plugin = CoherenceBasedItsa(TestInterface())
plugin.initGui()
report = dict(qgis_version=Qgis.QGIS_VERSION)

# 1. Processing algorithm on the synthetic stack.
options = make_stack(work)
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
assert Path(result["RECOVERY"]).name == "recovery.tif"
assert Path(result["CLASSES"]).name == "recovery_class.tif"
report["processing_run"] = result["RUN_FOLDER"]

# 2. The dialog, driven the way a user drives it.
plugin.show_dialog()
dialog = plugin.dialog
if len(sys.argv) > 1:
    for path in sorted(Path(sys.argv[1]).iterdir()):
        if path.suffix.lower() in (".tif", ".tiff"):
            dialog.inputs.append(path)
    if len(sys.argv) > 2:
        dialog.aoi.path.setText(sys.argv[2])
    output = root / "test_outputs" / "qgis_dialog"
else:
    for path in sorted((root / "coherence_based_itsa" / "sample").glob("*.tif")):
        dialog.inputs.append(path)
    dialog.options.fields["block_size"].setValue(2)
    output = work / "dialog_outputs"
dialog.inputs.sort()
report["table"] = [f"{o.phase} {o.date} {o.end_date}".strip()
                   for o in dialog.inputs.observations()]
dialog.output.setText(str(output))
started = time.time()
dialog.start()
assert dialog.task is not None, "the dialog refused to start"
while dialog.task is not None:
    app.processEvents()
    time.sleep(0.05)
    assert time.time() - started < 1800, "timed out"
report["dialog_seconds"] = round(time.time() - started, 1)
report["dialog_status"] = dialog.status.text()
assert dialog.status.text().startswith("Saved: "), dialog.status.text()
count, renderers = layer_summary()
report["project_layers"] = count
report["renderers"] = {name: renderers[name] for name in ("recovery", "recovery class")}
assert renderers["recovery"] == "singlebandpseudocolor", renderers
assert renderers["recovery class"] == "paletted", renderers
assert count == 15 + 3, count
assert plugin.results, "results window was not opened"

plugin.unload()
assert app.processingRegistry().providerById("coherence_itsa") is None
report["status"] = "passed"
print(json.dumps(report, indent=2))
QgsProject.instance().clear()
