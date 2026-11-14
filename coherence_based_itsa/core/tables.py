# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

import csv

import numpy as np


def open_csv(path, options, columns):
    stream = path.open("w", newline="", encoding="utf-8")
    stream.write(f"# bias_correction={options.bias}; covariance={options.covariance}; "
                 f"time_mode={options.time_mode}\n")
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    return stream, writer


def coefficient_row(scope, fit, index=0):
    row = dict(scope=scope, n=int(fit.n[index]), pre_count=int(fit.pre_count[index]),
               post_count=int(fit.post_count[index]), r_squared=fit.r_squared[index],
               residual_lag1=fit.lag1[index])
    for term in range(4):
        row[f"b{term}"] = fit.beta[term, index]
        row[f"b{term}_se"] = fit.standard_errors[term, index]
        row[f"b{term}_p"] = fit.p_values[term, index]
    return row


def write_summaries(folder, summaries, times, phases, fitted_post, t0, options, fit_function):
    tables, fits, series_list = [], [], []
    coefficient_rows = []
    stream, writer = open_csv(folder / "series.csv", options,
                              ["scope", "observation", "phase", "date", "time", "included",
                               "mean", "valid_pixels", "fitted", "counterfactual", "residual"])
    try:
        for name, (totals, counts) in summaries.items():
            series = np.divide(totals, counts, out=np.full(len(times), np.nan), where=counts > 0)
            fit = fit_function(series[:, None], times, phases, fitted_post, t0, options)
            fits.append(fit)
            series_list.append(series)
            coefficient_rows.append(coefficient_row(name, fit))
            b = fit.beta[:, 0]
            for i, observation in enumerate(options.observations):
                included = bool(phases[i] == "pre" or fitted_post[i])
                fitted = fit.fitted[i, 0] if included else np.nan
                writer.writerow(dict(scope=name, observation=i,
                                     phase=phases[i], date=observation.date,
                                     time=times[i], included=included, mean=series[i],
                                     valid_pixels=int(counts[i]), fitted=fitted,
                                     counterfactual=b[0] + b[1] * times[i],
                                     residual=series[i] - fitted))
    finally:
        stream.close()
    columns = list(coefficient_row("", fits[0]))
    stream, writer = open_csv(folder / "coefficients.csv", options, columns)
    try:
        writer.writerows(coefficient_rows)
    finally:
        stream.close()
    tables.extend([str(folder / "series.csv"), str(folder / "coefficients.csv")])
    return tables, fits, series_list
