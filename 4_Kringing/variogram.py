# -*- coding: utf-8 -*-
"""
variogram.py

Experimental + theoretical variogram tools, implemented in pure
numpy (no scipy/pykrige/gstools dependency required).

Provides
--------
- experimental_variogram : classic (Matheron) or robust (Cressie-Hawkins)
  binned semivariance from a point cloud of values.
- spherical / exponential / gaussian : theoretical variogram models.
- fit_variogram_model : grid-search + linear least squares fit of a single
  model (nugget, partial sill, range).
- fit_best_variogram : fits spherical and exponential and returns whichever
  fits better, with a bias toward spherical (the project default) unless
  exponential is meaningfully better.
"""

import numpy as np


###############################################################################
# Distances
###############################################################################

def pairwise_distances(x, y):
    """
    Pairwise Euclidean distance matrix for a set of points.

    Parameters
    ----------
    x, y : 1D arrays of projected coordinates (metres), same length.

    Returns
    -------
    (n, n) distance matrix.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    return np.sqrt(dx ** 2 + dy ** 2)


###############################################################################
# Experimental variogram
###############################################################################

def experimental_variogram(
        x, y, values,
        n_lags=12,
        max_lag=None,
        estimator="matheron"):
    """
    Binned experimental (semi)variogram from scattered point data.

    Parameters
    ----------
    x, y : arrays of projected coordinates (metres)
    values : array of the variable to compute the variogram of
        (rainfall, or elevation-drift residuals)
    n_lags : number of distance bins
    max_lag : maximum separation distance to consider (metres).
        Defaults to 2/3 of the maximum pairwise distance.
    estimator : "matheron" (classic) or "cressie" (robust to outliers)

    Returns
    -------
    dict with keys: lag_centers, gamma, counts (all length n_lags,
    NaN/0 for empty bins)
    """

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    v = np.asarray(values, dtype=float)

    ok = np.isfinite(v)
    x, y, v = x[ok], y[ok], v[ok]
    n = len(v)

    if n < 2:
        raise ValueError("Need at least 2 valid points to build a variogram.")

    dist = pairwise_distances(x, y)
    diff = v[:, None] - v[None, :]

    iu = np.triu_indices(n, k=1)
    d = dist[iu]
    dv = diff[iu]

    if max_lag is None:
        max_lag = d.max() * (2.0 / 3.0)

    bin_edges = np.linspace(0, max_lag, n_lags + 1)
    bin_idx = np.digitize(d, bin_edges) - 1

    lag_centers = np.full(n_lags, np.nan)
    gamma = np.full(n_lags, np.nan)
    counts = np.zeros(n_lags, dtype=int)

    for b in range(n_lags):
        sel = bin_idx == b
        m = sel.sum()
        counts[b] = m
        if m == 0:
            continue

        lag_centers[b] = d[sel].mean()

        if estimator == "matheron":
            gamma[b] = 0.5 * np.mean(dv[sel] ** 2)

        elif estimator == "cressie":
            # Cressie-Hawkins robust estimator
            root_abs = np.mean(np.sqrt(np.abs(dv[sel])))
            gamma[b] = 0.5 * (root_abs ** 4) / (0.457 + 0.494 / m)

        else:
            raise ValueError("estimator must be 'matheron' or 'cressie'")

    return {
        "lag_centers": lag_centers,
        "gamma": gamma,
        "counts": counts,
        "bin_edges": bin_edges,
    }


###############################################################################
# Theoretical models
###############################################################################

def spherical(h, nugget, sill, range_):
    h = np.asarray(h, dtype=float)
    partial = sill - nugget
    hr = np.clip(h / range_, 0, 1)
    g = nugget + partial * (1.5 * hr - 0.5 * hr ** 3)
    g = np.where(h >= range_, sill, g)
    g = np.where(h <= 0, 0.0, g)
    return g


def exponential(h, nugget, sill, range_):
    h = np.asarray(h, dtype=float)
    partial = sill - nugget
    # "practical range" convention: model reaches ~95% of sill at `range_`
    g = nugget + partial * (1 - np.exp(-3 * h / range_))
    g = np.where(h <= 0, 0.0, g)
    return g


def gaussian(h, nugget, sill, range_):
    h = np.asarray(h, dtype=float)
    partial = sill - nugget
    g = nugget + partial * (1 - np.exp(-3 * (h / range_) ** 2))
    g = np.where(h <= 0, 0.0, g)
    return g


MODELS = {
    "spherical": spherical,
    "exponential": exponential,
    "gaussian": gaussian,
}


###############################################################################
# Fitting (grid search over range + weighted linear least squares
# for nugget/partial-sill -- avoids needing scipy.optimize)
###############################################################################

def _shape_function(model_name, h, range_):
    """Model value for nugget=0, sill=1 (i.e. the pure shape term)."""
    return MODELS[model_name](h, 0.0, 1.0, range_)


def fit_variogram_model(
        lag_centers, gamma, counts,
        model="spherical",
        n_range_candidates=60):
    """
    Fit a theoretical variogram model (nugget, sill, range) to a binned
    experimental variogram using a range grid-search with a weighted
    linear least-squares solve for (nugget, partial_sill) at each
    candidate range -- fully in numpy, no scipy required.

    Bins are weighted by their pair count (more pairs = more reliable).

    Returns
    -------
    dict with keys: model, nugget, sill, range, rmse (weighted)
    """

    ok = np.isfinite(lag_centers) & np.isfinite(gamma) & (counts > 0)
    h = lag_centers[ok]
    g = gamma[ok]
    w = counts[ok].astype(float)

    if len(h) < 3:
        raise ValueError("Not enough populated lag bins to fit a variogram.")

    max_h = h.max()
    range_candidates = np.linspace(max_h * 0.1, max_h * 1.5, n_range_candidates)

    best = None

    for r in range_candidates:
        shape = _shape_function(model, h, r)

        # Design matrix for g ~ nugget * 1 + partial_sill * shape
        X = np.column_stack([np.ones_like(shape), shape])

        # Weighted least squares: (X'WX) beta = X'Wg
        XtW = X.T * w
        try:
            beta = np.linalg.solve(XtW @ X, XtW @ g)
        except np.linalg.LinAlgError:
            continue

        nugget, partial_sill = beta
        # Enforce physical constraints
        nugget = max(nugget, 0.0)
        partial_sill = max(partial_sill, 1e-9)
        sill = nugget + partial_sill

        pred = nugget + partial_sill * shape
        resid = g - pred
        wsse = np.sum(w * resid ** 2)

        if best is None or wsse < best["wsse"]:
            best = {
                "model": model,
                "nugget": float(nugget),
                "sill": float(sill),
                "range": float(r),
                "wsse": float(wsse),
            }

    rmse = np.sqrt(best["wsse"] / np.sum(w))
    best["rmse"] = float(rmse)
    del best["wsse"]
    return best


def fit_best_variogram(
        lag_centers, gamma, counts,
        candidate_models=("spherical", "exponential"),
        spherical_bias=0.05):
    """
    Fit each candidate model and return the best one.

    `spherical_bias`: fraction by which a non-spherical model's RMSE must
    be lower than spherical's before it is preferred (keeps spherical as
    the default choice "as much as possible" unless another model is a
    clearly better fit).
    """

    fits = {}
    for m in candidate_models:
        try:
            fits[m] = fit_variogram_model(lag_centers, gamma, counts, model=m)
        except ValueError:
            continue

    if not fits:
        raise ValueError("Could not fit any variogram model.")

    if "spherical" in fits:
        best = fits["spherical"]
        for m, fit in fits.items():
            if m == "spherical":
                continue
            if fit["rmse"] < best["rmse"] * (1 - spherical_bias):
                best = fit
        return best, fits

    best = min(fits.values(), key=lambda f: f["rmse"])
    return best, fits
