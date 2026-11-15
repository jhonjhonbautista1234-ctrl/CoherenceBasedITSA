# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from threading import Lock

import numpy as np
from matplotlib import dates as mdates
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap, ListedColormap
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, MaxNLocator

from .products import CLASSES, DIVERGING
from .tables import effects

PLOT_LOCK = Lock()
SURFACE, INK, INK2, MUTED, GRID, AXIS = (
    "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7")
PRE, POST, LOSS, GAIN = "#2a78d6", "#eb6834", DIVERGING[1], DIVERGING[-2]


def new_figure(width, height):
    figure = Figure(figsize=(width, height), facecolor=SURFACE)
    FigureCanvasAgg(figure)
    return figure


def style_axis(axis, grid="y"):
    axis.set_facecolor(SURFACE)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(AXIS)
    axis.tick_params(colors=INK2, labelsize=9, length=3, color=AXIS)
    if grid:
        axis.grid(axis=grid, color=GRID, linewidth=0.8)
        axis.set_axisbelow(True)


def heading(figure, title, subtitle, left=0.08):
    figure.text(left, 0.965, title, fontsize=13, fontweight="bold", color=INK, va="top")
    figure.text(left, 0.915, subtitle, fontsize=9.5, color=INK2, va="top")


def signed(value, digits=3):
    return "n/a" if not np.isfinite(value) else f"{value:+.{digits}f}"


def p_text(value):
    if not np.isfinite(value):
        return ""
    return " (p < 0.001)" if value < 0.001 else f" (p = {value:.3f})"


def series_graph(path, scope, series, q25, q75, fit, timeline, options, pixels):
    """Observed regional coherence with the fitted segments and the counterfactual."""
    times, phases, t0, k = timeline.times, timeline.phases, timeline.t0, timeline.k
    dated = timeline.mode == "dates"
    shift = mdates.date2num(timeline.origin) if dated else 0.0
    b = fit.beta[:, 0]
    fitted = bool(np.isfinite(b).all())
    pre_line = lambda t: b[0] + b[1] * t
    post_line = lambda t: b[0] + b[1] * t + b[2] + b[3] * (t - t0)
    with PLOT_LOCK:
        figure = new_figure(10, 6.2)
        axis = figure.add_axes([0.08, 0.30, 0.78, 0.53])
        style_axis(axis)
        # Spatial spread and, for interferometric pairs, the time span of each observation.
        axis.vlines(times + shift, q25, q75, color=GRID, linewidth=5, zorder=2)
        if dated and np.any(timeline.ends > timeline.starts):
            axis.hlines(series, timeline.starts + shift, timeline.ends + shift,
                        color=MUTED, linewidth=1, zorder=2)
        if fitted:
            first, last = times[phases == "pre"].min(), times.max()
            span = np.array([t0, last])
            axis.fill_between(span + shift, pre_line(span), post_line(span),
                              color=POST, alpha=0.10, linewidth=0, zorder=1)
            axis.plot(np.array([first, t0]) + shift, pre_line(np.array([first, t0])),
                      color=PRE, linewidth=2, zorder=3)
            axis.plot(span + shift, pre_line(span), color=MUTED, linewidth=1.6,
                      linestyle=(0, (5, 3)), zorder=3)
            axis.plot(span + shift, post_line(span), color=POST, linewidth=2, zorder=3)
        axis.axvline(t0 + shift, color=INK, linewidth=1, linestyle=(0, (2, 2)), zorder=3)
        markers = dict(pre=("o", PRE, PRE), event=("D", SURFACE, INK2), post=("s", POST, POST))
        for phase, (marker, face, edge) in markers.items():
            chosen = phases == phase
            hollow = phase == "event" and not options.include_event
            axis.plot(times[chosen] + shift, series[chosen], marker, markersize=8,
                      markerfacecolor=SURFACE if hollow else (POST if phase == "event" else face),
                      markeredgecolor=edge if hollow else SURFACE,
                      markeredgewidth=1.6 if hollow else 1.2, zorder=4)
        low = np.nanmin(np.concatenate([q25, series]))
        high = np.nanmax(np.concatenate([q75, series]))
        if fitted:
            ends = np.array([pre_line(times.max()), post_line(times.max()), post_line(t0)])
            low, high = min(low, ends.min()), max(high, ends.max())
        pad = max(0.02, 0.18 * (high - low))
        axis.set_ylim(max(0.0, low - pad), min(1.0, high + 1.6 * pad))
        axis.set_ylabel("Coherence magnitude", color=INK2, fontsize=10)
        if dated:
            locator = mdates.AutoDateLocator(minticks=4, maxticks=9)
            axis.xaxis.set_major_locator(locator)
            axis.xaxis.set_major_formatter(
                mdates.ConciseDateFormatter(locator, show_offset=False))
            axis.set_xlabel(f"Date, {timeline.label(times.min())} to "
                            f"{timeline.label(times.max())} (pair midpoints)",
                            color=INK2, fontsize=10)
        else:
            axis.set_xlabel("Observation order", color=INK2, fontsize=10)
        top = axis.get_ylim()[1]
        axis.annotate("Interruption\n" + timeline.label(t0), (t0 + shift, top),
                      xytext=(6, -4), textcoords="offset points", va="top", fontsize=9,
                      color=INK)
        if fitted:
            result = effects(fit, timeline)
            net = result["net_effect_at_k"]
            axis.annotate("", (k + shift, post_line(k)), (k + shift, pre_line(k)),
                          arrowprops=dict(arrowstyle="->", color=INK, linewidth=1.1), zorder=5)
            axis.annotate(f"Net effect {signed(net)}",
                          (k + shift, (post_line(k) + pre_line(k)) / 2),
                          xytext=(8, 0), textcoords="offset points", ha="left", va="center",
                          fontsize=9, color=INK, fontweight="bold", annotation_clip=False)
        handles = [
            Line2D([], [], marker="o", linestyle="", color=PRE, markersize=8, label="PRE mean"),
            Line2D([], [], marker="D", linestyle="", markerfacecolor=SURFACE,
                   markeredgecolor=INK2, markeredgewidth=1.6, markersize=7,
                   label="EVENT mean" + ("" if options.include_event else " (not fitted)")),
            Line2D([], [], marker="s", linestyle="", color=POST, markersize=8, label="POST mean"),
            Line2D([], [], color=GRID, linewidth=5, label="Spatial interquartile range"),
            Line2D([], [], color=PRE, linewidth=2, label="PRE trend"),
            Line2D([], [], color=POST, linewidth=2, label="POST trend"),
            Line2D([], [], color=MUTED, linewidth=1.6, linestyle=(0, (5, 3)),
                   label="Counterfactual (PRE trend continued)"),
            Patch(facecolor=POST, alpha=0.18, label="Gap to counterfactual"),
        ]
        if not (phases == "event").any():
            handles.pop(1)
        figure.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.07, 0.09), ncol=4,
                      frameon=False, fontsize=8.5, labelcolor=INK2, columnspacing=1.6)
        heading(figure, (options.title or "Interrupted time series of SAR coherence")
                + f": {scope}",
                f"Mean coherence of {pixels:,} pixels per date, segmented regression "
                f"({'Newey-West' if options.covariance == 'newey_west' else 'OLS'}), "
                f"{int(fit.pre_count[0])} PRE and {int(fit.post_count[0])} POST observations")
        if fitted:
            unit = "day" if dated else "step"
            p = fit.p_values[:, 0]
            line = (f"Level change at interruption {signed(result['level_change'])}"
                    f"{p_text(p[2])}   |   Trend change {signed(result['slope_change'], 4)}"
                    f" per {unit}{p_text(p[3])}   |   Net effect on {timeline.label(k)} "
                    f"{signed(net)}   |   R² {fit.r_squared[0]:.2f}")
        else:
            line = "Not enough valid observations to fit the model for this region."
        figure.text(0.08, 0.04, line, fontsize=9, color=INK)
        figure.savefig(str(path), dpi=options.dpi, facecolor=SURFACE)
        figure.clear()


def histogram_graph(path, edges, counts, outside, options, timeline):
    net = options.metric == "net_effect"
    with PLOT_LOCK:
        figure = new_figure(9, 5.4)
        axis = figure.add_axes([0.09, 0.13, 0.87, 0.68])
        style_axis(axis)
        centres = (edges[:-1] + edges[1:]) / 2
        axis.bar(edges[:-1], counts, width=np.diff(edges) * 0.92, align="edge",
                 color=np.where(centres < 0, LOSS, GAIN), linewidth=0)
        axis.axvline(0, color=INK, linewidth=1)
        axis.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        axis.set_ylabel("Pixels", color=INK2, fontsize=10)
        axis.set_xlabel("Net effect at " + timeline.label(timeline.k) + " (coherence units)"
                        if net else "Trend change (coherence per time unit)",
                        color=INK2, fontsize=10)
        total = counts.sum()
        if total:
            below = counts[centres < 0].sum() / total
            median = centres[min(np.searchsorted(np.cumsum(counts), total / 2), len(centres) - 1)]
            subtitle = (f"{total + outside:,} fitted pixels; {below:.0%} below and {1 - below:.0%} above "
                        f"the PRE counterfactual; median {median:+.3f}")
            if outside:
                subtitle += f"; {outside:,} beyond the axis"
            axis.legend(handles=[Patch(color=LOSS, label="Below counterfactual"),
                                 Patch(color=GAIN, label="Above counterfactual")],
                        frameon=False, fontsize=9, labelcolor=INK2, loc="upper right")
        else:
            subtitle = "No pixels satisfy the model requirements"
        heading(figure, "Distribution of the recovery map", subtitle, left=0.09)
        figure.savefig(str(path), dpi=options.dpi, facecolor=SURFACE)
        figure.clear()


def nice_length(value):
    scale = 10 ** np.floor(np.log10(value))
    return max(step for step in (1, 2, 5, 10) if step * scale <= value) * scale


def map_figure(array, extent, outlines, metres):
    """Create a map figure cropped to the valid data, with scale bar and AOI outline."""
    rows, cols = np.flatnonzero(np.isfinite(array).any(1)), np.flatnonzero(
        np.isfinite(array).any(0))
    xmin, xmax, ymin, ymax = extent
    if rows.size:
        dx, dy = (xmax - xmin) / array.shape[1], (ymax - ymin) / array.shape[0]
        array = array[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
        xmin, xmax = xmin + cols[0] * dx, xmin + (cols[-1] + 1) * dx
        ymax, ymin = ymax - rows[0] * dy, ymax - (rows[-1] + 1) * dy
    margin = 0.04 * max(xmax - xmin, ymax - ymin)
    aspect = (ymax - ymin + 2 * margin) / (xmax - xmin + 2 * margin)
    width, map_width = 10.0, 6.4
    map_height = float(np.clip(map_width * aspect, 3.0, 11.0))
    height = map_height + 1.9
    figure = new_figure(width, height)
    axis = figure.add_axes([0.09, 0.62 / height, map_width / width, map_height / height])
    style_axis(axis, grid=None)
    axis.set_aspect("equal", adjustable="datalim")
    for ring in outlines:
        axis.plot(ring[:, 0], ring[:, 1], color=INK2, linewidth=0.45, zorder=3)
    axis.set_xlim(xmin - margin, xmax + margin)
    axis.set_ylim(ymin - margin, ymax + margin)
    plain = FuncFormatter(lambda v, _: f"{v:,.0f}" if metres else f"{v:.3f}")
    axis.xaxis.set_major_formatter(plain)
    axis.yaxis.set_major_formatter(plain)
    axis.xaxis.set_major_locator(MaxNLocator(5))
    axis.yaxis.set_major_locator(MaxNLocator(6))
    axis.tick_params(axis="y", labelrotation=90)
    for label in axis.get_yticklabels():
        label.set_va("center")
    axis.set_xlabel("Easting (m)" if metres else "Longitude", color=INK2, fontsize=9)
    axis.set_ylabel("Northing (m)" if metres else "Latitude", color=INK2, fontsize=9)
    if metres:
        length = nice_length((xmax - xmin) / 4)
        x0, y0 = xmin, ymin - margin * 0.45
        axis.plot([x0, x0 + length], [y0, y0], color=INK, linewidth=2.5,
                  solid_capstyle="butt", zorder=4)
        text = f"{length / 1000:g} km" if length >= 1000 else f"{length:g} m"
        axis.text(x0 + length + margin * 0.3, y0, text, va="center", fontsize=8.5, color=INK)
    return figure, axis, array, (xmin, xmax, ymin, ymax)


def map_heading(figure, title, subtitle):
    height = figure.get_figheight()
    figure.text(0.09, 1 - 0.35 / height, title, fontsize=13, fontweight="bold", color=INK,
                va="top")
    figure.text(0.09, 1 - 0.72 / height, subtitle, fontsize=9.5, color=INK2, va="top")


def recovery_map(path, array, extent, limit, outlines, metres, options, timeline):
    net = options.metric == "net_effect"
    with PLOT_LOCK:
        figure, axis, array, extent = map_figure(array, extent, outlines, metres)
        cmap = LinearSegmentedColormap.from_list("recovery", DIVERGING)
        cmap = cmap.with_extremes(bad=SURFACE)
        image = axis.imshow(array, extent=extent, cmap=cmap, vmin=-limit, vmax=limit,
                            interpolation="nearest", zorder=2)
        bar = figure.colorbar(image, cax=figure.add_axes([0.80, 0.28, 0.02, 0.40]),
                              extend="both")
        bar.outline.set_visible(False)
        bar.ax.tick_params(labelsize=9, colors=INK2, length=3, color=AXIS)
        bar.set_label("Coherence difference from PRE counterfactual" if net
                      else "Trend change (coherence per time unit)", color=INK2, fontsize=9)
        figure.text(0.80, 0.72, "Above (gain)", fontsize=8.5, color=INK2)
        figure.text(0.80, 0.225, "Below (loss)", fontsize=8.5, color=INK2)
        map_heading(figure, (options.title or "Coherence recovery map"),
                (f"Net effect on {timeline.label(timeline.k)}: fitted coherence minus the "
                 f"continued PRE trend; interruption {timeline.label(timeline.t0)}") if net
                else f"Change in coherence trend after {timeline.label(timeline.t0)}")
        figure.savefig(str(path), dpi=options.dpi, facecolor=SURFACE)
        figure.clear()


def class_map(path, array, extent, counts, outlines, metres, options, timeline):
    total = counts[1:].sum()
    with PLOT_LOCK:
        figure, axis, array, extent = map_figure(array, extent, outlines, metres)
        cmap = ListedColormap([colour for *_, colour in CLASSES])
        cmap = cmap.with_extremes(bad=SURFACE)
        axis.imshow(array, extent=extent, cmap=cmap, interpolation="nearest", zorder=2,
                    norm=BoundaryNorm(np.arange(0.5, len(CLASSES) + 1), cmap.N))
        handles = [Patch(color=colour, label=f"{label}\n{counts[code] / total:.1%} of fitted area"
                         if total else label) for code, _, label, colour in CLASSES]
        figure.legend(handles=handles, loc="center left", bbox_to_anchor=(0.755, 0.5),
                      frameon=False, fontsize=8.5, labelcolor=INK2, labelspacing=1.3,
                      handlelength=1.2, handleheight=1.2)
        map_heading(figure, (options.title or "Coherence recovery classes"),
                f"Level change at {timeline.label(timeline.t0)} and net effect on "
                f"{timeline.label(timeline.k)}, tolerance ±{options.class_tolerance:g}")
        figure.savefig(str(path), dpi=options.dpi, facecolor=SURFACE)
        figure.clear()
