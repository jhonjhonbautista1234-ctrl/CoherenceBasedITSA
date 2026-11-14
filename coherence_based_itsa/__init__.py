# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

def classFactory(iface):
    from .plugin import CoherenceBasedItsa
    return CoherenceBasedItsa(iface)
