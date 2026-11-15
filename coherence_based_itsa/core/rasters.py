# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from osgeo import gdal, osr

from .coherence import lookup_table, prepare_values


@dataclass
class Grid:
    """The analysis grid: every input is read on it and every output is written on it."""
    transform: tuple
    width: int
    height: int
    projection: str

    @property
    def bounds(self):
        t = self.transform
        return (t[0], t[3] + self.height * t[5], t[0] + self.width * t[1], t[3])

    def pixel_area_ha(self):
        srs = osr.SpatialReference()
        srs.ImportFromWkt(self.projection)
        if not srs.IsProjected():
            return None
        unit = srs.GetLinearUnits()
        return abs(self.transform[1] * self.transform[5]) * unit * unit / 10000.0

    def windows(self, size):
        for row in range(0, self.height, size):
            for col in range(0, self.width, size):
                yield col, row, min(size, self.width - col), min(size, self.height - row)

    def window_count(self, size):
        return -(-self.width // size) * -(-self.height // size)


def same_crs(first, second):
    a, b = osr.SpatialReference(), osr.SpatialReference()
    if not first or not second:
        return False
    a.ImportFromWkt(first)
    b.ImportFromWkt(second)
    return bool(a.IsSame(b))


def open_raster(observation):
    source = gdal.Open(observation.path, gdal.GA_ReadOnly)
    if source is None:
        raise ValueError("Cannot open raster: " + observation.path)
    if observation.band > source.RasterCount:
        raise ValueError("Band does not exist: " + observation.path)
    if not source.GetProjection():
        raise ValueError("Raster has no CRS: " + observation.path)
    if gdal.DataTypeIsComplex(source.GetRasterBand(observation.band).DataType):
        raise ValueError("Input is complex data, not coherence magnitude: " + observation.path)
    return source


def reference_grid(source, envelope=None):
    """Grid of the first raster, optionally cropped to an (xmin, ymin, xmax, ymax) envelope."""
    t = source.GetGeoTransform()
    grid = Grid(tuple(t), source.RasterXSize, source.RasterYSize, source.GetProjection())
    if envelope is None:
        return grid
    if t[2] != 0 or t[4] != 0 or t[1] <= 0 or t[5] >= 0:
        return grid
    xmin, ymin, xmax, ymax = envelope
    col0 = max(0, int(np.floor((xmin - t[0]) / t[1])))
    col1 = min(grid.width, int(np.ceil((xmax - t[0]) / t[1])))
    row0 = max(0, int(np.floor((ymax - t[3]) / t[5])))
    row1 = min(grid.height, int(np.ceil((ymin - t[3]) / t[5])))
    if col1 <= col0 or row1 <= row0:
        raise ValueError("The AOI does not overlap the coherence rasters.")
    return Grid((t[0] + col0 * t[1], t[1], 0.0, t[3] + row0 * t[5], 0.0, t[5]),
                col1 - col0, row1 - row0, grid.projection)


def view_on_grid(source, grid, observation, options):
    """Return a dataset exposing the source on the analysis grid."""
    s, g = source.GetGeoTransform(), grid.transform
    if same_crs(source.GetProjection(), grid.projection) and s[1:3] == g[1:3] and s[4:] == g[4:]:
        col, row = (g[0] - s[0]) / s[1], (g[3] - s[3]) / s[5]
        whole = abs(col - round(col)) < 1e-6 and abs(row - round(row)) < 1e-6
        col, row = int(round(col)), int(round(row))
        if (whole and col >= 0 and row >= 0 and col + grid.width <= source.RasterXSize
                and row + grid.height <= source.RasterYSize):
            if (col, row, grid.width, grid.height) == (0, 0, source.RasterXSize, source.RasterYSize):
                return source
            return gdal.Translate("", source, format="VRT",
                                  srcWin=[col, row, grid.width, grid.height])
    if not options.resample:
        raise ValueError("Input grids or CRS differ. Enable grid alignment (resampling): "
                         + Path(observation.path).name)
    if g[2] != 0 or g[4] != 0 or g[1] <= 0 or g[5] >= 0:
        raise ValueError("Grid alignment requires a north-up first raster.")
    nodata = source.GetRasterBand(observation.band).GetNoDataValue()
    if nodata is None and options.zero_is_nodata:
        nodata = 0.0
    result = gdal.Warp("", source, format="VRT", dstSRS=grid.projection,
                       outputBounds=grid.bounds, width=grid.width, height=grid.height,
                       resampleAlg=options.resampling, outputType=gdal.GDT_Float32,
                       srcNodata=nodata, dstNodata=float("nan"), multithread=True)
    if result is None:
        raise ValueError("GDAL could not align " + Path(observation.path).name)
    return result


def open_sources(options, grid, first):
    sources, tables = [], []
    for index, observation in enumerate(options.observations):
        source = first if index == 0 else open_raster(observation)
        sources.append(view_on_grid(source, grid, observation, options))
        tables.append(lookup_table(observation.looks, options.lookup_points)
                      if options.bias == "expectation_inversion" else None)
    return sources, tables


def read_band(source, observation, window, zero_is_nodata=False):
    band = source.GetRasterBand(observation.band)
    a = band.ReadAsArray(*window).astype(float)
    mask = band.GetMaskBand().ReadAsArray(*window) != 0
    nodata = band.GetNoDataValue()
    if nodata is not None:
        mask &= ~np.isnan(a) if np.isnan(nodata) else a != nodata
    if zero_is_nodata:
        mask &= a != 0
    a[~mask] = np.nan
    scale, offset = band.GetScale(), band.GetOffset()
    if scale not in (None, 1.0) or offset not in (None, 0.0):
        a = a * (1.0 if scale is None else scale) + (0.0 if offset is None else offset)
    return a


def read_stack(sources, observations, tables, window, options):
    return np.stack([
        prepare_values(read_band(src, obs, window, options.zero_is_nodata), options, table)
        for src, obs, table in zip(sources, observations, tables)])


def create_raster(path, grid, nodata, description, data_type=gdal.GDT_Float32):
    predictor = "3" if data_type == gdal.GDT_Float32 else "2"
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path), grid.width, grid.height, 1, data_type,
        options=["TILED=YES", "COMPRESS=DEFLATE", "PREDICTOR=" + predictor,
                 "BIGTIFF=IF_SAFER"])
    if dataset is None:
        raise OSError("Cannot create output: " + str(path))
    dataset.SetGeoTransform(grid.transform)
    dataset.SetProjection(grid.projection)
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(nodata)
    band.SetDescription(description)
    band.Fill(nodata)
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


def read_preview(path, limit=1800, categorical=False):
    """Read a raster at reduced size for map figures. Returns array (nan = no data), extent."""
    dataset = gdal.Open(str(path))
    band = dataset.GetRasterBand(1)
    factor = max(1.0, max(dataset.RasterXSize, dataset.RasterYSize) / limit)
    width = max(1, int(round(dataset.RasterXSize / factor)))
    height = max(1, int(round(dataset.RasterYSize / factor)))
    algorithm = gdal.GRIORA_Mode if categorical else gdal.GRIORA_Average
    a = band.ReadAsArray(buf_xsize=width, buf_ysize=height,
                         resample_alg=algorithm).astype(float)
    a[a == band.GetNoDataValue()] = np.nan
    t = dataset.GetGeoTransform()
    extent = (t[0], t[0] + dataset.RasterXSize * t[1],
              t[3] + dataset.RasterYSize * t[5], t[3])
    return a, extent
