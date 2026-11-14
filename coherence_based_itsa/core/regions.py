# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from dataclasses import dataclass

import numpy as np
from osgeo import gdal, ogr, osr


@dataclass
class Region:
    identifier: str
    name: str
    geometries: list


def read_regions(path, reference, combine=False):
    source = ogr.Open(path)
    if source is None:
        raise ValueError("Cannot open vector file: " + path)
    target = osr.SpatialReference()
    target.ImportFromWkt(reference.GetProjection())
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    regions, all_geometries = [], []
    for layer in source:
        srs = layer.GetSpatialRef()
        if srs is None:
            raise ValueError("Vector layer requires an explicit CRS.")
        srs = srs.Clone()
        srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        conversion = osr.CoordinateTransformation(srs, target)
        for feature in layer:
            geometry = feature.GetGeometryRef()
            if geometry is None or geometry.IsEmpty():
                continue
            geometry = geometry.Clone()
            if geometry.Transform(conversion) != 0 or not geometry.IsValid():
                raise ValueError("Feature geometry is invalid; repair it before running.")
            kind = ogr.GT_Flatten(geometry.GetGeometryType())
            if kind not in (ogr.wkbPolygon, ogr.wkbMultiPolygon, ogr.wkbPoint, ogr.wkbMultiPoint):
                raise ValueError("Feature summaries support points and polygons only.")
            if combine and kind in (ogr.wkbPoint, ogr.wkbMultiPoint):
                raise ValueError("The AOI must contain polygons.")
            identifier = f"{layer.GetName()}:{feature.GetFID()}"
            regions.append(Region(identifier, identifier, [geometry]))
            all_geometries.append(geometry)
    if not regions:
        raise ValueError("Vector file has no usable features.")
    return [Region("aoi", "AOI", all_geometries)] if combine else regions


def region_mask(region, window, reference, all_touched):
    col, row, width, height = window
    transform = reference.GetGeoTransform()
    affine = (transform[0] + col * transform[1] + row * transform[2], transform[1],
              transform[2], transform[3] + col * transform[4] + row * transform[5],
              transform[4], transform[5])
    raster = gdal.GetDriverByName("MEM").Create("", width, height, 1, gdal.GDT_Byte)
    raster.SetGeoTransform(affine)
    raster.SetProjection(reference.GetProjection())
    driver = ogr.GetDriverByName("MEM") or ogr.GetDriverByName("Memory")
    vector = driver.CreateDataSource("")
    srs = osr.SpatialReference()
    srs.ImportFromWkt(reference.GetProjection())
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    layer = vector.CreateLayer("region", srs=srs, geom_type=ogr.wkbUnknown)
    for geometry in region.geometries:
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetGeometry(geometry)
        layer.CreateFeature(feature)
    gdal.RasterizeLayer(raster, [1], layer, burn_values=[1],
                        options=["ALL_TOUCHED=" + ("TRUE" if all_touched else "FALSE")])
    return raster.ReadAsArray() != 0
