# Verification record

Checks actually performed for Coherence Based ITSA 1.0.0. Anything not listed
here has not been tested.

## Environment

| Item | Value |
| --- | --- |
| Date | 2026-11-14 |
| Operating system | Windows 11 Home (64-bit) |
| QGIS | 4.2.3 (OSGeo4W build, Qt 6) |
| Python | 3.12.15 |
| GDAL | 3.13.3 |
| NumPy / SciPy / matplotlib | 2.4.6 / 1.18.1 / 3.11.2 |

## Checks and results

| Check | Command | Result |
| --- | --- | --- |
| Unit tests | `python -B -m unittest discover -s tests -v` | 19 of 19 passed |
| Packaging | `python -B tools/package.py` | ZIP built, about 46 KB, archive integrity and contents checked |
| Offscreen QGIS integration | `python -B tools/verify_qgis.py` | Passed |
| Packaged plugin in QGIS Desktop | `python -B tools/launch_qgis.py --smoke` | Passed |

All commands were run with the QGIS Python interpreter (`python-qgis.bat`).

The unit tests cover known coefficients, missingness patterns, event
inclusion, classical and Newey-West covariance against independent
references, the bias-correction expectation against simulated sample coherence
and direct summation of Touzi Eq. 6, non-finite inputs, source range
validation, grid rejection and explicit resampling, raster metadata,
AOI/feature series, deterministic CSV export and cancellation status.

The offscreen integration check confirms that the dialog opens, the Processing
provider registers `coherence_itsa:coherence_itsa`, a Processing run completes,
the 14 rasters and 2 tables load into the project, and the provider is removed
on unload.

The packaged-plugin check extracts `dist/coherence_based_itsa-1.0.0.zip` into
the plugin folder of an isolated QGIS profile, starts QGIS Desktop, loads the
plugin, fills the dialog with the bundled `sample/` rasters and runs the
analysis as a background task. The run finished with status `complete`, 16
layers were loaded into the project, and the output rasters matched the
documented sample values (b2 = -0.2, b3 = 0.035, pre trend = -0.01, post
trend = 0.025, net effect = -0.025, nodata in the upper-left pixel).

The regression coefficients, classical and Newey-West standard errors and
p-values were also compared with an explicit textbook implementation on an
irregular dated series and agreed to about 1e-15. An engine run with bias
correction and Newey-West enabled completed on the synthetic stack.

## Not tested

- QGIS 3.x (3.22 to 3.44) and the Qt 5 bindings. Compatibility is declared in
  `metadata.txt` but has not been run.
- Linux and macOS.
- The **Install from ZIP** screen itself; the ZIP was extracted into the
  profile plugin folder by script instead.
- Large rasters, real SAR coherence products, and performance with many
  features.
- Date mode, Newey-West, bias correction, AOI and resampling through the
  dialog. These are covered by unit tests of the engine, not by a GUI run.
