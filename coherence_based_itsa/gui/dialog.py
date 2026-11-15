# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from pathlib import Path

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import (QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                                QLineEdit, QMessageBox, QProgressBar, QPushButton, QTabWidget,
                                QVBoxLayout, QWidget)
from qgis.core import QgsApplication

from ..core.options import Options
from ..core.timing import chronology, sort_observations
from ..core.validation import validate_options
from .feature_selection import VectorInput
from .input_table import InputTable
from .option_fields import OptionFields
from .task import AnalysisTask

SETTING = "coherence_based_itsa/output_folder"


class ItsaDialog(QDialog):
    def __init__(self, iface, load_result):
        super().__init__(iface.mainWindow())
        self.load_result = load_result
        self.task = None
        self.setWindowTitle("Coherence Based ITSA")
        self.resize(980, 680)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        inputs = QWidget()
        page = QVBoxLayout(inputs)
        explanation = QLabel(
            "Add the coherence rasters (magnitude, 0 to 1). The phase and the dates are read "
            "from the file names, for example Coherence_Pre-Event-04_20220721_20220802.tif; "
            "correct them in the table if needed. Rasters on different grids are aligned "
            "automatically.")
        explanation.setWordWrap(True)
        page.addWidget(explanation)
        self.inputs = InputTable()
        page.addWidget(self.inputs)
        form = QFormLayout()
        self.aoi = VectorInput()
        self.features = VectorInput(points=True)
        self.output = QLineEdit(QSettings().value(SETTING, "", type=str))
        self.output.setAccessibleName("Output folder")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.choose_output)
        output = QHBoxLayout()
        output.addWidget(self.output)
        output.addWidget(browse)
        form.addRow("Study area (AOI) polygon, optional", self.aoi)
        form.addRow("Extra graphs per feature, optional", self.features)
        form.addRow("Output folder", output)
        page.addLayout(form)
        tabs.addTab(inputs, "Inputs")
        self.options = OptionFields()
        tabs.addTab(self.options, "Analysis options")

        self.progress = QProgressBar()
        self.status = QLabel("Ready")
        self.status.setWordWrap(True)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        controls = QHBoxLayout()
        controls.addStretch(1)
        self.run_button = QPushButton("Run")
        self.run_button.setDefault(True)
        self.run_button.clicked.connect(self.start)
        self.cancel_button = QPushButton("Cancel run")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        for button in (self.run_button, self.cancel_button, close):
            controls.addWidget(button)
        layout.addLayout(controls)

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output.text())
        if path:
            self.output.setText(path)

    def build_options(self):
        folder = self.output.text().strip()
        if not folder:
            raise ValueError("Choose an output folder.")
        options = Options(self.inputs.observations(), folder, **self.options.values())
        validate_options(options)
        sort_observations(options)
        chronology(options)
        Path(folder).mkdir(parents=True, exist_ok=True)
        options.aoi_path = self.aoi.resolve(folder, "AOI")
        options.features_path = self.features.resolve(folder, "Features")
        return options

    def start(self):
        try:
            options = self.build_options()
        except Exception as error:
            QMessageBox.warning(self, "Cannot run ITSA", str(error))
            return
        QSettings().setValue(SETTING, options.output_folder)
        self.task = AnalysisTask(options, self.completed)
        self.task.progressChanged.connect(lambda value: self.progress.setValue(int(value)))
        self.task.message.connect(self.status.setText)
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)
        self.status.setText("Starting")
        QgsApplication.taskManager().addTask(self.task)

    def completed(self, result, error):
        self.task = None
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if result:
            self.progress.setValue(100)
            try:
                self.load_result(result)
                self.status.setText("Saved: " + result.folder)
            except Exception as load_error:
                QMessageBox.warning(self, "Outputs saved",
                                    f"Outputs are in {result.folder}, but loading them into "
                                    f"the project failed: {load_error}")
        else:
            self.status.setText(error)
            QMessageBox.warning(self, "ITSA stopped", error)

    def cancel(self):
        if self.task:
            self.task.cancel()
            self.status.setText("Cancelling after the current block")

    def reject(self):
        if self.task:
            self.cancel()
            return
        super().reject()
