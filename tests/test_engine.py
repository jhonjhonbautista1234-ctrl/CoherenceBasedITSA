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
from coherence_based_itsa.core.naming import describe
from coherence_based_itsa.core.timing import chronology
from tests.fixtures import make_polygon, make_stack


def read(folder, name):
    dataset = gdal.Open(str(Path(folder) / (name + ".tif")))
    return dataset.ReadAsArray(), dataset.GetGeoTransform(), dataset.GetProjection()


def rows(path):
    with Path(path).open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


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
            values, transform, projection = read(folder, name)
            self.assertEqual(transform, source.GetGeoTransform())
            self.assertEqual(projection, source.GetProjection())
            self.assertEqual(values[0, 0], 0 if name == "valid_count" else self.options.nodata)
            np.testing.assert_allclose(values[1:], expected, atol=1e-6)
        # b2 = -0.2 and net effect -0.025: dropped, and back within the 0.05 tolerance.
        classes = read(folder, "recovery_class")[0]
        self.assertEqual(classes[0, 0], 0)
        self.assertTrue((classes[1:] == 2).all())
        parameters = json.loads((folder / "run_parameters.json").read_text())
        self.assertEqual(parameters["status"], "complete")
        self.assertEqual(parameters["interruption"], 5)
        self.assertEqual(parameters["time_mode"], "index")
        for path in result.graphs + result.tables + result.rasters:
            self.assertGreater(Path(path).stat().st_size, 0, path)
        self.assertEqual(Path(result.rasters[0]).name, "recovery.tif")
        for name in ("recovery", "recovery_class"):
            self.assertIn("rasterrenderer", (folder / (name + ".qml")).read_text())
        row = rows(folder / "coefficients.csv")[0]
        self.assertAlmostEqual(float(row["b2"]), -0.2, places=6)
        self.assertAlmostEqual(float(row["net_effect_at_k"]), -0.025, places=6)
        series = rows(folder / "series.csv")
        self.assertEqual(len(series), 11)
        self.assertEqual(series[5]["used_in_fit"], "False")
        self.assertAlmostEqual(float(series[0]["mean"]), 0.65, places=6)
        classes = {r["label"]: int(r["pixels"]) for r in rows(folder / "recovery_classes.csv")}
        self.assertEqual(classes["Coherence recovered"], 19)

    def test_grid_mismatch_aligned_by_default_and_rejected_on_request(self):
        dataset = gdal.Open(self.options.observations[-1].path, gdal.GA_Update)
        dataset.SetGeoTransform((500010, 10, 0, 1600000, 0, -10))
        dataset = None
        result = run(self.options)
        values = read(result.folder, "recovery")[0]
        np.testing.assert_allclose(values[1:, 1:], -0.025, atol=1e-6)
        self.options.resample = False
        with self.assertRaisesRegex(ValueError, "grids or CRS differ"):
            run(self.options)

    def test_zero_fill_dates_from_names_and_time_sorting(self):
        # Rename the rasters the way SNAP exports are named, give them a zero-filled
        # column and hand them over in the wrong order.
        observations = []
        for index, observation in enumerate(self.options.observations):
            dataset = gdal.Open(observation.path, gdal.GA_Update)
            band = dataset.GetRasterBand(1)
            band.DeleteNoDataValue()
            values = band.ReadAsArray()
            values[values < 0] = 0
            values[:, 4] = 0
            band.WriteArray(values)
            dataset = None
            label = {"pre": "Pre-Event", "event": "Event_Straddling",
                     "post": "Post-Event"}[observation.phase]
            day = 1 + 2 * index
            renamed = Path(observation.path).with_name(
                f"Coherence_{label}-{index:02d}_202201{day:02d}_202201{day + 2:02d}_coh.tif")
            Path(observation.path).rename(renamed)
            phase, start, end = describe(renamed)
            self.assertEqual(phase, observation.phase)
            observation.path, observation.date, observation.end_date = str(renamed), start, end
            observations.append(observation)
        self.options.observations = observations[::-1]
        result = run(self.options)
        parameters = json.loads(Path(result.folder, "run_parameters.json").read_text())
        self.assertEqual(parameters["time_mode"], "dates")
        self.assertEqual(parameters["interruption_label"], "12 Jan 2022")
        values = read(result.folder, "level_change")[0]
        np.testing.assert_allclose(values[1:, :4], -0.2, atol=1e-6)
        self.assertTrue((values[:, 4] == self.options.nodata).all())
        # Two days per step, so the slope change is half the per-index value.
        np.testing.assert_allclose(read(result.folder, "slope_change")[0][1:, :4], 0.0175,
                                   atol=1e-6)

    def test_aoi_crops_grid_feature_series_pixel_cap_and_determinism(self):
        path = Path(self.temp.name) / "aoi.geojson"
        make_polygon(path)
        self.options.aoi_path = str(path)
        self.options.features_path = str(path)
        self.options.pixel_csv = True
        self.options.pixel_cap = 3
        result = run(self.options)
        self.assertEqual(len(rows(Path(result.folder, "pixels.csv"))), 3)
        first, transform, _ = read(result.folder, "recovery")
        self.assertEqual(first.shape, (3, 3))
        self.assertEqual(transform[0], 500000)
        self.assertEqual(first[0, 0], self.options.nodata)
        scopes = {r["scope"] for r in rows(Path(result.folder, "coefficients.csv"))}
        self.assertEqual(scopes, {"AOI", "test (aoi:0)"})
        self.assertEqual(len([g for g in result.graphs if "timeseries" in g]), 2)
        second = run(self.options)
        np.testing.assert_array_equal(first, read(second.folder, "recovery")[0])
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
        dataset = gdal.Open(self.options.observations[0].path, gdal.GA_Update)
        dataset.GetRasterBand(1).WriteArray(np.full((4, 5), 1.1, dtype="float32"))
        dataset = None
        with self.assertRaisesRegex(ValueError, "magnitudes must lie"):
            run(self.options)


class NamingAndTimingTests(unittest.TestCase):
    def test_phase_and_dates_from_file_names(self):
        cases = {
            "Coherence_Pre-Event-04_20220721_20220802_split_Orb_Stack_esd_coh_deb_TC.tif":
                ("pre", "2022-07-21", "2022-08-02"),
            "Coherence_Event_Straddling_20220919_20221001_split.tif":
                ("event", "2022-09-19", "2022-10-01"),
            "Coherence_Post-Event-01_20221001_20221013_split.tif":
                ("post", "2022-10-01", "2022-10-13"),
            "post_2022-10-13.tif": ("post", "2022-10-13", ""),
            "scene_17.tif": ("", "", ""),
        }
        for name, expected in cases.items():
            self.assertEqual(describe(name), expected, name)

    def test_pairs_are_timed_at_their_midpoint(self):
        from coherence_based_itsa.core.options import Observation, Options
        names = ["Pre_20220721_20220802", "Pre_20220802_20220814", "Pre_20220907_20220919",
                 "Event_Straddling_20220919_20221001", "Post_20221001_20221013",
                 "Post_20221013_20221025"]
        observations = []
        for name in names:
            phase, start, end = describe(name)
            observations.append(Observation(name, phase, start, end_date=end))
        timeline = chronology(Options(observations, "."))
        self.assertEqual(timeline.mode, "dates")
        np.testing.assert_allclose(timeline.times, [6, 18, 54, 66, 78, 90])
        self.assertEqual(timeline.t0, 66)
        self.assertEqual(timeline.label(timeline.t0), "25 Sep 2022")


if __name__ == "__main__":
    unittest.main()
