# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from qgis.PyQt.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                                QMessageBox, QProgressBar, QPushButton, QTabWidget, QVBoxLayout)
from qgis.core import QgsApplication

from ..core.options import Options
from ..core.timing import chronology
from ..core.validation import validate_options
from .feature_selection import FeatureSelection
from .input_group import InputGroup
from .option_fields import OptionFields
from .task import AnalysisTask


class ItsaDialog(QDialog):
    def __init__(self, iface, load_result):
        super().__init__(iface.mainWindow())
        self.load_result = load_result
        self.task = None
        self.setWindowTitle("Coherence Based ITSA")
        self.resize(1000, 720)
        layout = QVBoxLayout(self)
        explanation = QLabel(
            "Add rasters in time order within each group. "
            "Magnitude inputs must be in [0,1]. "
            "In date mode, time is days from the first acquisition.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        tabs = QTabWidget()
        self.groups = {}
        for phase, label in (("pre", "Pre"), ("event", "Event-straddling"), ("post", "Post")):
            self.groups[phase] = InputGroup(phase)
            tabs.addTab(self.groups[phase], label)
        self.options = OptionFields()
        tabs.addTab(self.options, "Analysis options")
        layout.addWidget(tabs)
        self.features = FeatureSelection()
        layout.addWidget(self.features)
        note = QLabel(
            "Expectation inversion corrects the expectation, works best on "
            "spatially averaged values, and cannot remove nonstationarity bias. "
            "Newey-West lags count fitted observations.")
        note.setWordWrap(True)
        layout.addWidget(note)
        output = QHBoxLayout()
        self.output = QLineEdit()
        self.output.setAccessibleName("Output folder")
        browse = QPushButton("Output folder")
        browse.clicked.connect(self.choose_output)
        output.addWidget(self.output)
        output.addWidget(browse)
        layout.addLayout(output)
        self.progress = QProgressBar()
        self.status = QLabel("Ready")
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        controls = QHBoxLayout()
        self.run_button = QPushButton("Run")
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

    def start(self):
        try:
            observations = [o for group in self.groups.values() for o in group.observations()]
            options = Options(observations, self.output.text().strip(), **self.options.values())
            validate_options(options)
            chronology(options)
            snapshot = self.features.snapshot(options.output_folder)
            if snapshot:
                options.features_path = snapshot
            self.task = AnalysisTask(options, self.completed)
            self.task.progressChanged.connect(lambda value: self.progress.setValue(int(value)))
            self.task.message.connect(self.status.setText)
            self.run_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.progress.setValue(0)
            self.status.setText("Starting")
            QgsApplication.taskManager().addTask(self.task)
        except Exception as error:
            QMessageBox.warning(self, "Cannot run ITSA", str(error))

    def completed(self, result, error):
        self.task = None
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if result:
            try:
                self.load_result(result)
                self.status.setText("Saved: " + result.folder)
            except Exception as load_error:
                QMessageBox.warning(self, "Outputs saved", "Loading failed: " + str(load_error))
        else:
            self.status.setText(error)
            QMessageBox.warning(self, "ITSA stopped", error)

    def cancel(self):
        if self.task:
            self.task.cancel()
            self.status.setText("Cancelling after the current operation")

    def reject(self):
        if self.task:
            self.cancel()
            return
        super().reject()
