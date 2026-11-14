# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm, t as student_t


@dataclass
class FitResult:
    beta: np.ndarray
    standard_errors: np.ndarray
    p_values: np.ndarray
    n: np.ndarray
    pre_count: np.ndarray
    post_count: np.ndarray
    r_squared: np.ndarray
    lag1: np.ndarray
    fitted: np.ndarray


def design_matrix(times, post, t0):
    return np.column_stack((np.ones(len(times)), times, post,
                            (times - t0) * post)).astype(float)


def probabilities(estimates, errors, degrees, covariance):
    ratio = np.divide(np.abs(estimates), errors,
                      out=np.full_like(estimates, np.nan), where=errors > 0)
    ratio[(errors == 0) & (estimates != 0)] = np.inf
    if covariance == "newey_west":
        return 2 * norm.sf(ratio)
    return 2 * student_t.sf(ratio, degrees)


def covariance_matrices(x, residual, mode, lags):
    bread = np.linalg.inv(x.T @ x)
    degrees = len(x) - 4
    if mode == "ols":
        variance = np.sum(residual ** 2, axis=0) / degrees
        return bread[:, :, None] * variance
    scores = x[:, :, None] * residual[:, None, :]
    meat = np.einsum("tip,tjp->ijp", scores, scores)
    for lag in range(1, min(lags, len(x) - 1) + 1):
        cross = np.einsum("tip,tjp->ijp", scores[lag:], scores[:-lag])
        meat += (1 - lag / (lags + 1)) * (cross + cross.transpose(1, 0, 2))
    return np.einsum("ij,jkp,kl->ilp", bread, meat, bread)


def fit_series(values, times, phases, fitted_post, t0, options):
    y = np.asarray(values, dtype=float).reshape(len(times), -1)
    pre = phases == "pre"
    use = pre | fitted_post
    n_pixels = y.shape[1]
    beta = np.full((4, n_pixels), np.nan)
    se, p_values = beta.copy(), beta.copy()
    r2, lag1 = np.full(n_pixels, np.nan), np.full(n_pixels, np.nan)
    predictions = np.full_like(y, np.nan)
    valid = np.isfinite(y) & use[:, None]
    pre_count = (valid & pre[:, None]).sum(0)
    post_count = (valid & fitted_post[:, None]).sum(0)
    counts = valid.sum(0)
    x = design_matrix(times, fitted_post, t0)
    patterns, memberships = np.unique(valid.T, axis=0, return_inverse=True)
    for group, pattern in enumerate(patterns):
        indices = np.flatnonzero(memberships == group)
        if ((pattern & pre).sum() < options.min_pre
                or (pattern & fitted_post).sum() < options.min_post):
            continue
        a = x[pattern]
        # Centering preserves coefficients while avoiding large calendar offsets.
        centered = np.column_stack((a[:, 0], a[:, 1] - t0, a[:, 2], a[:, 3]))
        scale = max(float(np.max(np.abs(centered[:, 1]))), 1.0)
        centered[:, (1, 3)] /= scale
        if np.linalg.matrix_rank(centered) < 4:
            continue
        transform = np.array([[1, -t0 / scale, 0, 0], [0, 1 / scale, 0, 0],
                              [0, 0, 1, 0], [0, 0, 0, 1 / scale]])
        b = np.linalg.lstsq(centered, y[pattern][:, indices], rcond=None)[0]
        result = transform @ b
        beta[:, indices] = result
        predictions[:, indices] = x @ result
        residual = y[pattern][:, indices] - centered @ b
        sse = np.sum(residual ** 2, axis=0)
        total = np.sum((y[pattern][:, indices]
                        - y[pattern][:, indices].mean(0)) ** 2, axis=0)
        r2[indices] = np.divide(total - sse, total,
                                out=np.full_like(sse, np.nan), where=total > 0)
        if len(a) > 2:
            left, right = residual[:-1], residual[1:]
            left = left - left.mean(0)
            right = right - right.mean(0)
            denominator = np.sqrt(np.sum(left ** 2, 0) * np.sum(right ** 2, 0))
            lag1[indices] = np.divide(np.sum(left * right, 0), denominator,
                                      out=np.full_like(sse, np.nan), where=denominator > 0)
        if len(a) > 4:
            cov = covariance_matrices(centered, residual, options.covariance, options.nw_lags)
            cov = np.einsum("ij,jkp,lk->ilp", transform, cov, transform)
            errors = np.sqrt(np.maximum(0, np.einsum("iip->ip", cov)))
            se[:, indices] = errors
            p_values[:, indices] = probabilities(result, errors, len(a) - 4, options.covariance)
    return FitResult(beta, se, p_values, counts, pre_count, post_count, r2, lag1, predictions)
