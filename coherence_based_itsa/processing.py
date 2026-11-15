# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from dataclasses import asdict
import json
from pathlib import Path

from qgis.core import (QgsProcessing, QgsProcessingAlgorithm, QgsProcessingContext,
                       QgsProcessingException, QgsProcessingLayerPostProcessorInterface,
                       QgsProcessingOutputFolder,
                       QgsProcessingOutputMultipleLayers, QgsProcessingOutputRasterLayer,
                       QgsProcessingParameterDefinition,
                       QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterMultipleLayers, QgsProcessingParameterString,
                       QgsProcessingParameterVectorLayer, QgsProcessingProvider)

from .core.naming import guess_dates
from .core.options import Observation, Options

try:
    from qgis.core import Qgis
    RASTER = Qgis.ProcessingSourceType.Raster
    POLYGON = Qgis.ProcessingSourceType.VectorPolygon
    ADVANCED = Qgis.ProcessingParameterFlag.Advanced
except (ImportError, AttributeError):
    RASTER = QgsProcessing.SourceType.TypeRaster
    POLYGON = QgsProcessing.SourceType.TypeVectorPolygon
    ADVANCED = QgsProcessingParameterDefinition.Flag.FlagAdvanced

OVERRIDE_HELP = ('Leave this as [] unless a raster needs a date, look count or band that '
                 'differs from what is read automatically. Otherwise give one object per '
                 'raster, in PRE, EVENT, POST order, for example '
                 '[{"date": "2022-07-21", "end_date": "2022-08-02", "looks": 20, "band": 1}, '
                 '{}, {}, {}] where {} keeps the automatic values of that raster.')


class SavedStyle(QgsProcessingLayerPostProcessorInterface):
    """Applies the .qml written beside an output raster when the toolbox loads it."""

    kept = []  # QGIS does not own these objects; keep them alive until they are used.

    def __init__(self, style):
        super().__init__()
        self.style = style
        del SavedStyle.kept[:-8]
        SavedStyle.kept.append(self)

    def postProcessLayer(self, layer, context, feedback):
        if Path(self.style).is_file():
            layer.loadNamedStyle(self.style)
            layer.triggerRepaint()


class ItsaAlgorithm(QgsProcessingAlgorithm):
    # Set by the plugin: called in the main thread with the finished run, to show the
    # figures and tables after a toolbox run.
    viewer = None

    def __init__(self):
        super().__init__()
        self.finished = None

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
            "Select ALL rasters of each phase: at least two PRE and two POST rasters are "
            "needed. Choose an output folder to keep the results; the default is a "
            "temporary folder. The recovery map and recovery classes are added to the "
            "project and the graphs open in a results window.\n\n"
            "Advanced parameters: 'Per-raster overrides' stays [] in normal use. "
            + OVERRIDE_HELP + " 'Analysis options' is a JSON object of engine options, "
            "for example class_tolerance.\n\n"
            "The same analysis with a simpler form is in Raster > Coherence Based ITSA.\n\n"
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
        self.addParameter(QgsProcessingParameterFolderDestination(
            "OUTPUT", "Output folder (a new run folder is created inside it)"))
        overrides = QgsProcessingParameterString(
            "OBSERVATIONS", "Per-raster overrides (optional, leave as [])",
            defaultValue="[]", multiLine=True)
        overrides.setHelp(OVERRIDE_HELP)
        defaults = asdict(Options([], ""))
        for name in ("observations", "output_folder", "aoi_path"):
            defaults.pop(name)
        settings = QgsProcessingParameterString(
            "OPTIONS", "Analysis options (JSON object)",
            defaultValue=json.dumps(defaults, indent=2), multiLine=True)
        for parameter in (overrides, settings):
            parameter.setFlags(parameter.flags() | ADVANCED)
            self.addParameter(parameter)
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
                raise ValueError(
                    "Per-raster overrides must be [] or hold one object for each of the "
                    f"{len(records)} rasters. " + OVERRIDE_HELP + " Thresholds such as "
                    "class_tolerance belong in Analysis options.")
            for record, values in zip(records, settings):
                if (not isinstance(values, dict)
                        or set(values) - {"date", "end_date", "looks", "band"}):
                    raise ValueError("Per-raster overrides support date, end_date, "
                                     "looks and band only. " + OVERRIDE_HELP)
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
            for path in result.tables + result.graphs:
                feedback.pushInfo("  " + path)
            # Added to the project by the toolbox; the .qml beside each raster styles it.
            for path, name, key in ((result.rasters[1], "recovery class", "CLASSES"),
                                    (result.rasters[0], "recovery", "RECOVERY")):
                details = QgsProcessingContext.LayerDetails(name, context.project(), key)
                details.setPostProcessor(SavedStyle(str(Path(path).with_suffix(".qml"))))
                context.addLayerToLoadOnCompletion(path, details)
            self.finished = result
            return {"RECOVERY": result.rasters[0], "CLASSES": result.rasters[1],
                    "RASTERS": result.rasters, "RUN_FOLDER": result.folder}
        except Exception as error:
            raise QgsProcessingException(str(error)) from error

    def postProcessAlgorithm(self, context, feedback):
        if self.finished is not None and ItsaAlgorithm.viewer is not None:
            ItsaAlgorithm.viewer(self.finished)
        return {}


class ItsaProvider(QgsProcessingProvider):
    def id(self):
        return "coherence_itsa"

    def name(self):
        return "Coherence Based ITSA"

    def loadAlgorithms(self):
        self.addAlgorithm(ItsaAlgorithm())
