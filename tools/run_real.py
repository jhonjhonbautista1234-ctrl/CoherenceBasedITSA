# SPDX-License-Identifier: GPL-2.0-or-later
"""Run the engine on a folder of coherence rasters without opening QGIS.

python-qgis.bat tools/run_real.py <raster folder> <output folder> [AOI vector file]
"""
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coherence_based_itsa.core.engine import run
from coherence_based_itsa.core.naming import describe
from coherence_based_itsa.core.options import Observation, Options

observations = []
for path in sorted(Path(sys.argv[1]).glob("*.tif")):
    phase, start, end = describe(path)
    print(f"{phase:5} {start} {end}  {path.name}")
    observations.append(Observation(str(path), phase, start, end_date=end))
options = Options(observations, sys.argv[2], aoi_path=sys.argv[3] if len(sys.argv) > 3 else "")
started = time.time()
last = [-10]


def progress(value, message):
    if value - last[0] >= 10 or value >= 86:
        last[0] = value
        print(f"{value:5.1f}%  {message}  [{time.time() - started:.0f}s]", flush=True)


result = run(options, progress)
print("Run folder:", result.folder)
for path in result.rasters + result.tables + result.graphs:
    print("  ", Path(path).name)
