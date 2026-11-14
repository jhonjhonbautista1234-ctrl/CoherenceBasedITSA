# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from pathlib import Path

from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtWidgets import QDialog, QTextBrowser, QVBoxLayout


class ResultsDialog(QDialog):
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Coherence Based ITSA results")
        self.resize(950, 700)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        folder_url = QUrl.fromLocalFile(result.folder).toString()
        browser.append(f'<p>Outputs saved to <a href="{folder_url}">run folder</a>.</p>')
        for path in result.graphs:
            url = QUrl.fromLocalFile(path).toString()
            browser.append(f'<p>{Path(path).name}</p><a href="{url}">'
                           f'<img src="{url}" width="850"></a>')
        layout.addWidget(browser)
