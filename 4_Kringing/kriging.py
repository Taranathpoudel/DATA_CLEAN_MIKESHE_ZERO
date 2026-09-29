# -*- coding: utf-8 -*-
"""
kriging.py

Ordinary Kriging (OK) and Kriging with an External Drift (KED, using
elevation) solvers, implemented directly with numpy.linalg (no
pykrige/gstools dependency).

Both solvers build the kriging system matrix once (it only depends on
the known-point configuration and the variogram model) and then solve
for ALL prediction locations in a single batched linear solve
(np.linalg.solve broadcasts over stacked right-hand-side vectors),
which is what makes predicting over a full DEM grid fast in pure numpy.
"""

import numpy as np

from variogram import MODELS


def _model_func(model_name, nugget, sill, range_):
    base = MODELS[model_name]
    return lambda h: base(h, nugget, sill, range_)


###############################################################################
# Ordinary Kriging
###############################################################################

def ordinary_kriging_predict(
        x, y, values,
        x_pred, y_pred,
        variogram_fit):
    """
    Ordinary Kriging at many prediction points at once.

    Parameters
    ----------
    x, y, values : known-point coordinates (m) and observed values
    x_pred, y_pred : 1D arrays of prediction-point coordinates (m)
    variogram_fit : dict with keys model/nugget/sill/range
        (as returned by variogram.fit_variogram_model / fit_best_variogram)

    Returns
    -------
    zhat, variance : arrays same shape as x_pred
    """

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    v = np.asarray(values, dtype=float)
    n = len(v)

    gamma = _model_func(variogram_fit["model"], variogram_fit["nugget"],
                         variogram_fit["sill"], variogram_fit["range"])

    # System matrix (n+1) x (n+1)
    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx ** 2 + dy ** 2)

    A = np.ones((n + 1, n + 1))
    A[:n, :n] = gamma(d)
    A[n, n] = 0.0
    np.fill_diagonal(A[:n, :n], 0.0)

    # RHS for every prediction point at once: (n+1) x m
    xp = np.asarray(x_pred, dtype=float).ravel()
    yp = np.asarray(y_pred, dtype=float).ravel()
    dxp = x[:, None] - xp[None, :]
    dyp = y[:, None] - yp[None, :]
    dp = np.sqrt(dxp ** 2 + dyp ** 2)

    m = len(xp)
    B = np.ones((n + 1, m))
    B[:n, :] = gamma(dp)

    W = np.linalg.solve(A, B)  # (n+1) x m

    weights = W[:n, :]
    mu = W[n, :]

    zhat = weights.T @ v
    variance = np.sum(weights * B[:n, :], axis=0) + mu

    shape = np.asarray(x_pred).shape
    return zhat.reshape(shape), variance.reshape(shape)


###############################################################################
# Kriging with External Drift (elevation)
###############################################################################

def external_drift_kriging_predict(
        x, y, values, elevation,
        x_pred, y_pred, elevation_pred,
        variogram_fit):
    """
    Kriging with External Drift: elevation enters as a second
    unbiasedness constraint alongside the usual weights-sum-to-one
    constraint (universal-kriging-style system), using a variogram
    already fit to elevation-drift residuals (see climatology.py).

    Parameters
    ----------
    x, y, values, elevation : known stations
    x_pred, y_pred, elevation_pred : prediction locations + elevation
        there (same shape, elevation_pred typically comes from a DEM)
    variogram_fit : dict with keys model/nugget/sill/range (fit to
        the elevation-drift residuals)

    Returns
    -------
    zhat, variance : arrays same shape as x_pred
    """

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    v = np.asarray(values, dtype=float)
    z = np.asarray(elevation, dtype=float)
    n = len(v)

    gamma = _model_func(variogram_fit["model"], variogram_fit["nugget"],
                         variogram_fit["sill"], variogram_fit["range"])

    dx = x[:, None] - x[None, :]
    dy = y[:, None] - y[None, :]
    d = np.sqrt(dx ** 2 + dy ** 2)

    k = n + 2  # + constant constraint + elevation-drift constraint
    A = np.zeros((k, k))
    A[:n, :n] = gamma(d)
    np.fill_diagonal(A[:n, :n], 0.0)
    A[:n, n] = 1.0
    A[n, :n] = 1.0
    A[:n, n + 1] = z
    A[n + 1, :n] = z
    # bottom-right 2x2 block stays zero

    xp = np.asarray(x_pred, dtype=float).ravel()
    yp = np.asarray(y_pred, dtype=float).ravel()
    zp = np.asarray(elevation_pred, dtype=float).ravel()

    dxp = x[:, None] - xp[None, :]
    dyp = y[:, None] - yp[None, :]
    dp = np.sqrt(dxp ** 2 + dyp ** 2)

    m = len(xp)
    B = np.zeros((k, m))
    B[:n, :] = gamma(dp)
    B[n, :] = 1.0
    B[n + 1, :] = zp

    W = np.linalg.solve(A, B)

    weights = W[:n, :]
    mu0 = W[n, :]
    mu1 = W[n + 1, :]

    zhat = weights.T @ v
    variance = np.sum(weights * B[:n, :], axis=0) + mu0 + mu1 * zp

    shape = np.asarray(x_pred).shape
    return zhat.reshape(shape), variance.reshape(shape)


###############################################################################
# Leave-one-out cross-validation
###############################################################################

def leave_one_out_cv(
        x, y, values, elevation,
        variogram_fit,
        method="ked"):
    """
    Leave-one-out cross-validation at the station locations.

    Parameters
    ----------
    method : "ked" or "ok"

    Returns
    -------
    dict: observed, predicted, rmse, mae, bias
    """

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    v = np.asarray(values, dtype=float)
    z = np.asarray(elevation, dtype=float)
    n = len(v)

    pred = np.full(n, np.nan)

    for i in range(n):
        keep = np.arange(n) != i
        if method == "ked":
            zhat, _ = external_drift_kriging_predict(
                x[keep], y[keep], v[keep], z[keep],
                np.array([x[i]]), np.array([y[i]]), np.array([z[i]]),
                variogram_fit)
        elif method == "ok":
            zhat, _ = ordinary_kriging_predict(
                x[keep], y[keep], v[keep],
                np.array([x[i]]), np.array([y[i]]),
                variogram_fit)
        else:
            raise ValueError("method must be 'ked' or 'ok'")
        pred[i] = zhat[0]

    err = pred - v
    return {
        "observed": v,
        "predicted": pred,
        "rmse": float(np.sqrt(np.nanmean(err ** 2))),
        "mae": float(np.nanmean(np.abs(err))),
        "bias": float(np.nanmean(err)),
    }
