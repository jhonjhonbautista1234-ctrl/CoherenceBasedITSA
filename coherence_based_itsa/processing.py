# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from dataclasses import asdict
import json

from qgis.core import (QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
                       QgsProcessingOutputFolder, QgsProcessingOutputMultipleLayers,
                       QgsProcessingOutputRasterLayer, QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterMultipleLayers, QgsProcessingParameterString,
                       QgsProcessingProvider)

from .core.options import Observation, Options


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
            "Fit segmented OLS to coherence rasters. Input order: Pre, Event, Post. "
            "Observation settings is a JSON array, one object per raster, with "
            "optional date (YYYY-MM-DD), looks (>1), and band (1-based). "
            "An empty array uses defaults. Analysis options is a JSON object "
            "using the shared engine option names. Dates require time_mode=dates. "
            "T0 and k are days from the first acquisition in date mode, or "
            "zero-based indices in index mode. Four fitted observations permit "
            "coefficients but not standard errors or p-values. Positive net "
            "effects indicate coherence above the pre counterfactual, not "
            "proof of physical recovery. Each run creates a new subfolder. "
            "Failed or cancelled partial runs are marked in JSON.")

    def initAlgorithm(self, configuration=None):
        groups = (("PRE", "Pre rasters (time order)", False),
                  ("EVENT", "Event-straddling rasters (time order)", True),
                  ("POST", "Post rasters (time order)", False))
        for key, label, optional in groups:
            self.addParameter(QgsProcessingParameterMultipleLayers(
                key, label, layerType=QgsProcessing.TypeRaster, optional=optional))
        self.addParameter(QgsProcessingParameterString(
            "OBSERVATIONS", "Observation settings (JSON array)",
            defaultValue="[]", multiLine=True))
        defaults = asdict(Options([], ""))
        defaults.pop("observations")
        defaults.pop("output_folder")
        self.addParameter(QgsProcessingParameterString(
            "OPTIONS", "Analysis options (JSON object)",
            defaultValue=json.dumps(defaults, indent=2),
            multiLine=True))
        self.addParameter(QgsProcessingParameterFolderDestination(
            "OUTPUT", "Output parent folder"))
        self.addOutput(QgsProcessingOutputRasterLayer("RECOVERY", "Coherence recovery map"))
        self.addOutput(QgsProcessingOutputMultipleLayers("RASTERS", "All output rasters"))
        self.addOutput(QgsProcessingOutputFolder("RUN_FOLDER", "Run folder"))

    def processAlgorithm(self, parameters, context, feedback):
        try:
            records = []
            for key, phase in (("PRE", "pre"), ("EVENT", "event"), ("POST", "post")):
                for layer in self.parameterAsLayerList(parameters, key, context):
                    records.append(Observation(
                        layer.source().split("|")[0], phase))
            settings = json.loads(self.parameterAsString(
                parameters, "OBSERVATIONS", context))
            if not isinstance(settings, list) or (settings and len(settings) != len(records)):
                raise ValueError("Observation settings must be empty "
                                 "or have one object per raster.")
            for record, values in zip(records, settings):
                if (not isinstance(values, dict)
                        or set(values) - {"date", "looks", "band"}):
                    raise ValueError("Observation settings support date, looks, band only.")
                for key, value in values.items():
                    setattr(record, key, value)
            values = json.loads(self.parameterAsString(parameters, "OPTIONS", context))
            if not isinstance(values, dict) or {"observations", "output_folder"} & set(values):
                raise ValueError("Analysis options must be an object "
                                 "without observations/output_folder.")
            options = Options(records, self.parameterAsString(
                parameters, "OUTPUT", context), **values)
            from .core.engine import run

            def progress(value, message):
                feedback.setProgress(value)
                feedback.setProgressText(message)

            result = run(options, progress, feedback.isCanceled)
            feedback.pushInfo("Saved run: " + result.folder)
            return {"RECOVERY": result.rasters[0], "RASTERS": result.rasters,
                    "RUN_FOLDER": result.folder}
        except Exception as error:
            raise QgsProcessingException(str(error)) from error


class ItsaProvider(QgsProcessingProvider):
    def id(self):
        return "coherence_itsa"

    def name(self):
        return "Coherence Based ITSA"

    def loadAlgorithms(self):
        self.addAlgorithm(ItsaAlgorithm())
