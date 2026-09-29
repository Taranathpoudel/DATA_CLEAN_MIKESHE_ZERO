# -*- coding: utf-8 -*-
"""
plotting.py

Diagnostic and result visualisations for the Kriging pipeline:
- elevation-rainfall drift scatter (with residuals)
- experimental variogram + fitted model curve
- kriged surface map
- leave-one-out cross-validation scatter
"""

import numpy as np
import matplotlib.pyplot as plt

from variogram import MODELS


###############################################################################
# Elevation-rainfall drift diagnostic
###############################################################################

def plot_drift(elevation, values, fit, title=None, ax=None):
    """
    Scatter of station values vs. elevation, with the fitted OLS drift
    line, and each station's residual drawn as a vertical segment
    (the "residual points" used to build the variogram).

    `fit` is the dict returned by climatology.fit_daily_drift.
    """

    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(figsize=(6, 5))

    common = elevation.index.intersection(values.index)
    z = elevation.reindex(common)
    v = values.reindex(common)
    ok = v.notna() & z.notna()
    z, v = z[ok].to_numpy(dtype=float), v[ok].to_numpy(dtype=float)

    pred = fit["a"] + fit["b"] * z

    order = np.argsort(z)
    ax.plot(z[order], pred[order], color="crimson", lw=2, label="OLS drift")

    # residual segments
    for zi, vi, pi in zip(z, v, pred):
        ax.plot([zi, zi], [pi, vi], color="grey", lw=0.8, alpha=0.6, zorder=1)

    ax.scatter(z, v, s=28, color="steelblue", edgecolor="white", zorder=2, label="stations")

    ax.set_xlabel("Elevation (m)")
    ax.set_ylabel("Rainfall (mm)")
    ax.set_title(title or f"Elevation-rainfall drift  (r = {fit['r']:.2f}, n = {fit['n']})")
    ax.legend(frameon=False)
    ax.grid(alpha=0.3)

    if own_fig:
        fig.tight_layout()
        return fig
    return ax


###############################################################################
# Variogram plot
###############################################################################

def plot_variogram(variogram_result, title=None, ax=None):
    """
    Experimental variogram points (size scaled by pair count) + fitted
    theoretical model curve, with nugget/sill/range annotated.

    `variogram_result` is a dict as returned by
    climatology.pooled_residual_variogram / pooled_raw_variogram
    (must contain lag_centers, gamma, counts, best_fit).
    """

    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(figsize=(6.5, 5))

    lag = variogram_result["lag_centers"]
    gamma = variogram_result["gamma"]
    counts = variogram_result["counts"]
    fit = variogram_result["best_fit"]

    ok = np.isfinite(lag) & np.isfinite(gamma)
    sizes = 20 + 180 * (counts[ok] / counts[ok].max())

    ax.scatter(lag[ok] / 1000, gamma[ok], s=sizes, color="darkorange",
               edgecolor="black", linewidth=0.5, zorder=3,
               label="experimental (pair count ∝ size)")

    h = np.linspace(0, lag[ok].max() * 1.05, 300)
    model_func = MODELS[fit["model"]]
    curve = model_func(h, fit["nugget"], fit["sill"], fit["range"])
    ax.plot(h / 1000, curve, color="navy", lw=2,
            label=f"{fit['model']} model")

    ax.axhline(fit["sill"], color="grey", ls="--", lw=1)
    ax.axvline(fit["range"] / 1000, color="grey", ls="--", lw=1)
    ax.text(fit["range"] / 1000, fit["sill"] * 1.02,
            f"  range={fit['range']/1000:.1f} km\n  sill={fit['sill']:.1f}\n  nugget={fit['nugget']:.1f}",
            va="bottom", fontsize=9)

    ax.set_xlabel("Lag distance (km)")
    ax.set_ylabel("Semivariance")
    ax.set_title(title or "Climatological variogram")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(alpha=0.3)

    if own_fig:
        fig.tight_layout()
        return fig
    return ax


###############################################################################
# Kriged surface map
###############################################################################

def plot_kriged_surface(xx, yy, zhat, stations_x=None, stations_y=None,
                         stations_v=None, title=None, ax=None, cmap="YlGnBu"): #"Blues"

    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(figsize=(7, 7))

    zplot = np.ma.masked_invalid(zhat)
    im = ax.pcolormesh(xx, yy, zplot, shading="auto", cmap=cmap)
    cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Rainfall (mm)")

    if stations_x is not None:
        ax.scatter(stations_x, stations_y, c=stations_v, cmap=cmap,
                   edgecolor="black", linewidth=0.8, s=45, zorder=3)

    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.set_aspect("equal")
    ax.set_title(title or "Kriged rainfall surface")

    if own_fig:
        fig.tight_layout()
        return fig
    return ax


###############################################################################
# Cross-validation scatter
###############################################################################

def plot_cross_validation(cv_result, title=None, ax=None):

    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(figsize=(5.5, 5.5))

    obs = cv_result["observed"]
    pred = cv_result["predicted"]

    lo = min(obs.min(), pred.min())
    hi = max(obs.max(), pred.max())
    ax.plot([lo, hi], [lo, hi], color="grey", ls="--", lw=1, label="1:1")

    ax.scatter(obs, pred, s=35, color="seagreen", edgecolor="white")

    ax.set_xlabel("Observed (mm)")
    ax.set_ylabel("Predicted, leave-one-out (mm)")
    ax.set_title(title or (
        f"Cross-validation  RMSE={cv_result['rmse']:.2f}  "
        f"MAE={cv_result['mae']:.2f}  bias={cv_result['bias']:.2f}"))
    ax.legend(frameon=False)
    ax.grid(alpha=0.3)
    ax.set_aspect("equal")

    if own_fig:
        fig.tight_layout()
        return fig
    return ax
