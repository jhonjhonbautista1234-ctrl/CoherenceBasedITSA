# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class Observation:
    path: str
    phase: str
    date: str = ""        # acquisition date, or first date of an interferometric pair
    looks: float = 4.0
    band: int = 1
    end_date: str = ""    # second date of the pair; the observation is timed at the midpoint


@dataclass
class Options:
    observations: List[Observation]
    output_folder: str
    time_mode: str = "auto"            # auto | dates | index
    interruption: Optional[float] = None
    include_event: bool = False
    metric: str = "net_effect"
    evaluation_time: Optional[float] = None
    min_pre: int = 2
    min_post: int = 2
    covariance: str = "ols"
    nw_lags: int = 1
    bias: str = "none"
    lookup_points: int = 4097
    low_threshold: Optional[float] = None
    zero_is_nodata: bool = True        # exact zeros are fill, as in SNAP exports
    resample: bool = True              # align mismatched grids to the first raster
    resampling: str = "bilinear"
    block_size: int = 1024
    nodata: float = -9999.0
    class_tolerance: float = 0.05      # coherence units, for the recovery classes
    histogram_bins: int = 60
    dpi: int = 200
    aoi_path: str = ""
    features_path: str = ""
    all_touched: bool = False
    pixel_csv: bool = False
    pixel_step: int = 1
    pixel_cap: int = 10000
    title: str = ""

    def serializable(self):
        return asdict(self)


@dataclass
class RunResult:
    folder: str
    rasters: List[str] = field(default_factory=list)
    tables: List[str] = field(default_factory=list)
    graphs: List[str] = field(default_factory=list)
