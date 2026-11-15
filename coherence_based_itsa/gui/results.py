# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from pathlib import Path

from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QDialog, QHBoxLayout, QPushButton, QTextBrowser, QVBoxLayout


class ResultsDialog(QDialog):
    """Shows the figures of a finished run with links to every output file."""

    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Coherence Based ITSA results")
        self.resize(1000, 760)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        parts = [f"<h3>Run saved to {result.folder}</h3>"]
        tables = " &nbsp;|&nbsp; ".join(
            f'<a href="{QUrl.fromLocalFile(path).toString()}">{Path(path).name}</a>'
            for path in result.tables)
        parts.append(f"<p>Tables: {tables}</p>")
        for path in result.graphs:
            url = QUrl.fromLocalFile(path).toString()
            parts.append(f'<p><a href="{url}"><img src="{url}" width="920"></a></p>')
        browser.setHtml("".join(parts))
        layout.addWidget(browser)
        controls = QHBoxLayout()
        controls.addStretch(1)
        folder = QPushButton("Open output folder")
        folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(result.folder)))
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        controls.addWidget(folder)
        controls.addWidget(close)
        layout.addLayout(controls)
