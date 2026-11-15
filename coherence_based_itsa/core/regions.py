# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from dataclasses import dataclass

import numpy as np
from osgeo import gdal, ogr, osr

POLYGONS = (ogr.wkbPolygon, ogr.wkbMultiPolygon)
POINTS = (ogr.wkbPoint, ogr.wkbMultiPoint)


@dataclass
class Region:
    identifier: str
    name: str
    geometries: list

    @property
    def envelope(self):
        """(xmin, ymin, xmax, ymax) in the raster CRS."""
        boxes = np.array([g.GetEnvelope() for g in self.geometries])
        return boxes[:, 0].min(), boxes[:, 2].min(), boxes[:, 1].max(), boxes[:, 3].max()

    def outlines(self):
        """Polygon rings as (x, y) arrays, for drawing on map figures."""
        rings = []

        def collect(geometry):
            if geometry.GetGeometryCount():
                for index in range(geometry.GetGeometryCount()):
                    collect(geometry.GetGeometryRef(index))
            elif geometry.GetPointCount() > 1:
                rings.append(np.array(geometry.GetPoints())[:, :2])

        for geometry in self.geometries:
            if ogr.GT_Flatten(geometry.GetGeometryType()) in POLYGONS:
                collect(geometry)
        return rings


def feature_name(feature):
    for index in range(feature.GetFieldCount()):
        if feature.GetFieldDefnRef(index).GetName().lower() in ("name", "label", "id"):
            value = feature.GetField(index)
            if value not in (None, ""):
                return str(value)
    return ""


def read_regions(path, projection, combine=False):
    source = ogr.Open(path)
    if source is None:
        raise ValueError("Cannot open vector file: " + path)
    target = osr.SpatialReference()
    target.ImportFromWkt(projection)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    regions, all_geometries = [], []
    for layer in source:
        srs = layer.GetSpatialRef()
        if srs is None:
            raise ValueError("Vector layer requires a CRS: " + path)
        srs = srs.Clone()
        srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        conversion = osr.CoordinateTransformation(srs, target)
        for feature in layer:
            geometry = feature.GetGeometryRef()
            if geometry is None or geometry.IsEmpty():
                continue
            geometry = geometry.Clone()
            geometry.FlattenTo2D()
            if geometry.Transform(conversion) != 0:
                raise ValueError("Could not reproject a feature to the raster CRS.")
            kind = ogr.GT_Flatten(geometry.GetGeometryType())
            if kind in POLYGONS and not geometry.IsValid():
                geometry = geometry.MakeValid()
                if geometry is None or geometry.IsEmpty():
                    raise ValueError("Feature geometry is invalid; repair it before running.")
                kind = ogr.GT_Flatten(geometry.GetGeometryType())
            if kind not in POLYGONS + POINTS:
                if combine:
                    continue
                raise ValueError("Feature summaries support points and polygons only.")
            if combine and kind in POINTS:
                continue
            identifier = f"{layer.GetName()}:{feature.GetFID()}"
            name = feature_name(feature)
            if name:
                identifier = f"{name} ({identifier})"
            regions.append(Region(identifier, name or identifier, [geometry]))
            all_geometries.append(geometry)
    if not regions:
        raise ValueError("The AOI file has no polygons." if combine
                         else "Vector file has no usable features.")
    return [Region("AOI", "AOI", all_geometries)] if combine else regions


def region_mask(region, window, grid, all_touched):
    """Boolean mask of the window's pixels inside the region; None when it cannot overlap."""
    col, row, width, height = window
    t = grid.transform
    left, top = t[0] + col * t[1], t[3] + row * t[5]
    right, bottom = left + width * t[1], top + height * t[5]
    xmin, ymin, xmax, ymax = region.envelope
    if t[2] == 0 and t[4] == 0 and (xmax < min(left, right) or xmin > max(left, right)
                                    or ymax < min(top, bottom) or ymin > max(top, bottom)):
        return None
    affine = (left + row * t[2], t[1], t[2], top + col * t[4], t[4], t[5])
    raster = gdal.GetDriverByName("MEM").Create("", width, height, 1, gdal.GDT_Byte)
    raster.SetGeoTransform(affine)
    raster.SetProjection(grid.projection)
    driver = ogr.GetDriverByName("MEM") or ogr.GetDriverByName("Memory")
    vector = driver.CreateDataSource("")
    srs = osr.SpatialReference()
    srs.ImportFromWkt(grid.projection)
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    layer = vector.CreateLayer("region", srs=srs, geom_type=ogr.wkbUnknown)
    for geometry in region.geometries:
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetGeometry(geometry)
        layer.CreateFeature(feature)
    gdal.RasterizeLayer(raster, [1], layer, burn_values=[1],
                        options=["ALL_TOUCHED=" + ("TRUE" if all_touched else "FALSE")])
    mask = raster.ReadAsArray() != 0
    return mask if mask.any() else None
