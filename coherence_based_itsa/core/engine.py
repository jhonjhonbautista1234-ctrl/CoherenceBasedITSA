# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
import re
import time

import numpy as np
from osgeo import gdal

from .blocks import create_outputs, process_blocks
from .errors import CancelledError, check_cancel
from .model import fit_series
from .options import RunResult
from .products import robust_edges, symmetric_limit
from .rasters import open_raster, open_sources, read_preview, reference_grid
from .regions import read_regions
from .styles import class_style, diverging_style
from .tables import Summary, coefficient_row, open_csv, write_classes, write_summaries
from .timing import chronology, sort_observations
from .validation import validate_options


def run(options, progress=None, cancelled=None):
    """Run the whole analysis and return a RunResult listing every output file."""
    progress = progress or (lambda value, message: None)
    cancelled = cancelled or (lambda: False)
    options = replace(options, observations=list(options.observations))
    validate_options(options)
    sort_observations(options)
    timeline = chronology(options)
    check_cancel(cancelled)
    progress(0, "Opening rasters")
    sources, outputs = [], {}
    try:
        first = open_raster(options.observations[0])
        sources.append(first)
        aoi = (read_regions(options.aoi_path, first.GetProjection(), True)[0]
               if options.aoi_path else None)
        grid = reference_grid(first, aoi.envelope if aoi else None)
        regions = (read_regions(options.features_path, grid.projection)
                   if options.features_path else [])
        opened, tables = open_sources(options, grid, first)
        sources[:] = opened
        first = None
    except BaseException:
        sources.clear()   # release the file handles before the error propagates
        first = None
        raise
    folder = new_folder(options.output_folder)
    result = RunResult(str(folder))
    parameters = dict(
        status="running", options=options.serializable(), time_mode=timeline.mode,
        time_origin=timeline.origin_text, resolved_time=timeline.times.tolist(),
        interruption=timeline.t0, interruption_label=timeline.label(timeline.t0),
        evaluation_time=timeline.k, evaluation_label=timeline.label(timeline.k),
        grid=dict(width=grid.width, height=grid.height, transform=list(grid.transform)),
        model="b0 + b1*time + b2*post + b3*(time-T0)*post",
        coefficient_order=["b0", "b1", "b2", "b3"],
        recovery_metric=options.metric,
        recovery_classes="1 no loss (b2 >= -tol); 2 recovered (net >= -tol); "
                         "3 partial (b2 < net < -tol); 4 not recovered (net <= b2)",
        observation_time="midpoint of the pair dates" if timeline.mode == "dates"
                         else "order index",
        nw_kernel="Bartlett", nw_finite_sample_adjustment=False,
        bias_application="per observation before spatial averaging and fitting",
        threshold_application="after bias correction")
    started = time.time()
    try:
        save_parameters(folder, parameters)
        execute(options, grid, sources, tables, timeline, aoi, regions, folder, outputs,
                result, parameters, progress, cancelled)
        parameters.update(status="complete", seconds=round(time.time() - started, 1))
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
        (folder / "processing.log").write_text(
            "\n".join(f"{key}: {parameters.get(key)}" for key in (
                "status", "error", "seconds", "time_mode", "interruption_label",
                "evaluation_label", "fitted_pixels", "grid")) + "\n", encoding="utf-8")


def new_folder(parent):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder, suffix = Path(parent) / ("itsa_" + stamp), 1
    while folder.exists():
        suffix += 1
        folder = Path(parent) / f"itsa_{stamp}_{suffix}"
    folder.mkdir(parents=True)
    return folder


def save_parameters(folder, parameters):
    (folder / "run_parameters.json").write_text(json.dumps(parameters, indent=2),
                                                encoding="utf-8")


def slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:60] or "region"


def execute(options, grid, sources, tables, timeline, aoi, regions, folder, outputs,
            result, parameters, progress, cancelled):
    count = len(timeline.times)
    summaries = [Summary("AOI" if aoi else "Full extent", count)]
    summaries += [Summary(region.identifier, count) for region in regions]
    outputs.update(create_outputs(folder, grid, options, result))
    stream, writer = None, None
    if options.pixel_csv:
        columns = ["row", "column", "x", "y"] + list(coefficient_row("", fit_series(
            np.full((count, 1), np.nan), timeline.times, timeline.phases,
            timeline.fitted_post, timeline.t0, options)))
        stream, writer = open_csv(folder / "pixels.csv", columns)
        result.tables.append(str(folder / "pixels.csv"))
    try:
        stats = process_blocks(options, grid, sources, tables, timeline, outputs, summaries,
                               aoi, regions, writer, progress, cancelled)
    finally:
        if stream:
            stream.close()
    for dataset in outputs.values():
        dataset.FlushCache()
    check_cancel(cancelled)
    progress(86, "Writing tables")
    summary_tables, fits = write_summaries(folder, summaries, timeline, options, fit_series)
    result.tables[:0] = summary_tables + [
        write_classes(folder, stats.class_counts, grid.pixel_area_ha())]

    sample = stats.sample
    limit = symmetric_limit(sample)
    diverging_style(folder / "recovery.tif", limit)
    for name in ("level_change", "slope_change"):
        diverging_style(folder / (name + ".tif"), band_limit(outputs[name], options.nodata))
    class_style(folder / "recovery_class.tif")

    from .plots import class_map, histogram_graph, recovery_map, series_graph
    progress(88, "Drawing time-series graphs")
    for index, (summary, (series, q25, q75, fit)) in enumerate(zip(summaries, fits)):
        check_cancel(cancelled)
        path = folder / f"timeseries_{index:03d}_{slug(summary.name)}.png"
        series_graph(path, summary.name, series, q25, q75, fit, timeline, options,
                     int(summary.counts.max()))
        result.graphs.append(str(path))

    progress(92, "Drawing recovery maps")
    outlines = aoi.outlines() if aoi else []
    metres = grid.pixel_area_ha() is not None
    array, extent = read_preview(folder / "recovery.tif")
    path = folder / "recovery_map.png"
    recovery_map(path, array, extent, limit, outlines, metres, options, timeline)
    result.graphs.insert(0, str(path))
    array, extent = read_preview(folder / "recovery_class.tif", categorical=True)
    path = folder / "recovery_class_map.png"
    class_map(path, array, extent, stats.class_counts, outlines, metres, options, timeline)
    result.graphs.insert(1, str(path))

    progress(96, "Drawing histogram")
    edges = robust_edges(sample, options.histogram_bins)
    counts = np.zeros(options.histogram_bins, dtype=np.int64)
    for window in grid.windows(options.block_size):
        check_cancel(cancelled)
        a = outputs["recovery"].GetRasterBand(1).ReadAsArray(*window)
        counts += np.histogram(a[a != np.float32(options.nodata)], edges)[0]
    path = folder / "recovery_histogram.png"
    histogram_graph(path, edges, counts, stats.fitted_pixels - int(counts.sum()),
                    options, timeline)
    result.graphs.append(str(path))
    parameters.update(
        fitted_pixels=stats.fitted_pixels, pixel_csv_rows=stats.csv_rows,
        recovery_colour_limit=limit, histogram_edges=edges.tolist(),
        class_pixels={str(code): int(n) for code, n in enumerate(stats.class_counts) if code},
        outputs=dict(rasters=result.rasters, tables=result.tables, graphs=result.graphs))


def band_limit(dataset, nodata):
    """Symmetric colour limit of a written raster, from a reduced-resolution read."""
    band = dataset.GetRasterBand(1)
    factor = max(1, max(dataset.RasterXSize, dataset.RasterYSize) // 1000)
    a = band.ReadAsArray(buf_xsize=max(1, dataset.RasterXSize // factor),
                         buf_ysize=max(1, dataset.RasterYSize // factor),
                         resample_alg=gdal.GRIORA_NearestNeighbour)
    return symmetric_limit(a[a != np.float32(nodata)])
