# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

import numpy as np


def products(fit, t0, k, metric, shape):
    b = fit.beta
    net = b[2] + b[3] * (k - t0)
    values = dict(recovery=net if metric == "net_effect" else b[3], level_change=b[2],
                  slope_change=b[3], pre_trend=b[1], post_trend=b[1] + b[3],
                  r_squared=fit.r_squared, valid_count=fit.n.astype(float),
                  pre_count=fit.pre_count.astype(float), post_count=fit.post_count.astype(float),
                  residual_lag1=fit.lag1, level_se=fit.standard_errors[2],
                  slope_se=fit.standard_errors[3], level_p=fit.p_values[2],
                  slope_p=fit.p_values[3])
    return {name: a.reshape(shape) for name, a in values.items()}


def histogram_edges(minimum, maximum, bins):
    if not np.isfinite(minimum):
        return np.linspace(0, 1, bins + 1)
    if minimum == maximum:
        width = max(abs(minimum), 1.0) * np.sqrt(np.finfo(float).eps)
        minimum, maximum = minimum - width, maximum + width
    return np.linspace(minimum, maximum, bins + 1)
