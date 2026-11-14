# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
from osgeo import gdal

from .model import fit_series
from .blocks import process_blocks
from .errors import CancelledError, check_cancel
from .options import RunResult
from .products import histogram_edges
from .rasters import open_sources, windows
from .regions import read_regions
from .tables import coefficient_row, open_csv, write_summaries
from .timing import chronology
from .validation import validate_options


def validate_source_ranges(options, cancelled):
    from .coherence import prepare_values
    from .rasters import read_band
    for observation in options.observations:
        source = gdal.Open(observation.path, gdal.GA_ReadOnly)
        for window in windows(source, options.block_size):
            check_cancel(cancelled)
            prepare_values(read_band(source, observation, window), options)
        source = None


def run(options, progress=None, cancelled=None):
    progress = progress or (lambda value, message: None)
    cancelled = cancelled or (lambda: False)
    validate_options(options)
    times, phases, post, t0, k, origin = chronology(options)
    check_cancel(cancelled)
    sources, tables = open_sources(options)
    progress(0, "Validating source coherence ranges")
    validate_source_ranges(options, cancelled)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = Path(options.output_folder) / ("itsa_" + stamp)
    folder.mkdir(parents=True, exist_ok=False)
    result = RunResult(str(folder))
    parameters = dict(options=options.serializable(), resolved_time=times.tolist(),
                      time_origin=origin, interruption=t0, evaluation_time=k,
                      status="running", coefficient_order=["b0", "b1", "b2", "b3"],
                      model="b0 + b1*time + b2*post + b3*(time-T0)*post",
                      nw_kernel="Bartlett", nw_finite_sample_adjustment=False,
                      residual_order="consecutive finite fitted observations",
                      bias_application="per observation before spatial averaging and fitting",
                      threshold_application="after bias correction", covariance=options.covariance)
    outputs = {}
    try:
        save_parameters(folder, parameters)
        with (folder / "processing.log").open("w", encoding="utf-8") as log:
            log.write(f"bias_correction={options.bias}\ncovariance={options.covariance}\n")
            execute(options, sources, tables, times, phases, post, t0, k,
                    folder, outputs, result, parameters, progress, cancelled)
        parameters["status"] = "complete"
        progress(100, "Complete")
        return result
    except BaseException as error:
        parameters.update(status="cancelled" if isinstance(error, CancelledError) else "failed",
                          error=str(error))
        raise
    finally:
        outputs.clear()
        sources.clear()
        save_parameters(folder, parameters)


def save_parameters(folder, parameters):
    path = folder / "run_parameters.json"
    path.write_text(json.dumps(parameters, indent=2), encoding="utf-8")


def execute(options, sources, tables, times, phases, post, t0, k,
            folder, outputs, result, parameters, progress, cancelled):
    reference = sources[0]
    aoi = read_regions(options.aoi_path, reference, True)[0] if options.aoi_path else None
    regions = read_regions(options.features_path, reference) if options.features_path else []
    summaries = {
        name: (np.zeros(len(times)), np.zeros(len(times), dtype=np.int64))
        for name in ["AOI"] + [r.identifier for r in regions]}
    stream, writer = None, None
    if options.pixel_csv:
        columns = ["row", "column"] + list(coefficient_row("", fit_series(
            np.full((len(times), 1), np.nan), times, phases, post, t0, options)))
        stream, writer = open_csv(folder / "pixels.csv", options, columns)
        result.tables.append(str(folder / "pixels.csv"))
    try:
        minimum, maximum, written = process_blocks(options, sources, tables, times, phases,
            post, t0, k, folder, outputs, result, summaries, aoi, regions, writer, progress, cancelled)
        parameters.update(pixel_csv_rows=written, valid_recovery_range=[minimum, maximum]
                          if np.isfinite(minimum) else None)
    finally:
        if stream:
            stream.close()
    for dataset in outputs.values():
        dataset.FlushCache()
    check_cancel(cancelled)
    summary_tables, fits, series = write_summaries(folder, summaries, times, phases, post,
                                                   t0, options, fit_series)
    result.tables.extend(summary_tables)
    from .plots import histogram_graph, series_graph
    for index, name in enumerate(summaries):
        check_cancel(cancelled)
        path = folder / f"series_{index:04d}.png"
        series_graph(path, name, series[index], fits[index], times, phases,
                     post, t0, options)
        result.graphs.append(str(path))
    edges = histogram_edges(minimum, maximum, options.histogram_bins)
    counts = np.zeros(options.histogram_bins, dtype=np.int64)
    for window in windows(reference, options.block_size):
        check_cancel(cancelled)
        a = outputs["recovery"].ReadAsArray(*window)
        counts += np.histogram(a[np.isfinite(a) & (a != options.nodata)], edges)[0]
    path = folder / "recovery_histogram.png"
    histogram_graph(path, edges, counts, options)
    result.graphs.append(str(path))
    parameters["histogram_edges"] = edges.tolist()
    parameters["outputs"] = dict(rasters=result.rasters, tables=result.tables, graphs=result.graphs)


