# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from functools import lru_cache
import math

import numpy as np
from scipy.special import gammaln, logsumexp


def expectation(true_coherence, looks):
    """Expected sample coherence magnitude, Touzi et al. (1999), Eq. 6."""
    if not np.isfinite(looks) or looks <= 1:
        raise ValueError("Expectation inversion requires independent looks L > 1.")
    truth = np.asarray(true_coherence, dtype=float)
    squared = np.atleast_1d(truth).ravel() ** 2
    result = np.ones(squared.shape)
    inside = squared < 1
    if not inside.any():
        return result.reshape(truth.shape)
    log_coefficient = gammaln(looks) + gammaln(1.5) - gammaln(looks + 0.5)
    spread = looks + 50 + 10 * math.sqrt(looks)
    largest = squared[inside].max()
    limit = 1 if largest <= 0 else int(math.ceil(spread / -math.log(largest))) + 20
    n = np.arange(limit, dtype=float)
    # Logarithms of the 3F2 series terms, without the power of D squared.
    base = (gammaln(1.5 + n) - gammaln(1.5) + 2 * (gammaln(looks + n) - gammaln(looks))
            - gammaln(looks + 0.5 + n) + gammaln(looks + 0.5) - 2 * gammaln(n + 1))
    for index in np.flatnonzero(inside):
        z = squared[index]
        if z <= 0:
            series = 0.0
        else:
            log_z = math.log(z)
            count = min(limit, int(math.ceil(spread / -log_z)) + 20)
            series = logsumexp(base[:count] + n[:count] * log_z)
        result[index] = math.exp(log_coefficient + looks * math.log1p(-z) + series)
    return result.reshape(truth.shape)


@lru_cache(maxsize=32)
def lookup_table(looks, points):
    truth = np.linspace(0, 1, points)
    expected = expectation(truth, looks)
    expected[-1] = 1.0
    if not np.isfinite(expected).all() or np.any(np.diff(expected) <= 0):
        raise ValueError("Could not construct a finite monotonic coherence lookup table.")
    return expected, truth


def prepare_values(values, options, table=None):
    a = np.asarray(values, dtype=float)
    finite = np.isfinite(a)
    a[~finite] = np.nan
    if np.any((a[finite] < 0) | (a[finite] > 1)):
        raise ValueError("Coherence magnitudes must lie in [0,1]; check band, scaling and nodata.")
    if table is not None:
        a[finite] = np.interp(a[finite], table[0], table[1], left=0, right=1)
    a[finite] = np.clip(a[finite], 0, 1)
    if options.low_threshold is not None:
        a[a < options.low_threshold] = np.nan
    return a
