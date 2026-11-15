# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np


@dataclass
class Timeline:
    times: np.ndarray          # days from origin (date mode) or order index
    phases: np.ndarray
    fitted_post: np.ndarray    # observations fitted in the post segment
    t0: float
    k: float
    mode: str                  # dates | index
    origin: Optional[datetime]
    starts: np.ndarray         # interval start per observation, same units as times
    ends: np.ndarray

    @property
    def origin_text(self):
        return self.origin.date().isoformat() if self.origin else "index 0"

    def date_of(self, value):
        return self.origin + timedelta(days=float(value)) if self.origin else None

    def label(self, value):
        moment = self.date_of(value)
        return moment.strftime("%d %b %Y") if moment else f"index {value:g}"


def parse(text):
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Dates must be written YYYY-MM-DD, not '{text}'.") from None


def resolve_mode(options):
    dated = [bool(o.date) for o in options.observations]
    if options.time_mode == "auto":
        return "dates" if all(dated) else "index"
    if options.time_mode == "dates":
        if not all(dated):
            raise ValueError("Date mode requires a date for every raster.")
        return "dates"
    if options.time_mode == "index":
        return "index"
    raise ValueError("Time mode must be auto, dates or index.")


def sort_observations(options):
    """In date mode put the rasters in time order so the user does not have to."""
    if resolve_mode(options) != "dates":
        return
    options.observations.sort(key=lambda o: _interval(o)[2])


def _interval(observation):
    start = parse(observation.date)
    end = parse(observation.end_date) if observation.end_date else start
    if end < start:
        raise ValueError("A pair's end date precedes its start date: " + observation.path)
    return start, end, start + (end - start) / 2


def chronology(options):
    records = options.observations
    if any(o.phase not in ("pre", "event", "post") for o in records):
        raise ValueError("Every raster needs a phase: pre, event or post.")
    phases = np.array([o.phase for o in records])
    mode = resolve_mode(options)
    if mode == "dates":
        intervals = [_interval(o) for o in records]
        origin = min(i[0] for i in intervals)

        def days(moment):
            return (moment - origin).total_seconds() / 86400

        starts = np.array([days(i[0]) for i in intervals])
        ends = np.array([days(i[1]) for i in intervals])
        times = np.array([days(i[2]) for i in intervals])
    else:
        origin = None
        times = np.arange(len(records), dtype=float)
        starts = ends = times
    if len(times) < 4 or np.any(np.diff(times) <= 0):
        raise ValueError("Supply at least four rasters with distinct dates, in time order.")
    pre, event, post = phases == "pre", phases == "event", phases == "post"
    fitted_post = post | (event & options.include_event)
    if pre.sum() < options.min_pre or fitted_post.sum() < options.min_post:
        raise ValueError(f"Need at least {options.min_pre} PRE and {options.min_post} POST "
                         f"rasters; got {int(pre.sum())} PRE and {int(fitted_post.sum())} POST.")
    if not post.any() or times[pre].max() >= times[post].min():
        raise ValueError("PRE rasters must precede POST rasters.")
    if event.any() and (times[event].min() <= times[pre].max()
                        or times[event].max() >= times[post].min()):
        raise ValueError("Event rasters must lie between PRE and POST.")
    default = (float(np.mean([times[event].min(), times[event].max()]))
               if event.any() else float((times[pre].max() + times[post].min()) / 2))
    t0 = default if options.interruption is None else float(options.interruption)
    if not np.isfinite(t0) or not times[pre].max() < t0 < times[post].min():
        raise ValueError("Interruption time must lie strictly between last PRE and first POST.")
    k = times[-1] if options.evaluation_time is None else float(options.evaluation_time)
    if not np.isfinite(k) or not times[post].min() <= k <= times[-1]:
        raise ValueError("Evaluation time must be within the observed POST period.")
    return Timeline(times, phases, fitted_post, float(t0), float(k), mode, origin, starts, ends)
