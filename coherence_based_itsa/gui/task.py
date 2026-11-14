# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsTask


class AnalysisTask(QgsTask):
    message = pyqtSignal(str)

    def __init__(self, options, callback):
        super().__init__("Coherence Based ITSA", QgsTask.CanCancel)
        self.options = options
        self.callback = callback
        self.result = None
        self.error = None

    def run(self):
        try:
            from ..core.engine import run
            self.result = run(self.options, self.report, self.isCanceled)
            return True
        except Exception as error:
            self.error = str(error)
            return False

    def report(self, progress, message):
        self.setProgress(progress)
        self.message.emit(message)

    def finished(self, success):
        self.callback(self.result if success else None, self.error or "Run cancelled.")
