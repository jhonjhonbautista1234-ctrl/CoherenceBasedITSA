# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

import json
import os
from pathlib import Path

from qgis.core import QgsProject
from qgis.PyQt.QtCore import QTimer
from qgis.utils import loadPlugin, plugins, startPlugin

root = Path(os.environ["ITSA_WORKSPACE"])
state_path = root / "tmp" / "gui_smoke.json"


def start():
    try:
        if "coherence_based_itsa" not in plugins:
            assert loadPlugin("coherence_based_itsa")
            assert startPlugin("coherence_based_itsa")
        plugin = plugins["coherence_based_itsa"]
        plugin.show_dialog()
        dialog = plugin.dialog
        import coherence_based_itsa
        sample = Path(coherence_based_itsa.__file__).parent / "sample"
        for path in sorted(sample.glob("*.tif")):
            dialog.inputs.append(str(path))
        dialog.output.setText(str(root / "tmp" / "gui_outputs"))
        dialog.options.fields["block_size"].setValue(2)
        dialog.start()
        QTimer.singleShot(250, finish)
    except Exception as error:
        state_path.write_text(json.dumps(dict(status="failed", error=str(error))), encoding="utf-8")


def finish():
    plugin = plugins["coherence_based_itsa"]
    if plugin.dialog.task is not None:
        QTimer.singleShot(250, finish)
        return
    layers = QgsProject.instance().mapLayers()
    state_path.write_text(json.dumps(dict(status="passed" if len(layers) == 18 else "failed",
                                          layers=len(layers), message=plugin.dialog.status.text())),
                          encoding="utf-8")
    if plugin.results:
        plugin.results[-1].raise_()


QTimer.singleShot(1500, start)
