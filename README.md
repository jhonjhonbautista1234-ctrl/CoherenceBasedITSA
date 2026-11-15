# Coherence Based ITSA

Per-pixel interrupted time series analysis of SAR coherence magnitudes for QGIS 3.22 and later.

Copyright (C) 2026 Allen John T. Bautista. This software is licensed under
GPL-2.0-or-later: GNU GPL version 2 or, at your option, any later version.

## Install

In QGIS, open **Plugins > Manage and Install Plugins > Install from ZIP** and
select `coherence_based_itsa-1.1.0.zip`. Enable **Coherence Based ITSA** and open
**Raster > Coherence Based ITSA**. The official Plugin Manager search will list
the plugin after its submission to, and approval by, the QGIS repository.

Requires NumPy, SciPy, GDAL/OGR and matplotlib in the QGIS Python environment.
No packages are installed by the plugin. No network connection is used during analysis.
If an import fails, repair the QGIS distribution rather than installing into a
different Python environment. Windows, Linux and macOS use the same source.

## Inputs and workflow

1. Open **Raster > Coherence Based ITSA**.
2. Click **Add folder...** (or **Add files...** / **Add open raster layers**) and pick
   the coherence rasters. One table lists them all. The phase (PRE, EVENT, POST) and
   the dates are read from each file name, for example
   `Coherence_Pre-Event-04_20220721_20220802_split_Orb_Stack_esd_coh_deb_TC.tif`
   is PRE, 2022-07-21 to 2022-08-02. Correct any cell that was guessed wrongly.
3. Optionally choose a study-area (AOI) polygon: a project layer or a file
   (`.kml`, `.gpkg`, `.shp`, `.geojson`). The outputs are cropped to it.
4. Choose an output folder and click **Run**.

Each run creates a new `itsa_YYYYMMDD_HHMMSS` subfolder; earlier runs are never
replaced. The recovery map and the recovery classes load into the project already
styled, the other model rasters go into a collapsed **Model details** group, the CSV
tables load as attribute tables, and a results window shows the figures. The work
runs in a cancellable background task. A cancelled or failed run keeps its partial
outputs with that status in `run_parameters.json`.

**Time.** With the default *Automatic* time coordinate, dates are used when every
raster has one; otherwise the table order is used as an index. Dated rasters are
sorted by time, so the table order does not matter. A raster with two dates is an
interferometric pair and is timed at the midpoint of the pair. Time is in days from
the earliest date. At least two PRE and two POST rasters are required; standard
errors and p-values need at least five fitted observations per pixel.
Event-straddling rasters are plotted but not fitted unless you enable their inclusion.

**Values.** Inputs must be real coherence magnitudes in [0,1]; anything outside
stops the run. Declared nodata, raster masks, NaN and infinite values are missing.
Exact zeros are treated as no data by default because SNAP writes zero outside the
swath without declaring nodata; switch this off under *Analysis options* if your
zeros are real. GDAL scale/offset metadata is applied. There is no temporal
interpolation.

**Grids.** Rasters that do not share one grid (different extent, origin, pixel size
or CRS) are aligned to the grid of the first raster in time, bilinear by default.
Rasters that only differ by a whole-pixel offset are read directly without
resampling. Switch alignment off to make mismatched grids an error instead. Cubic
resampling can overshoot [0,1]; such values are rejected.

## ITSA model and recovery metric

The model is

`Y(t) = b0 + b1*time + b2*post + b3*(time-T0)*post + error`.

`b2` is the level discontinuity at T0 and `b3` is the slope change. The pre
trend is `b1`; the post trend is `b1+b3`. Time is scaled internally for numerical
conditioning and coefficients are transformed back to the declared time units.
Pixels are grouped by missingness pattern and fitted with vectorised NumPy OLS.

T0 defaults to the midpoint between last Pre and first Post, or the midpoint
of the event observation range. Each event observation is plotted at its own
time. T0 can be entered explicitly, strictly between last Pre and first Post.
With multiple events included in Post, the Post indicator follows the assigned
group even for event observations earlier than T0.

The default recovery map is the net effect against the pre counterfactual:

`net_effect(k) = b2 + b3*(k-T0)`.

`k` defaults to the last observation and can be set within the observed Post
range. Alternatively select slope change `b3`. Positive net effect means
coherence above the counterfactual; a negative value means below it. Positive
slope change describes an increase relative to the pre slope, not necessarily
an increasing absolute post trend.

`recovery_class.tif` turns the same two numbers into four descriptive classes,
using a tolerance `tol` (default 0.05 coherence units):

| Class | Meaning | Rule |
| --- | --- | --- |
| 1 | No detectable coherence loss | `b2 >= -tol` |
| 2 | Coherence recovered | `b2 < -tol` and `net_effect(k) >= -tol` |
| 3 | Partially recovered | `b2 < net_effect(k) < -tol` |
| 4 | Not recovered / further loss | `net_effect(k) <= b2 < -tol` |

The classes describe coherence relative to the continued PRE trend. Single-pixel
coherence is noisy and the classes carry no significance test; they do not
establish physical reconstruction or ecological recovery.

## Statistical inference

Minimum Pre and Post counts are configurable, each at least two. A rank-four
design and at least four fitted observations are required. A stack unable to
meet the configured counts stops immediately. Individual unsupported pixels
have undefined coefficients and effect maps. Observation count rasters remain
available as diagnostics, including zero for completely missing pixels inside
the AOI. Outside the AOI all rasters have output nodata.

Classical standard errors use `SSE/(n-4)` and two-sided Student t p-values with
`n-4` degrees of freedom. Exactly four observations can determine coefficients,
but standard errors and p-values are undefined and exported as nodata/NaN.
R-squared is `1-SSE/SST`; it is undefined when SST is zero.

Optional Newey-West covariance uses Bartlett weights and the chosen maximum
lag, with no finite-sample multiplier. P-values use asymptotic normal inference.
Lags beyond the available observations have no cross-products. Lags count
consecutive finite fitted observations, not calendar intervals; missing dates
are not imputed and can cause lags to span gaps. Use caution for irregular time
series. Residual lag-1 autocorrelation is the Pearson correlation between the
adjacent residual vectors in that same order, including the segment boundary.
It is undefined if either vector has zero variance.

Short series, correlated acquisition pairs, seasonal effects, nonlinearity,
unmeasured confounding and spatial dependence limit inference. Newey-West
changes covariance, not coefficients, and does not resolve these limitations.

## Coherence bias correction

Default: none. Optional expectation inversion uses Touzi et al. (1999), Eq. 6
and Eq. 20, with independent looks L > 1 entered separately for each raster.
An equally spaced lookup table in true magnitude D is precomputed for each L.
Its resolution is configurable from 16 to 65537 points. Eq. 6 is

`E(d|D,L) = Gamma(L)*Gamma(3/2)/Gamma(L+1/2) * 3F2(3/2,L,L;L+1/2,1;D^2) * (1-D^2)^L`.

The 3F2 series is summed term by term in logarithms, so it stays finite close
to D=1 and for large L. The tests compare it with simulated sample coherence.

Linear lookup inversion maps observed magnitudes below E(d|D=0,L) to zero and
the upper endpoint to one. Corrected magnitudes are clipped to [0,1]. The
optional low-coherence mask is applied **after** correction; values strictly
below the threshold are missing. Correction is applied to each observation's
pixels before fitting and spatial averaging. This order is explicitly recorded.

The inversion corrects the expectation, works best on spatially averaged values,
and cannot remove bias under nonstationarity. Applying the nonlinear inverse
to individual noisy pixels does not yield an unbiased per-pixel estimator;
averaging corrected pixels differs from correcting an average. L is the number
of independent looks, not necessarily the window's pixel count. One-look
magnitude does not identify true coherence through this inversion. No intensity
correlation estimator is used.

Touzi, R., Lopes, A., Bruniquel, J., and Vachon, P. W. (1999). Coherence
Estimation for SAR Imagery. IEEE Transactions on Geoscience and Remote Sensing,
37(1), 135-149. https://doi.org/10.1109/36.739146

## AOI and feature series

Leave the AOI empty to analyse the full grid. Otherwise choose a polygon layer or
file. Geometries are reprojected to the raster CRS and invalid polygons are repaired.
The analysis grid is cropped to the AOI bounding box, pixels outside the polygons are
no data, and blocks that do not touch the AOI are skipped, so a small AOI inside a
large scene runs quickly. The default mask uses pixel centres; all-touched inclusion
is optional.

Optionally choose a point/polygon layer or file under **Extra graphs per feature**
to get one time-series graph and one coefficient row per feature. Project layers
(optionally only the selected features) are saved as a GeoPackage snapshot under the
output folder before the background run. Features are named by their `name` field
when present, plus layer name and feature ID. Each feature is intersected with the
AOI. Overlapping polygons are summarised independently.

Graphs and coefficients for the AOI and the features use the arithmetic mean of the
valid pixels at each date; the spatial median and quartiles are exported alongside.
These aggregate fits are separate from the pixel fits and are not averages of pixel
coefficients.

## Outputs

Rasters are tiled, compressed GeoTIFFs on the analysis grid and CRS. Model rasters
are float32 with configurable negative nodata (default -9999); `recovery_class.tif`
is byte with nodata 0.

| File | Content |
| --- | --- |
| recovery.tif (+ .qml) | Recovery map: net effect at k, or slope change |
| recovery_class.tif (+ .qml) | Recovery classes 1-4 |
| level_change.tif, slope_change.tif (+ .qml) | b2, b3 |
| pre_trend.tif, post_trend.tif | b1, b1+b3 |
| r_squared.tif | R-squared |
| valid_count.tif, pre_count.tif, post_count.tif | Fitted observation counts |
| level_se.tif, slope_se.tif | Standard errors of b2, b3 |
| level_p.tif, slope_p.tif | Two-sided p-values of b2, b3 |
| residual_lag1.tif | Lag-1 residual autocorrelation |
| recovery_map.png | Recovery map figure with colour bar, scale bar and AOI outline |
| recovery_class_map.png | Recovery class figure with the share of each class |
| timeseries_000_AOI.png, timeseries_001_... | ITSA graph of the AOI, then of each feature |
| recovery_histogram.png | Distribution of the recovery map over all fitted pixels |
| series.csv | Per date: phase, dates, mean, median, quartiles, valid pixels, fitted value, counterfactual, residual |
| coefficients.csv | Per AOI/feature: b0-b3 with standard errors and p-values, level change, slope change, net effect at k, R-squared |
| recovery_classes.csv | Pixels, area (ha) and percentage of each recovery class |
| pixels.csv | Optional sampled pixel coefficients with map coordinates |
| run_parameters.json | Options, resolved times, status, colour limits and output paths |
| processing.log | Status, duration and the main resolved settings |

The ITSA graph shows the mean coherence of each date (PRE, EVENT, POST), the
spatial interquartile range, the time span of each pair, the fitted PRE and POST
trends, the counterfactual (PRE trend continued), the interruption, and the net
effect at k; the level change, trend change, p-values and R-squared are printed
under the graph. The map colour scale is symmetric about zero and limited to the
98th percentile of the absolute values. The histogram axis covers the central 99%
of the values and reports how many pixels lie beyond it.

CSV files are plain comma-separated tables with one header row; undefined numbers
are empty cells. Pixel CSV sampling uses the cell index modulo the configured step,
then keeps up to the row cap in block order, so it is deterministic.

## Processing and example

The provider registers `coherence_itsa:coherence_itsa` in the Processing toolbox
for batch runs and models. Supply Pre/Event/Post raster lists, a JSON observation
settings array, an analysis-options JSON object and an output parent folder.
All engine options are available through that object; the dialog exposes the
same settings. Observation settings, if nonempty, must contain one object per
raster in Pre/Event/Post order, for example
`{"date":"2022-01-01","end_date":"2022-01-13","looks":4,"band":1}`.
The default empty array reads the dates from the file names and uses L=4, band 1.
An optional study-area polygon layer can be supplied.

The `sample/` folder contains eleven 5x4 synthetic GeoTIFFs, under 1 MB total.
Use **Add folder...** on it: `00_pre` through `04_pre` are recognised as PRE,
`05_event` as EVENT and `06_post` through `10_post` as POST. They carry no dates,
so the order index is used. Valid pixels
have b2=-0.2, b3=0.035, pre trend=-0.01, post trend=0.025 and net effect=-0.025
at k=10, with T0=5. The upper-left pixel is nodata. Noise-free examples illustrate
coefficient recovery; their inferential outputs are not realistic uncertainty.

## Development and verification

Run `python -B -m unittest discover -s tests -v` in the QGIS Python environment.
Tests cover known coefficients, missingness, event inclusion, classical and
Newey-West covariance, correction lookup, grid rejection/resampling, raster
metadata, AOI/feature series, deterministic exports and cancellation.
`tools/verify_qgis.py` checks provider registration, a Processing run, the dialog
workflow (optionally on a real raster folder and AOI), styled project loading and
provider cleanup using an offscreen QGIS application. `tools/run_real.py` runs the
engine on a raster folder without QGIS Desktop.
`tools/package.py` creates the ZIP from the plugin folder and checks archive
contents and size. Platform/version checks actually performed are listed in
`VERIFICATION.md`; declared compatibility is not a claim of testing every QGIS build.

Public source: https://github.com/jhonjhonbautista1234-ctrl/CoherenceBasedITSA

Issues: https://github.com/jhonjhonbautista1234-ctrl/CoherenceBasedITSA/issues
