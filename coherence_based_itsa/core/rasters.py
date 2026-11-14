# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from pathlib import Path

import numpy as np
from osgeo import gdal, osr

from .coherence import lookup_table, prepare_values


def same_crs(first, second):
    a, b = osr.SpatialReference(), osr.SpatialReference()
    if not first or not second:
        return False
    a.ImportFromWkt(first)
    b.ImportFromWkt(second)
    return bool(a.IsSame(b))


def open_sources(options):
    sources, tables = [], []
    reference = None
    for observation in options.observations:
        source = gdal.Open(observation.path, gdal.GA_ReadOnly)
        if source is None:
            raise ValueError("Cannot open raster: " + observation.path)
        if observation.band > source.RasterCount:
            raise ValueError("Band does not exist: " + observation.path)
        if not source.GetProjection():
            raise ValueError("Raster has no CRS: " + observation.path)
        band = source.GetRasterBand(observation.band)
        if gdal.DataTypeIsComplex(band.DataType):
            raise ValueError("Input is complex data, not coherence magnitude.")
        if reference is None:
            reference = source
        same_grid = (source.RasterXSize == reference.RasterXSize
                     and source.RasterYSize == reference.RasterYSize
                     and source.GetGeoTransform() == reference.GetGeoTransform()
                     and same_crs(source.GetProjection(), reference.GetProjection()))
        if not same_grid:
            if not options.resample:
                raise ValueError("Input grids or CRS differ. Explicitly enable resampling: "
                                 + Path(observation.path).name)
            source = warp_source(source, reference, options)
        sources.append(source)
        tables.append(lookup_table(observation.looks, options.lookup_points)
                      if options.bias == "expectation_inversion" else None)
    return sources, tables


def warp_source(source, reference, options):
    transform = reference.GetGeoTransform()
    if (transform[2] != 0 or transform[4] != 0
            or transform[1] <= 0 or transform[5] >= 0):
        raise ValueError("Explicit resampling requires a north-up reference grid.")
    x, y = reference.RasterXSize, reference.RasterYSize
    result = gdal.Warp("", source, format="VRT", dstSRS=reference.GetProjection(),
                       outputBounds=(transform[0], transform[3] + y * transform[5],
                                     transform[0] + x * transform[1], transform[3]),
                       width=x, height=y, resampleAlg=options.resampling,
                       outputType=gdal.GDT_Float64, dstNodata=float("nan"))
    if result is None:
        raise ValueError("GDAL resampling failed.")
    return result


def windows(source, size):
    for row in range(0, source.RasterYSize, size):
        for col in range(0, source.RasterXSize, size):
            yield col, row, min(size, source.RasterXSize - col), min(size, source.RasterYSize - row)


def read_band(source, observation, window):
    band = source.GetRasterBand(observation.band)
    a = band.ReadAsArray(*window).astype(float)
    mask = band.GetMaskBand().ReadAsArray(*window) != 0
    nodata = band.GetNoDataValue()
    if nodata is not None:
        mask &= ~np.isnan(a) if np.isnan(nodata) else a != nodata
    a[~mask] = np.nan
    scale, offset = band.GetScale(), band.GetOffset()
    return a * (1.0 if scale is None else scale) + (0.0 if offset is None else offset)


def read_stack(sources, observations, tables, window, options):
    return np.stack([prepare_values(read_band(src, obs, window), options, table)
                     for src, obs, table in zip(sources, observations, tables)])


def create_raster(path, reference, nodata, description):
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path), reference.RasterXSize, reference.RasterYSize, 1, gdal.GDT_Float32,
        options=["TILED=YES", "COMPRESS=DEFLATE", "PREDICTOR=3", "BIGTIFF=IF_SAFER"])
    if dataset is None:
        raise OSError("Cannot create output: " + str(path))
    dataset.SetGeoTransform(reference.GetGeoTransform())
    dataset.SetProjection(reference.GetProjection())
    dataset.GetRasterBand(1).SetNoDataValue(nodata)
    dataset.GetRasterBand(1).SetDescription(description)
    return dataset


def write_block(dataset, values, window, nodata):
    a = np.asarray(values)
    if np.any(np.isfinite(a) & (a == nodata)):
        raise ValueError("Output nodata collides with a computed value. "
                         "Choose another nodata value.")
    a = np.where(np.isfinite(a), a, nodata).astype("float32")
    if not np.isfinite(a).all():
        raise ValueError("A computed value exceeds the float32 output range.")
    dataset.GetRasterBand(1).WriteArray(a, window[0], window[1])
