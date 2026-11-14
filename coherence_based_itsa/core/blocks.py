# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

import numpy as np

from .errors import check_cancel
from .model import fit_series
from .products import products
from .rasters import create_raster, read_stack, windows, write_block
from .regions import region_mask
from .tables import coefficient_row


def process_blocks(options, sources, tables, times, phases, post, t0, k, folder,
                   outputs, result, summaries, aoi, regions, writer, progress, cancelled):
    reference = sources[0]
    total = ((reference.RasterXSize + options.block_size - 1) // options.block_size
             * ((reference.RasterYSize + options.block_size - 1) // options.block_size))
    minimum, maximum, written = np.inf, -np.inf, 0
    for index, window in enumerate(windows(reference, options.block_size)):
        check_cancel(cancelled)
        stack = read_stack(sources, options.observations, tables, window, options)
        inside = (region_mask(aoi, window, reference, options.all_touched)
                  if aoi else np.ones(stack.shape[1:], bool))
        stack[:, ~inside] = np.nan
        masks = [inside] + [
            inside & region_mask(r, window, reference, options.all_touched)
            for r in regions]
        for name, mask in zip(summaries, masks):
            values = stack[:, mask]
            sums, counts = summaries[name]
            sums += np.nansum(values, axis=1)
            counts += np.isfinite(values).sum(axis=1)
        fit = fit_series(stack, times, phases, post, t0, options)
        arrays = products(fit, t0, k, options.metric, stack.shape[1:])
        for name, values in arrays.items():
            values[~inside] = np.nan
            if name not in outputs:
                path = folder / (name + ".tif")
                outputs[name] = create_raster(path, reference, options.nodata, name)
                outputs[name].SetMetadataItem("bias_correction", options.bias)
                outputs[name].SetMetadataItem("covariance", options.covariance)
                result.rasters.append(str(path))
            write_block(outputs[name], values, window, options.nodata)
        valid = arrays["recovery"][np.isfinite(arrays["recovery"])]
        if valid.size:
            # Use exported precision for histogram bounds.
            minimum = min(minimum, float(valid.astype("float32").min()))
            maximum = max(maximum, float(valid.astype("float32").max()))
        if writer:
            written = pixel_rows(writer, fit, window, reference.RasterXSize, options, written)
        progress(5 + 85 * (index + 1) / total, f"Fitting block {index + 1}/{total}")
    return minimum, maximum, written


def pixel_rows(writer, fit, window, width, options, written):
    col, row, columns, rows = window
    for local in np.flatnonzero(np.isfinite(fit.beta).all(0)):
        y, x = row + local // columns, col + local % columns
        if (y * width + x) % options.pixel_step != 0 or written >= options.pixel_cap:
            continue
        writer.writerow(dict(row=y, column=x, **coefficient_row("pixel", fit, local)))
        written += 1
    return written
