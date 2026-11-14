# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

import configparser
from pathlib import Path
import zipfile


def package(root):
    source = root / "coherence_based_itsa"
    metadata = configparser.ConfigParser()
    metadata.read(source / "metadata.txt", encoding="utf-8")
    required = ("name", "qgisMinimumVersion", "description", "about", "version", "author",
                "email", "homepage", "tracker", "repository", "license", "changelog", "icon")
    if any(not metadata["general"].get(key, "").strip() for key in required):
        raise ValueError("Missing publication metadata.")
    for name in ("README.md", "LICENSE", "icon.png", "__init__.py"):
        if not (source / name).is_file():
            raise ValueError("Missing package file: " + name)
    destination = root / "dist"
    destination.mkdir(exist_ok=True)
    path = destination / ("coherence_based_itsa-" + metadata["general"]["version"] + ".zip")
    banned = {".dll", ".so", ".exe", ".pyd", ".pyc", ".pyo"}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(source.rglob("*")):
            relative = item.relative_to(root)
            if any(p.startswith(".") or p == "__pycache__" for p in relative.parts):
                continue
            if item.is_file():
                if item.suffix.lower() in banned or item.name.startswith("ui_") or item.name == "resources_rc.py":
                    raise ValueError("Disallowed package file: " + str(relative))
                archive.write(item, str(relative).replace("\\", "/"))
    if path.stat().st_size >= 20 * 1024 * 1024:
        raise ValueError("ZIP must remain under 20 MB.")
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert all(n.startswith("coherence_based_itsa/") for n in archive.namelist())
    print(path)
    print(f"{path.stat().st_size} bytes")


if __name__ == "__main__":
    package(Path(__file__).resolve().parents[1])
