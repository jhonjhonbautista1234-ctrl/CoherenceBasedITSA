# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

import csv
from pathlib import Path

import numpy as np

from .products import CLASSES

LEVELS = 500   # histogram resolution used for spatial medians and quartiles


class Summary:
    """Running spatial statistics of one region, per observation."""

    def __init__(self, name, observations):
        self.name = name
        self.sums = np.zeros(observations)
        self.counts = np.zeros(observations, dtype=np.int64)
        self.levels = np.zeros((observations, LEVELS), dtype=np.int64)

    def add(self, values):
        """values: (observations, pixels) with nan for missing."""
        finite = np.isfinite(values)
        self.sums += np.where(finite, values, 0).sum(axis=1)
        self.counts += finite.sum(axis=1)
        for index in range(values.shape[0]):
            v = values[index][finite[index]]
            if v.size:
                self.levels[index] += np.bincount(
                    np.minimum((v * LEVELS).astype(np.int64), LEVELS - 1), minlength=LEVELS)

    @property
    def mean(self):
        return np.divide(self.sums, self.counts,
                         out=np.full(len(self.sums), np.nan), where=self.counts > 0)

    def quantile(self, q):
        result = np.full(len(self.sums), np.nan)
        centres = (np.arange(LEVELS) + 0.5) / LEVELS
        for index, row in enumerate(self.levels):
            if row.sum():
                cumulative = np.cumsum(row) / row.sum()
                result[index] = centres[min(np.searchsorted(cumulative, q), LEVELS - 1)]
        return result


def open_csv(path, columns):
    stream = Path(path).open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    return stream, writer


def number(value):
    return "" if value is None or not np.isfinite(value) else float(f"{value:.8g}")


def coefficient_row(scope, fit, index=0):
    row = dict(scope=scope, n=int(fit.n[index]), pre_count=int(fit.pre_count[index]),
               post_count=int(fit.post_count[index]), r_squared=number(fit.r_squared[index]),
               residual_lag1=number(fit.lag1[index]))
    for term in range(4):
        row[f"b{term}"] = number(fit.beta[term, index])
        row[f"b{term}_se"] = number(fit.standard_errors[term, index])
        row[f"b{term}_p"] = number(fit.p_values[term, index])
    return row


def effects(fit, timeline):
    """Named effects of one fitted series."""
    b = fit.beta[:, 0]
    return dict(level_change=b[2], slope_change=b[3], pre_trend=b[1], post_trend=b[1] + b[3],
                net_effect_at_k=b[2] + b[3] * (timeline.k - timeline.t0),
                counterfactual_at_k=b[0] + b[1] * timeline.k)


def write_summaries(folder, summaries, timeline, options, fit_function):
    """Write series.csv and coefficients.csv; return paths and the fitted series."""
    times = timeline.times
    fits, rows = [], []
    stream, writer = open_csv(folder / "series.csv", [
        "scope", "observation", "file", "phase", "date_start", "date_end", "date_mid", "time",
        "used_in_fit", "mean", "median", "q25", "q75", "valid_pixels", "fitted",
        "counterfactual", "residual"])
    try:
        for summary in summaries:
            series = summary.mean
            median, q25, q75 = (summary.quantile(q) for q in (0.5, 0.25, 0.75))
            fit = fit_function(series[:, None], times, timeline.phases, timeline.fitted_post,
                               timeline.t0, options)
            fits.append((series, q25, q75, fit))
            b = fit.beta[:, 0]
            for i, observation in enumerate(options.observations):
                used = bool(timeline.phases[i] == "pre" or timeline.fitted_post[i])
                fitted = fit.fitted[i, 0] if used else np.nan
                middle = timeline.date_of(times[i])
                writer.writerow(dict(
                    scope=summary.name, observation=i + 1, file=Path(observation.path).name,
                    phase=timeline.phases[i], date_start=observation.date,
                    date_end=observation.end_date or observation.date,
                    date_mid=middle.date().isoformat() if middle else "",
                    time=number(times[i]), used_in_fit=used, mean=number(series[i]),
                    median=number(median[i]), q25=number(q25[i]), q75=number(q75[i]),
                    valid_pixels=int(summary.counts[i]), fitted=number(fitted),
                    counterfactual=number(b[0] + b[1] * times[i]),
                    residual=number(series[i] - fitted)))
            row = coefficient_row(summary.name, fit)
            row.update({name: number(value) for name, value in effects(fit, timeline).items()})
            row.update(interruption=timeline.label(timeline.t0),
                       evaluation=timeline.label(timeline.k),
                       time_unit="days" if timeline.mode == "dates" else "index steps")
            rows.append(row)
    finally:
        stream.close()
    stream, writer = open_csv(folder / "coefficients.csv", list(rows[0]))
    try:
        writer.writerows(rows)
    finally:
        stream.close()
    return [str(folder / "series.csv"), str(folder / "coefficients.csv")], fits


def write_classes(folder, counts, pixel_area_ha):
    """Write recovery_classes.csv from per-class pixel counts (index = class code)."""
    total = int(counts[1:].sum())
    stream, writer = open_csv(folder / "recovery_classes.csv",
                              ["class", "label", "pixels", "area_ha", "percent"])
    try:
        for code, _, label, _ in CLASSES:
            pixels = int(counts[code])
            writer.writerow({"class": code, "label": label, "pixels": pixels,
                             "area_ha": "" if pixel_area_ha is None
                             else round(pixels * pixel_area_ha, 2),
                             "percent": round(100 * pixels / total, 2) if total else ""})
    finally:
        stream.close()
    return str(folder / "recovery_classes.csv")
