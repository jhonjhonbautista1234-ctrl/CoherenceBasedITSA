# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

"""Guess the phase and acquisition dates of a coherence raster from its file name."""

from datetime import datetime
from pathlib import Path
import re

DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})[-_.]?(\d{2})[-_.]?(\d{2})(?!\d)")


def guess_dates(path):
    """Return up to two ISO dates found in the file name, in order of appearance."""
    found = []
    for year, month, day in DATE.findall(Path(path).stem):
        try:
            found.append(datetime(int(year), int(month), int(day)).date().isoformat())
        except ValueError:
            continue
    start = found[0] if found else ""
    end = found[1] if len(found) > 1 and found[1] > found[0] else ""
    return start, end


def guess_phase(path):
    """Return pre, event or post, or an empty string when the name gives no hint."""
    name = Path(path).stem.lower()
    if re.search(r"straddl|co[-_ ]?event|coseismic|syn[-_ ]?event", name):
        return "event"
    if re.search(r"(?<![a-z])pre(?![a-z])|pre[-_ ]?event|before", name):
        return "pre"
    if re.search(r"(?<![a-z])post(?![a-z])|post[-_ ]?event|after", name):
        return "post"
    if re.search(r"(?<![a-z])event(?![a-z])", name):
        return "event"
    return ""


def describe(path):
    start, end = guess_dates(path)
    return guess_phase(path), start, end
