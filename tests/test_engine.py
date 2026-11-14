# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

import csv
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from osgeo import gdal

from coherence_based_itsa.core.engine import CancelledError, run
from tests.fixtures import make_polygon, make_stack


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.options = make_stack(self.temp.name)

    def test_complete_run_grid_values_masks_and_tables(self):
        result = run(self.options)
        folder = Path(result.folder)
        source = gdal.Open(self.options.observations[0].path)
        for name, expected in (("level_change", -0.2), ("slope_change", 0.035),
                                ("recovery", -0.025), ("pre_trend", -0.01),
                                ("post_trend", 0.025), ("valid_count", 10)):
            ds = gdal.Open(str(folder / (name + ".tif")))
            self.assertEqual(ds.GetGeoTransform(), source.GetGeoTransform())
            self.assertEqual(ds.GetProjection(), source.GetProjection())
            self.assertEqual(ds.GetRasterBand(1).DataType, gdal.GDT_Float32)
            values = ds.ReadAsArray()
            if name == "valid_count":
                self.assertEqual(values[0, 0], 0)
            else:
                self.assertEqual(values[0, 0], self.options.nodata)
            np.testing.assert_allclose(values[1:], expected, atol=1e-6)
            ds = None
        parameters = json.loads((folder / "run_parameters.json").read_text())
        self.assertEqual(parameters["status"], "complete")
        self.assertEqual(parameters["interruption"], 5)
        self.assertTrue(all(Path(path).stat().st_size > 0 for path in result.graphs))
        with (folder / "coefficients.csv").open() as stream:
            self.assertIn("bias_correction=none", next(stream))
            row = next(csv.DictReader(stream))
            self.assertAlmostEqual(float(row["b2"]), -0.2, places=6)

    def test_grid_mismatch_rejected_and_explicit_resampling(self):
        path = self.options.observations[-1].path
        ds = gdal.Open(path, gdal.GA_Update)
        ds.SetGeoTransform((500010, 10, 0, 1600000, 0, -10))
        ds = None
        with self.assertRaisesRegex(ValueError, "grids or CRS differ"):
            run(self.options)
        self.options.resample = True
        result = run(self.options)
        self.assertTrue(Path(result.folder, "recovery.tif").exists())

    def test_aoi_feature_series_pixel_cap_and_determinism(self):
        path = Path(self.temp.name) / "aoi.geojson"
        make_polygon(path)
        self.options.aoi_path = str(path)
        self.options.features_path = str(path)
        self.options.pixel_csv = True
        self.options.pixel_cap = 3
        result = run(self.options)
        with Path(result.folder, "pixels.csv").open() as stream:
            next(stream)
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 3)
        ds = gdal.Open(str(Path(result.folder, "recovery.tif")))
        first = ds.ReadAsArray()
        self.assertEqual(first[3, 4], self.options.nodata)
        ds = None
        second = run(self.options)
        ds = gdal.Open(str(Path(second.folder, "recovery.tif")))
        np.testing.assert_array_equal(first, ds.ReadAsArray())
        self.assertEqual(Path(result.folder, "pixels.csv").read_bytes(),
                         Path(second.folder, "pixels.csv").read_bytes())

    def test_cancellation_status(self):
        state = {"cancel": False}

        def progress(value, message):
            if value > 5:
                state["cancel"] = True

        with self.assertRaises(CancelledError):
            run(self.options, progress, lambda: state["cancel"])
        manifest = next(Path(self.options.output_folder).glob("*/run_parameters.json"))
        self.assertEqual(json.loads(manifest.read_text())["status"], "cancelled")

    def test_source_range_validation(self):
        ds = gdal.Open(self.options.observations[0].path, gdal.GA_Update)
        ds.GetRasterBand(1).WriteArray(np.full((4, 5), 1.1, dtype="float32"))
        ds = None
        with self.assertRaisesRegex(ValueError, "magnitudes must lie"):
            run(self.options)


if __name__ == "__main__":
    unittest.main()
