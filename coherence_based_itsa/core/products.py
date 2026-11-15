# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

import numpy as np

# code, key, label, colour (colour-blind-safe, shared by the QGIS style and the figures)
CLASSES = (
    (1, "no_loss", "No detectable coherence loss", "#2a78d6"),
    (2, "recovered", "Coherence recovered", "#1baf7a"),
    (3, "partial", "Partially recovered", "#eda100"),
    (4, "not_recovered", "Not recovered / further loss", "#d03b3b"),
)
# Diverging ramp for the continuous recovery map: loss (red) - neutral - gain (blue).
DIVERGING = ("#a52828", "#d9624f", "#efb3a4", "#f0efec", "#a9c9ee", "#4f8fdc", "#1c5cab")

DESCRIPTIONS = {
    "recovery": "Recovery metric (see run_parameters.json)",
    "recovery_class": "Recovery class 1-4",
    "level_change": "Immediate level change at the interruption (b2)",
    "slope_change": "Change in trend after the interruption (b3)",
    "pre_trend": "Pre-event trend (b1)",
    "post_trend": "Post-event trend (b1+b3)",
    "r_squared": "Model R squared",
    "valid_count": "Observations used in the fit",
    "pre_count": "PRE observations used",
    "post_count": "POST observations used",
    "residual_lag1": "Lag-1 residual autocorrelation",
    "level_se": "Standard error of b2",
    "slope_se": "Standard error of b3",
    "level_p": "p-value of b2",
    "slope_p": "p-value of b3",
}


def classify(level, net, tolerance):
    """Descriptive recovery classes from the level change and the net effect at k.

    1 no loss: the level did not drop by more than the tolerance at the interruption.
    2 recovered: it dropped, but by k coherence is back within tolerance of the
      pre-event counterfactual.
    3 partial: still below the counterfactual at k, but the gap has narrowed.
    4 not recovered: the gap at k is as large as, or larger than, the initial drop.
    """
    result = np.full(level.shape, np.nan)
    fitted = np.isfinite(level) & np.isfinite(net)
    dropped = fitted & (level < -tolerance)
    result[fitted & ~dropped] = 1
    result[dropped & (net >= -tolerance)] = 2
    result[dropped & (net < -tolerance) & (net > level)] = 3
    result[dropped & (net < -tolerance) & (net <= level)] = 4
    return result


def products(fit, t0, k, metric, shape, tolerance=0.05):
    b = fit.beta
    net = b[2] + b[3] * (k - t0)
    values = dict(recovery=net if metric == "net_effect" else b[3],
                  recovery_class=classify(b[2], net, tolerance),
                  level_change=b[2], slope_change=b[3], pre_trend=b[1],
                  post_trend=b[1] + b[3], r_squared=fit.r_squared,
                  valid_count=fit.n.astype(float),
                  pre_count=fit.pre_count.astype(float), post_count=fit.post_count.astype(float),
                  residual_lag1=fit.lag1, level_se=fit.standard_errors[2],
                  slope_se=fit.standard_errors[3], level_p=fit.p_values[2],
                  slope_p=fit.p_values[3])
    return {name: a.reshape(shape) for name, a in values.items()}


def robust_edges(sample, bins):
    """Histogram edges covering the central 99% of the sampled values."""
    if not len(sample):
        return np.linspace(0, 1, bins + 1)
    low, high = np.percentile(sample, [0.5, 99.5])
    if low == high:
        width = max(abs(low), 1.0) * 1e-6
        low, high = low - width, high + width
    return np.linspace(low, high, bins + 1)


def symmetric_limit(sample):
    """Colour-scale half-range for a diverging map: the 98th percentile of |value|."""
    if not len(sample):
        return 1.0
    limit = float(np.percentile(np.abs(sample), 98))
    return limit if limit > 0 else 1.0
