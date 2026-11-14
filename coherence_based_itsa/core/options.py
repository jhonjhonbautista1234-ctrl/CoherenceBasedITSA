# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class Observation:
    path: str
    phase: str
    date: str = ""
    looks: float = 4.0
    band: int = 1


@dataclass
class Options:
    observations: List[Observation]
    output_folder: str
    time_mode: str = "index"
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
    resample: bool = False
    resampling: str = "bilinear"
    block_size: int = 256
    nodata: float = -9999.0
    histogram_bins: int = 50
    dpi: int = 150
    aoi_path: str = ""
    features_path: str = ""
    all_touched: bool = False
    pixel_csv: bool = False
    pixel_step: int = 1
    pixel_cap: int = 10000

    def serializable(self):
        return asdict(self)


@dataclass
class RunResult:
    folder: str
    rasters: List[str] = field(default_factory=list)
    tables: List[str] = field(default_factory=list)
    graphs: List[str] = field(default_factory=list)
