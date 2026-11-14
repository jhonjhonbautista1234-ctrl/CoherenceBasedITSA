# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.fixtures import make_stack

root = Path(__file__).resolve().parents[1]
folder = root / "coherence_based_itsa" / "sample"
options = make_stack(folder)
manifest = dict(observations=[dict(path=Path(o.path).name, phase=o.phase, date=o.date,
                                    looks=o.looks, band=o.band) for o in options.observations],
                time_mode="index", interruption=5, evaluation_time=10,
                expected=dict(b0=0.65, b1=-0.01, b2=-0.2, b3=0.035, net_effect=-0.025))
(folder / "sample.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(sum(p.stat().st_size for p in folder.iterdir() if p.is_file()), "sample bytes")
