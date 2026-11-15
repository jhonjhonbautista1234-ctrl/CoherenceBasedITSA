# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

import unittest

import numpy as np

from coherence_based_itsa.core.coherence import expectation, lookup_table, prepare_values
from coherence_based_itsa.core.model import design_matrix, fit_series
from coherence_based_itsa.core.options import Observation, Options
from coherence_based_itsa.core.timing import chronology


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.times = np.arange(11, dtype=float)
        self.phases = np.array(["pre"] * 5 + ["event"] + ["post"] * 5)
        self.post = self.phases == "post"
        self.t0 = 5.0
        self.options = Options([], ".")
        self.x = design_matrix(self.times, self.post, self.t0)
        self.beta = np.array([0.65, -0.01, -0.2, 0.035])
        self.y = (self.x @ self.beta)[:, None]

    def fit(self, y=None):
        return fit_series(self.y if y is None else y, self.times, self.phases,
                          self.post, self.t0, self.options)

    def test_known_level_and_slope_changes(self):
        fit = self.fit()
        np.testing.assert_allclose(fit.beta[:, 0], self.beta, atol=1e-12)
        self.assertAlmostEqual(fit.beta[2, 0], -0.2)
        self.assertAlmostEqual(fit.beta[3, 0], 0.035)
        self.assertAlmostEqual(fit.r_squared[0], 1.0)
        self.assertEqual(fit.n[0], 10)

    def test_event_excluded_and_missing_patterns(self):
        values = np.repeat(self.y, 3, axis=1)
        values[5] = 0.0
        values[0, 1] = np.nan
        values[8, 2] = np.nan
        fit = self.fit(values)
        np.testing.assert_allclose(fit.beta, np.repeat(self.beta[:, None], 3, 1), atol=1e-12)
        np.testing.assert_array_equal(fit.n, [10, 9, 9])

    def test_insufficient_segment_masked(self):
        y = self.y.copy()
        y[:4] = np.nan
        self.assertTrue(np.isnan(self.fit(y).beta).all())

    def test_four_observations_fit_without_inference(self):
        y = self.y.copy()
        y[[0, 1, 2, 8, 9, 10]] = np.nan
        fit = self.fit(y)
        np.testing.assert_allclose(fit.beta[:, 0], self.beta, atol=1e-12)
        self.assertTrue(np.isnan(fit.standard_errors).all())
        self.assertTrue(np.isnan(fit.p_values).all())

    def test_ols_covariance_independent_reference(self):
        y = self.y + np.array([0.01, -0.02, 0.01, 0, 0.02, 0, -0.01, 0.02, -0.01, 0, 0.01])[:, None]
        fit = self.fit(y)
        use = self.phases != "event"
        x = self.x[use]
        b = np.linalg.lstsq(x, y[use], rcond=None)[0]
        variance = np.sum((y[use] - x @ b) ** 2) / (use.sum() - 4)
        expected = np.sqrt(np.diag(np.linalg.inv(x.T @ x)) * variance)
        np.testing.assert_allclose(fit.standard_errors[:, 0], expected, rtol=1e-10)
        self.assertTrue(((fit.p_values >= 0) & (fit.p_values <= 1)).all())

    def test_newey_west_independent_reference(self):
        self.options.covariance = "newey_west"
        self.options.nw_lags = 2
        y = self.y + np.sin(self.times)[:, None] * 0.01
        fit = self.fit(y)
        x, values = self.x[self.phases != "event"], y[self.phases != "event", 0]
        b = np.linalg.lstsq(x, values, rcond=None)[0]
        scores = x * (values - x @ b)[:, None]
        meat = scores.T @ scores
        for lag in (1, 2):
            cross = scores[lag:].T @ scores[:-lag]
            meat += (1 - lag / 3) * (cross + cross.T)
        bread = np.linalg.inv(x.T @ x)
        np.testing.assert_allclose(fit.standard_errors[:, 0],
                                   np.sqrt(np.diag(bread @ meat @ bread)), rtol=1e-9)

    def test_irregular_dates_and_event_inclusion(self):
        times = np.array([0, 2, 4, 9, 12, 15, 19, 24, 30, 37, 45], float)
        post = self.post | (self.phases == "event")
        y = (design_matrix(times, post, 15) @ self.beta)[:, None]
        fit = fit_series(y, times, self.phases, post, 15, self.options)
        np.testing.assert_allclose(fit.beta[:, 0], self.beta, atol=1e-12)
        self.assertEqual(fit.n[0], 11)


class CoherenceTests(unittest.TestCase):
    def test_zero_coherence_expectation_and_inverse(self):
        self.assertAlmostEqual(float(expectation(np.array(0.0), 2)), 2 / 3)
        table = lookup_table(4, 4097)
        true = np.array([0.1, 0.3, 0.7, 0.95])
        values = prepare_values(expectation(true, 4), Options([], "."), table)
        np.testing.assert_allclose(values, true, atol=1e-6)

    def test_expectation_matches_simulated_sample_coherence(self):
        rng = np.random.default_rng(7)
        for looks, true in ((2, 0.5), (4, 0.2), (4, 0.8), (9, 0.5), (20, 0.95)):
            shape = (200000, looks)
            first = (rng.standard_normal(shape) + 1j * rng.standard_normal(shape)) / np.sqrt(2)
            noise = (rng.standard_normal(shape) + 1j * rng.standard_normal(shape)) / np.sqrt(2)
            second = true * first + np.sqrt(1 - true ** 2) * noise
            sample = np.abs((first * second.conj()).sum(1)) / np.sqrt(
                (np.abs(first) ** 2).sum(1) * (np.abs(second) ** 2).sum(1))
            self.assertAlmostEqual(float(expectation(np.array(true), looks)),
                                   sample.mean(), delta=0.002)

    def test_expectation_series_reference_and_limits(self):
        # Direct summation of the Eq. 6 series at moderate coherence.
        for looks, true, expected in ((2, 0.5, 0.735939), (4, 0.5, 0.604538),
                                      (9, 0.8, 0.805511), (20, 0.2, 0.267551)):
            self.assertAlmostEqual(float(expectation(np.array(true), looks)), expected, places=6)
        curve = expectation(np.linspace(0, 1, 513), 4)
        self.assertEqual(curve[-1], 1.0)
        self.assertTrue(np.all(np.diff(curve) > 0))
        self.assertTrue(np.all(curve[:-1] > np.linspace(0, 1, 513)[:-1]))
        self.assertAlmostEqual(float(expectation(np.array(0.9999), 4)), 1.0, places=3)

    def test_zero_valid_range_and_threshold(self):
        options = Options([], ".")
        self.assertEqual(prepare_values(np.array([0.0]), options)[0], 0)
        with self.assertRaises(ValueError):
            prepare_values(np.array([1.01]), options)
        options.low_threshold = 0.1
        self.assertTrue(np.isnan(prepare_values(np.array([0.0]), options)[0]))

    def test_no_looks_inversion_at_one_look(self):
        with self.assertRaises(ValueError):
            lookup_table(1, 4097)

    def test_nonfinite_observations_are_missing(self):
        values = prepare_values(np.array([np.inf, -np.inf, np.nan, 0.5]), Options([], "."))
        self.assertTrue(np.isnan(values[:3]).all())
        self.assertEqual(values[3], 0.5)


class TimingTests(unittest.TestCase):
    def test_default_interruption_and_invalid_stack(self):
        observations = [Observation(str(i), p) for i, p in enumerate(
            ["pre", "pre", "event", "post", "post"])]
        options = Options(observations, ".")
        self.assertEqual(chronology(options).t0, 2)
        options.observations = observations[:3]
        with self.assertRaises(ValueError):
            chronology(options)


if __name__ == "__main__":
    unittest.main()
