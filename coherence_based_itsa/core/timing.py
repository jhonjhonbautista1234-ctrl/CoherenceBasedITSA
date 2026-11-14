# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from datetime import datetime

import numpy as np


def chronology(options):
    records = options.observations
    if any(o.phase not in ("pre", "event", "post") for o in records):
        raise ValueError("Unknown observation group.")
    phases = np.array([o.phase for o in records])
    if options.time_mode == "dates":
        if any(not o.date for o in records):
            raise ValueError("Date mode requires a date for every raster.")
        dates = [datetime.strptime(o.date, "%Y-%m-%d") for o in records]
        origin = min(dates)
        times = np.array([(d - origin).total_seconds() / 86400 for d in dates])
        origin_text = origin.date().isoformat()
    elif options.time_mode == "index":
        if any(o.date for o in records):
            raise ValueError("Clear dates in index mode, or supply all dates in date mode.")
        times = np.arange(len(records), dtype=float)
        origin_text = "index 0"
    else:
        raise ValueError("Time mode must be index or dates.")
    if len(times) < 4 or np.any(np.diff(times) <= 0):
        raise ValueError("Supply at least four observations in distinct increasing time order.")
    pre, event, post = phases == "pre", phases == "event", phases == "post"
    fitted_post = post | (event & options.include_event)
    if pre.sum() < options.min_pre or fitted_post.sum() < options.min_post:
        raise ValueError("The stack cannot satisfy the minimum PRE and POST observation counts.")
    if not post.any() or times[pre].max() >= times[post].min():
        raise ValueError("PRE observations must precede POST observations.")
    if event.any() and (times[event].min() <= times[pre].max()
                        or times[event].max() >= times[post].min()):
        raise ValueError("Event observations must lie between PRE and POST.")
    default = (float(np.mean([times[event].min(), times[event].max()]))
               if event.any() else float((times[pre].max() + times[post].min()) / 2))
    t0 = default if options.interruption is None else options.interruption
    if not np.isfinite(t0) or not times[pre].max() < t0 < times[post].min():
        raise ValueError("Interruption time must lie strictly between last PRE and first POST.")
    k = times[-1] if options.evaluation_time is None else options.evaluation_time
    if not np.isfinite(k) or not times[post].min() <= k <= times[-1]:
        raise ValueError("Evaluation time must be within the observed POST period.")
    return times, phases, fitted_post, float(t0), float(k), origin_text
