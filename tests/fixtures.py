# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

import json
from pathlib import Path

import numpy as np
from osgeo import gdal, osr

from coherence_based_itsa.core.options import Observation, Options


def make_stack(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32651)
    observations = []
    for index in range(11):
        phase = "pre" if index < 5 else "event" if index == 5 else "post"
        value = 0.65 - 0.01 * index
        if phase == "post":
            value += -0.2 + 0.035 * (index - 5)
        path = folder / f"{index:02d}_{phase}.tif"
        source = gdal.GetDriverByName("GTiff").Create(str(path), 5, 4, 1, gdal.GDT_Float32)
        source.SetGeoTransform((500000, 10, 0, 1600000, 0, -10))
        source.SetProjection(srs.ExportToWkt())
        band = source.GetRasterBand(1)
        band.SetNoDataValue(-9999)
        values = np.full((4, 5), value, dtype="float32")
        values[0, 0] = -9999
        band.WriteArray(values)
        source = None
        observations.append(Observation(str(path), phase))
    return Options(observations, str(folder / "outputs"), block_size=2, dpi=50)


def make_polygon(path):
    polygon = dict(type="FeatureCollection", name="aoi",
                   crs={"type": "name", "properties": {"name": "EPSG:32651"}},
                   features=[dict(type="Feature", properties={"name": "test"}, geometry=dict(
                       type="Polygon", coordinates=[[[500000, 1600000], [500030, 1600000],
                                                    [500030, 1599970], [500000, 1599970],
                                                    [500000, 1600000]]]))])
    Path(path).write_text(json.dumps(polygon), encoding="utf-8")
