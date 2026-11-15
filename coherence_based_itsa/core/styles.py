# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

"""QGIS layer styles (.qml) written beside the rasters so they open ready-styled."""

from pathlib import Path

import numpy as np

from .products import CLASSES, DIVERGING

HEADER = ("<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>\n"
          '<qgis version="3.22.0" styleCategories="Symbology">\n  <pipe>\n')
FOOTER = ('    <brightnesscontrast brightness="0" contrast="0" gamma="1"/>\n'
          '    <huesaturation saturation="0" grayscaleMode="0" colorizeOn="0"/>\n'
          '    <rasterresampler maxOversampling="2"/>\n  </pipe>\n</qgis>\n')


def diverging_style(raster_path, limit):
    """Symmetric red-neutral-blue ramp centred on zero."""
    values = np.linspace(-limit, limit, len(DIVERGING))
    items = "".join(
        f'          <item value="{value:.6g}" color="{colour}" alpha="255" '
        f'label="{value:+.3g}"/>\n' for value, colour in zip(values, DIVERGING))
    body = (f'    <rasterrenderer type="singlebandpseudocolor" band="1" opacity="1" '
            f'alphaBand="-1" classificationMin="{-limit:.6g}" '
            f'classificationMax="{limit:.6g}">\n'
            '      <rastershader>\n'
            f'        <colorrampshader colorRampType="INTERPOLATED" classificationMode="1" '
            f'clip="0" minimumValue="{-limit:.6g}" maximumValue="{limit:.6g}">\n'
            f'{items}        </colorrampshader>\n      </rastershader>\n'
            '    </rasterrenderer>\n')
    Path(raster_path).with_suffix(".qml").write_text(HEADER + body + FOOTER, encoding="utf-8")


def class_style(raster_path):
    entries = "".join(
        f'        <paletteEntry value="{code}" color="{colour}" alpha="255" label="{label}"/>\n'
        for code, _, label, colour in CLASSES)
    body = ('    <rasterrenderer type="paletted" band="1" opacity="1" alphaBand="-1">\n'
            f'      <colorPalette>\n{entries}      </colorPalette>\n'
            '    </rasterrenderer>\n')
    Path(raster_path).with_suffix(".qml").write_text(HEADER + body + FOOTER, encoding="utf-8")
