# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 Allen John T. Bautista

from threading import Lock

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

PLOT_LOCK = Lock()


def series_graph(path, name, series, fit, times, phases, fitted_post, t0, options):
    with PLOT_LOCK:
        figure = Figure(figsize=(9, 5), tight_layout=True)
        FigureCanvasAgg(figure)
        axis = figure.add_subplot(111)
        for phase, marker in (("pre", "o"), ("event", "D"), ("post", "s")):
            selected = phases == phase
            axis.plot(times[selected], series[selected], marker, label=phase.capitalize())
        beta = fit.beta[:, 0]
        for selected, label, is_post in ((phases == "pre", "Pre fit", False),
                                          (fitted_post, "Post fit", True)):
            t = np.array([times[selected].min(), times[selected].max()])
            y = beta[0] + beta[1] * t
            if is_post:
                y += beta[2] + beta[3] * (t - t0)
            axis.plot(t, y, label=label)
        axis.plot(times, beta[0] + beta[1] * times, "--", label="Pre counterfactual")
        axis.axvline(t0, color="black", linestyle=":", label="Interruption")
        time_label = ("Days from first acquisition"
                      if options.time_mode == "dates" else "Order index")
        axis.set(title=name + " mean coherence",
                 ylabel="Coherence magnitude", xlabel=time_label)
        axis.legend(fontsize=8)
        axis.grid(alpha=0.2)
        figure.savefig(str(path), dpi=options.dpi)
        figure.clear()


def histogram_graph(path, edges, counts, options):
    with PLOT_LOCK:
        figure = Figure(figsize=(8, 5), tight_layout=True)
        FigureCanvasAgg(figure)
        axis = figure.add_subplot(111)
        axis.bar(edges[:-1], counts, width=np.diff(edges), align="edge")
        axis.set(title="Coherence recovery map distribution", ylabel="Pixels",
                 xlabel="Net effect (coherence units)" if options.metric == "net_effect"
                 else "Slope change (coherence per time unit)")
        if not counts.sum():
            axis.text(0.5, 0.5, "No pixels satisfy the model requirements",
                      transform=axis.transAxes, ha="center")
        figure.savefig(str(path), dpi=options.dpi)
        figure.clear()
