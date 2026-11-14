# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

import math
from pathlib import Path


def validate_options(options):
    enums = {"metric": ("net_effect", "slope_change"), "covariance": ("ols", "newey_west"),
             "bias": ("none", "expectation_inversion"),
             "resampling": ("nearest", "bilinear", "cubic", "average")}
    for name, allowed in enums.items():
        if getattr(options, name) not in allowed:
            raise ValueError("Invalid setting: " + name)
    for name, lower in (("min_pre", 2), ("min_post", 2), ("nw_lags", 0),
                        ("lookup_points", 16), ("block_size", 1), ("histogram_bins", 1),
                        ("dpi", 50), ("pixel_step", 1), ("pixel_cap", 1)):
        value = getattr(options, name)
        if not isinstance(value, int) or value < lower:
            raise ValueError(f"{name} must be an integer >= {lower}.")
    if options.lookup_points > 65537:
        raise ValueError("lookup_points must not exceed 65537.")
    if not math.isfinite(options.nodata) or abs(options.nodata) > 3.4e38:
        raise ValueError("Nodata must be a finite float32 value.")
    if options.nodata >= 0:
        raise ValueError("Use negative output nodata outside the count "
                         "and p-value ranges.")
    if options.low_threshold is not None and not 0 <= options.low_threshold <= 1:
        raise ValueError("Low-coherence threshold must lie in [0,1].")
    if not options.output_folder:
        raise ValueError("Choose an output folder.")
    for observation in options.observations:
        if not Path(observation.path).is_file():
            raise ValueError("Raster file does not exist: " + observation.path)
        if observation.band < 1:
            raise ValueError("Band numbers start at 1.")
        if options.bias != "none" and (
                not math.isfinite(observation.looks) or observation.looks <= 1):
            raise ValueError("Enter independent looks L > 1 for every raster.")
    unique = {(str(Path(o.path).resolve()), o.band)
              for o in options.observations}
    if len(unique) != len(options.observations):
        raise ValueError("The same raster band cannot be supplied more than once.")
