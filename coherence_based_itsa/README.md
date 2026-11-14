# Coherence Based ITSA

Per-pixel interrupted time series analysis of SAR coherence magnitudes for QGIS 3.22 and later.

Copyright (C) 2026 Allen John T. Bautista. This software is licensed under
GPL-2.0-or-later: GNU GPL version 2 or, at your option, any later version.

## Install

In QGIS, open **Plugins > Manage and Install Plugins > Install from ZIP** and
select `coherence_based_itsa-1.0.0.zip`. Enable **Coherence Based ITSA** and open
**Raster > Coherence Based ITSA**. The official Plugin Manager search will list
the plugin after its submission to, and approval by, the QGIS repository.

Requires NumPy, SciPy, GDAL/OGR and matplotlib in the QGIS Python environment.
No packages are installed by the plugin. No network connection is used during analysis.
If an import fails, repair the QGIS distribution rather than installing into a
different Python environment. Windows, Linux and macOS use the same source.

## Inputs and workflow

Add disk rasters or project raster layers to Pre, Event-straddling and Post.
Each row has an editable path, optional acquisition date, independent looks L,
and 1-based band number. Select a row to move it up/down or remove it.
At least two valid observations in each fitted segment are required.
Event-straddling inputs are optional and excluded from regression by default;
enable their inclusion to assign all of them to the Post segment.

Index mode uses zero-based indices across Pre, Event, Post, in table order.
Leave all dates blank. Date mode requires all dates in `YYYY-MM-DD` format,
strictly increasing in the table order. Time is elapsed days from the earliest
acquisition. Mixed dated/undated observations are rejected. Duplicate raster-band
inputs are rejected. Acquisition dates describe the supplied observation times;
coherence itself spans image pairs and is not an instantaneous measurement.

Select an output parent folder and click Run. Work runs in a cancellable QGIS
task. Each run creates a new UTC-named subfolder; earlier runs are not replaced.
Rasters and CSV tables load into a project group, and a results window shows
the PNG graphs. Cancel stops at the next block or output operation. Incomplete
outputs are retained with failed/cancelled status in `run_parameters.json` and
are not loaded as completed results.

Inputs must be real coherence magnitudes in [0,1]. Declared nodata, raster masks,
NaN and infinite values are missing. GDAL scale/offset metadata is applied.
Zero is valid unless masked or removed by the optional threshold. Values
outside [0,1] cause an error before resampling or analysis. There is no temporal
interpolation. Source values are validated in blocks before analysis.

CRS, dimensions and all six grid-transform values must match. Otherwise the
run stops. Explicit resampling uses the first Pre raster as reference and the
selected nearest, bilinear, cubic or average method; a north-up reference is
required for this option. Cubic interpolation can overshoot [0,1]; such values
are rejected. Resampling changes spatial support and should be deliberate.

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
an increasing absolute post trend. Outputs are not recovery percentages or
classifications and do not establish physical reconstruction or ecological recovery.

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

Leave the AOI path blank to use the full grid. Otherwise supply a polygon vector
file. Geometries are transformed to the raster CRS, and the default mask uses
pixel centers; all-touched inclusion is optional. Input rasters are never cropped.

Supply a point/polygon vector file for optional per-feature series, or choose a
project layer and optionally its selected features. Project features are saved
as a GeoPackage snapshot under the output parent before background execution.
Feature identifiers use layer name and feature ID. Multi-layer vector files are
supported. Points use their containing grid cells. Overlapping polygons are
summarized independently. Each feature is intersected with the AOI.

Graphs and coefficients for the AOI/features use arithmetic means of the valid
pixels at each observation. Counts are exported, and spatial membership can
change between dates. These descriptive aggregate fits are separate from the
pixel fits and are not averages of pixel coefficients. Empty features retain
undefined series and coefficients. Large feature collections can be slow.

## Outputs

All rasters are tiled, compressed float32 GeoTIFFs on the reference grid and CRS
with configurable negative nodata, default -9999. A collision with a computed
value stops the run so another nodata value can be chosen.

| File | Content |
| --- | --- |
| recovery.tif | Selected net effect at k or slope change |
| level_change.tif, slope_change.tif | b2, b3 |
| pre_trend.tif, post_trend.tif | b1, b1+b3 |
| r_squared.tif | R-squared |
| valid_count.tif, pre_count.tif, post_count.tif | Fitted observation counts |
| level_se.tif, slope_se.tif | Standard errors of b2, b3 |
| level_p.tif, slope_p.tif | Two-sided p-values of b2, b3 |
| residual_lag1.tif | Lag-1 residual autocorrelation |
| series.csv | AOI/feature means, counts, fitted values, counterfactual and residuals |
| coefficients.csv | Aggregate b0-b3, standard errors, p-values and fit diagnostics |
| pixels.csv | Optional sampled pixel coefficients and diagnostics |
| series_0000.png, series_0001.png, ... | AOI, then feature series and fitted segments |
| recovery_histogram.png | Full valid-map histogram, without random sampling |
| run_parameters.json | Options, resolved times, status, output paths and histogram edges |
| processing.log | Chosen correction and covariance modes |

CSV files start with a `#` metadata line including bias-correction mode; skip
that line in other CSV readers. Undefined CSV numbers are `nan`. Pixel CSV
sampling uses global zero-based cell index modulo the configured step, then
keeps up to the row cap in block traversal order. It is deterministic for the
same options. CSV row caps affect CSV only, not raster fits or the histogram.

## Processing and example

The provider registers `coherence_itsa:coherence_itsa` in the Processing toolbox
for batch runs and models. Supply Pre/Event/Post raster lists, a JSON observation
settings array, an analysis-options JSON object and an output parent folder.
All engine options are available through that object; the dialog exposes the
same settings. Observation settings, if nonempty, must contain one object per
raster in Pre/Event/Post order, for example `{"date":"2022-01-01","looks":4,"band":1}`.
The default empty array uses blank dates, L=4 and band 1.

The `sample/` folder contains eleven 5x4 synthetic GeoTIFFs, under 1 MB total.
Add `00_pre` through `04_pre` to Pre, `05_event` to Event, and `06_post` through
`10_post` to Post. Use index mode with defaults and no correction. Valid pixels
have b2=-0.2, b3=0.035, pre trend=-0.01, post trend=0.025 and net effect=-0.025
at k=10, with T0=5. The upper-left pixel is nodata. Noise-free examples illustrate
coefficient recovery; their inferential outputs are not realistic uncertainty.

## Development and verification

Run `python -B -m unittest discover -s tests -v` in the QGIS Python environment.
Tests cover known coefficients, missingness, event inclusion, classical and
Newey-West covariance, correction lookup, grid rejection/resampling, raster
metadata, AOI/feature series, deterministic exports and cancellation.
`tools/verify_qgis.py` checks the dialog, provider registration, Processing run,
project output loading and provider cleanup using an offscreen QGIS application.
`tools/package.py` creates the ZIP from the plugin folder and checks archive
contents and size. Platform/version checks actually performed are listed in
`VERIFICATION.md`; declared compatibility is not a claim of testing every QGIS build.

Public source: https://github.com/jhonjhonbautista1234-ctrl/CoherenceBasedITSA

Issues: https://github.com/jhonjhonbautista1234-ctrl/CoherenceBasedITSA/issues
