# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

import os
import argparse
from pathlib import Path
import subprocess
import zipfile

root = Path(__file__).resolve().parents[1]
executable = Path(os.environ["OSGEO4W_ROOT"]) / "bin" / "qgis-bin.exe"
profiles = root / "tmp" / "qgis_profiles"
profiles.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument("--smoke", action="store_true")
args = parser.parse_args()
profile = "itsa_smoke" if args.smoke else "itsa_test"
command = [str(executable), "--profiles-path", str(profiles), "--profile", profile, "--nologo"]
if args.smoke:
    destination = profiles / "profiles" / profile / "python" / "plugins"
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(root / "dist" / "coherence_based_itsa-1.0.0.zip") as archive:
        assert all(name.startswith("coherence_based_itsa/") and ".." not in name.split("/")
                   for name in archive.namelist())
        archive.extractall(destination)
    command.extend(["--code", str(root / "tools" / "gui_smoke.py")])
subprocess.Popen(command,
                 cwd=str(root), env=dict(os.environ, ITSA_WORKSPACE=str(root)),
                 stdout=(root / "tmp" / "qgis_stdout.txt").open("w"),
                 stderr=(root / "tmp" / "qgis_stderr.txt").open("w"))
