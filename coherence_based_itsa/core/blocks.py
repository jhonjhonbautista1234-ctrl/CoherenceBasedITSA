# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from dataclasses import dataclass, field

import numpy as np
from osgeo import gdal

from .errors import check_cancel
from .model import fit_series
from .products import CLASSES, DESCRIPTIONS, products
from .rasters import create_raster, read_stack, write_block
from .regions import region_mask
from .tables import coefficient_row

SAMPLE_PER_BLOCK = 4000


@dataclass
class BlockStats:
    samples: list = field(default_factory=list)
    class_counts: np.ndarray = field(
        default_factory=lambda: np.zeros(len(CLASSES) + 1, dtype=np.int64))
    fitted_pixels: int = 0
    csv_rows: int = 0

    @property
    def sample(self):
        return np.concatenate(self.samples) if self.samples else np.array([])


def create_outputs(folder, grid, options, result):
    outputs = {}
    for name, description in DESCRIPTIONS.items():
        path = folder / (name + ".tif")
        if name == "recovery_class":
            dataset = create_raster(path, grid, 0, description, gdal.GDT_Byte)
        else:
            dataset = create_raster(path, grid, options.nodata, description)
        dataset.SetMetadataItem("bias_correction", options.bias)
        dataset.SetMetadataItem("covariance", options.covariance)
        outputs[name] = dataset
        result.rasters.append(str(path))
    return outputs


def process_blocks(options, grid, sources, tables, timeline, outputs, summaries,
                   aoi, regions, writer, progress, cancelled):
    """Fit every block of the grid, write the rasters and accumulate the statistics."""
    stats = BlockStats()
    total = grid.window_count(options.block_size)
    for index, window in enumerate(grid.windows(options.block_size)):
        check_cancel(cancelled)
        progress(5 + 80 * index / total, f"Fitting block {index + 1} of {total}")
        inside = region_mask(aoi, window, grid, options.all_touched) if aoi else None
        if aoi and inside is None:
            continue
        stack = read_stack(sources, options.observations, tables, window, options)
        if inside is not None:
            stack[:, ~inside] = np.nan
        if not np.isfinite(stack).any():
            continue
        summaries[0].add(stack.reshape(len(stack), -1))
        for summary, region in zip(summaries[1:], regions):
            mask = region_mask(region, window, grid, options.all_touched)
            if mask is not None:
                summary.add(stack[:, mask])
        fit = fit_series(stack, timeline.times, timeline.phases, timeline.fitted_post,
                         timeline.t0, options)
        arrays = products(fit, timeline.t0, timeline.k, options.metric, stack.shape[1:],
                          options.class_tolerance)
        if inside is not None:
            for name in ("valid_count", "pre_count", "post_count"):
                arrays[name][~inside] = np.nan
        for name, values in arrays.items():
            if name == "recovery_class":
                classes = np.where(np.isfinite(values), values, 0).astype("uint8")
                outputs[name].GetRasterBand(1).WriteArray(classes, window[0], window[1])
                stats.class_counts += np.bincount(classes.ravel(),
                                                  minlength=len(CLASSES) + 1)
            else:
                write_block(outputs[name], values, window, options.nodata)
        valid = arrays["recovery"][np.isfinite(arrays["recovery"])]
        stats.fitted_pixels += valid.size
        if valid.size:
            stats.samples.append(
                valid[::max(1, valid.size // SAMPLE_PER_BLOCK)].astype("float32"))
        if writer:
            stats.csv_rows = pixel_rows(writer, fit, window, grid, options,
                                        stats.csv_rows)
    return stats


def pixel_rows(writer, fit, window, grid, options, written):
    col, row, columns, rows = window
    t, width = grid.transform, grid.width
    for local in np.flatnonzero(np.isfinite(fit.beta).all(0)):
        if written >= options.pixel_cap:
            break
        y, x = row + local // columns, col + local % columns
        if (y * width + x) % options.pixel_step != 0:
            continue
        writer.writerow(dict(row=y, column=x,
                             x=round(t[0] + (x + 0.5) * t[1] + (y + 0.5) * t[2], 3),
                             y=round(t[3] + (x + 0.5) * t[4] + (y + 0.5) * t[5], 3),
                             **coefficient_row("pixel", fit, local)))
        written += 1
    return written
