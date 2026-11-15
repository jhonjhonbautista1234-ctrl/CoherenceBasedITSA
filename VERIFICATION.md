# Verification record

Checks actually performed for Coherence Based ITSA 1.1.2. Anything not listed
here has not been tested.

## Environment

| Item | Value |
| --- | --- |
| Date | 2026-11-15 |
| Operating system | Windows 11 Home (64-bit) |
| QGIS | 4.2.3 (OSGeo4W build, Qt 6) |
| Python | 3.12 (QGIS interpreter, `python-qgis.bat`) |

## Checks and results

| Check | Command | Result |
| --- | --- | --- |
| Unit tests | `python -B -m unittest discover -s tests` | 22 of 22 passed |
| Offscreen QGIS, bundled sample | `python -B tools/verify_qgis.py` | Passed |
| Offscreen QGIS, real data through the dialog | `python -B tools/verify_qgis.py <Coherence folder> <INFANTA_BOUNDARY.kml>` | Passed, 10.7 s |
| Engine on real data, full extent, no AOI | `python -B tools/run_real.py <Coherence folder> <output>` | Completed in 244 s: 8,451 x 13,216 grid, 32,453,656 fitted pixels |
| Packaging | `python -B tools/package.py` | ZIP built, about 62 KB, archive integrity and contents checked |

All commands were run with the QGIS Python interpreter.

### Real data

Seven Sentinel-1 coherence GeoTIFFs exported from SNAP for Infanta, Quezon
(3 PRE, 1 event-straddling, 3 POST pairs, 21 July to 6 November 2022, about
8,600 x 13,250 pixels each, PRS92 zone 3). They exercise the cases that stopped
version 1.0.0:

- every raster has a different extent, origin and pixel size, so 1.0.0 stopped with
  "Input grids or CRS differ";
- no nodata value is declared and about 71% of each raster is zero fill, which
  1.0.0 would have fitted as real coherence;
- the dates exist only in the file names.

The dialog check adds the folder to the table, confirms that the phases and the
pair dates were read from the file names, sets the AOI file, runs the background
task and waits for it. It then confirms that 15 rasters and 3 tables were loaded,
that `recovery` opened with the pseudocolour style and `recovery class` with the
paletted style, and that the results window opened.

Result for the Infanta AOI: 860,931 fitted pixels; AOI mean coherence 0.187, 0.188,
0.173 (PRE), 0.167 (event), 0.183, 0.172, 0.170 (POST); interruption 25 Sep 2022;
level change +0.018 (p = 0.13), trend change -0.0002 per day (p = 0.42), net effect
on 31 Oct 2022 +0.009, R-squared 0.92. Classes: 69.0% no detectable loss, 12.8%
recovered, 6.1% partially recovered, 12.1% not recovered. The pixel count and the
coherence level agree with the earlier stand-alone pilot on the same data
(859,255 common-support pixels, medians near 0.15 to 0.16). The figures were
inspected by eye.

The unit tests cover known coefficients, missingness patterns, event inclusion,
classical and Newey-West covariance against independent references, the
bias-correction expectation, non-finite inputs, source range validation, automatic
grid alignment and its opt-out, zero fill, phase and dates from file names, sorting
by time, pair midpoints, AOI cropping, feature series, recovery classes, QGIS
style files, CSV contents, deterministic export and cancellation status.

## Not tested

- QGIS Desktop with a visible window: the dialog was driven offscreen, so the
  widgets were exercised but not clicked by hand. **Install from ZIP** was not run.
- QGIS 3.x (3.22 to 3.44) and the Qt 5 bindings. Compatibility is declared in
  `metadata.txt` but has not been run.
- Linux and macOS.
- Date mode with Newey-West errors or bias correction on real data; these are
  covered by the unit tests only.
- Stacks longer than seven rasters on real data.
