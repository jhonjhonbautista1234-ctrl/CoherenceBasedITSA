# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from dataclasses import asdict
import json

from qgis.core import (QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
                       QgsProcessingOutputFolder, QgsProcessingOutputMultipleLayers,
                       QgsProcessingOutputRasterLayer, QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterMultipleLayers, QgsProcessingParameterString,
                       QgsProcessingParameterVectorLayer, QgsProcessingProvider)

from .core.naming import guess_dates
from .core.options import Observation, Options

try:
    from qgis.core import Qgis
    RASTER = Qgis.ProcessingSourceType.Raster
    POLYGON = Qgis.ProcessingSourceType.VectorPolygon
except (ImportError, AttributeError):
    RASTER, POLYGON = QgsProcessing.TypeRaster, QgsProcessing.TypeVectorPolygon


class ItsaAlgorithm(QgsProcessingAlgorithm):
    def name(self):
        return "coherence_itsa"

    def displayName(self):
        return "Coherence Based ITSA"

    def group(self):
        return "Time series"

    def groupId(self):
        return "time_series"

    def createInstance(self):
        return ItsaAlgorithm()

    def shortHelpString(self):
        return (
            "Fits a segmented regression (interrupted time series) to SAR coherence "
            "rasters, per pixel and for the study area, and writes recovery maps, "
            "time-series graphs and CSV tables into a new run folder.\n\n"
            "Dates are read from the file names (two dates = an interferometric pair, "
            "timed at its midpoint). Rasters on different grids are aligned to the first "
            "PRE raster. Exact zeros are treated as no data.\n\n"
            "Observation settings is an optional JSON array, one object per raster in "
            "PRE, EVENT, POST order, with date, end_date (YYYY-MM-DD), looks and band. "
            "Analysis options is a JSON object of engine options.\n\n"
            "A positive net effect means coherence above the continued PRE trend; it is "
            "not by itself proof of physical recovery.")

    def initAlgorithm(self, configuration=None):
        groups = (("PRE", "Pre-event rasters", False),
                  ("EVENT", "Event-straddling rasters", True),
                  ("POST", "Post-event rasters", False))
        for key, label, optional in groups:
            self.addParameter(QgsProcessingParameterMultipleLayers(
                key, label, layerType=RASTER, optional=optional))
        self.addParameter(QgsProcessingParameterVectorLayer(
            "AOI", "Study area polygon", types=[POLYGON], optional=True))
        self.addParameter(QgsProcessingParameterString(
            "OBSERVATIONS", "Observation settings (JSON array)",
            defaultValue="[]", multiLine=True))
        defaults = asdict(Options([], ""))
        for name in ("observations", "output_folder", "aoi_path"):
            defaults.pop(name)
        self.addParameter(QgsProcessingParameterString(
            "OPTIONS", "Analysis options (JSON object)",
            defaultValue=json.dumps(defaults, indent=2), multiLine=True))
        self.addParameter(QgsProcessingParameterFolderDestination(
            "OUTPUT", "Output parent folder"))
        self.addOutput(QgsProcessingOutputRasterLayer("RECOVERY", "Coherence recovery map"))
        self.addOutput(QgsProcessingOutputRasterLayer("CLASSES", "Recovery classes"))
        self.addOutput(QgsProcessingOutputMultipleLayers("RASTERS", "All output rasters"))
        self.addOutput(QgsProcessingOutputFolder("RUN_FOLDER", "Run folder"))

    def processAlgorithm(self, parameters, context, feedback):
        try:
            records = []
            for key, phase in (("PRE", "pre"), ("EVENT", "event"), ("POST", "post")):
                for layer in self.parameterAsLayerList(parameters, key, context) or []:
                    path = layer.source().split("|")[0]
                    start, end = guess_dates(path)
                    records.append(Observation(path, phase, start, end_date=end))
            settings = json.loads(self.parameterAsString(
                parameters, "OBSERVATIONS", context) or "[]")
            if not isinstance(settings, list) or (settings and len(settings) != len(records)):
                raise ValueError("Observation settings must be empty "
                                 "or have one object per raster.")
            for record, values in zip(records, settings):
                if (not isinstance(values, dict)
                        or set(values) - {"date", "end_date", "looks", "band"}):
                    raise ValueError("Observation settings support date, end_date, "
                                     "looks and band only.")
                for key, value in values.items():
                    setattr(record, key, value)
            values = json.loads(self.parameterAsString(parameters, "OPTIONS", context) or "{}")
            if not isinstance(values, dict) or {"observations", "output_folder"} & set(values):
                raise ValueError("Analysis options must be an object "
                                 "without observations/output_folder.")
            aoi = self.parameterAsVectorLayer(parameters, "AOI", context)
            if aoi is not None:
                values["aoi_path"] = aoi.source().split("|")[0]
            options = Options(records, self.parameterAsString(
                parameters, "OUTPUT", context), **values)
            from .core.engine import run

            def progress(value, message):
                feedback.setProgress(value)
                feedback.setProgressText(message)

            result = run(options, progress, feedback.isCanceled)
            feedback.pushInfo("Saved run: " + result.folder)
            return {"RECOVERY": result.rasters[0], "CLASSES": result.rasters[1],
                    "RASTERS": result.rasters, "RUN_FOLDER": result.folder}
        except Exception as error:
            raise QgsProcessingException(str(error)) from error


class ItsaProvider(QgsProcessingProvider):
    def id(self):
        return "coherence_itsa"

    def name(self):
        return "Coherence Based ITSA"

    def loadAlgorithms(self):
        self.addAlgorithm(ItsaAlgorithm())
