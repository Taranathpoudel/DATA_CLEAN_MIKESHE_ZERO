# -*- coding: utf-8 -*-
"""
climatology.py

Elevation-drift fitting and the day-of-year "climatological" variogram:
pools drift residuals from a +/- window_days window around a target
calendar day, across ALL available years, into one experimental
variogram. This gives far more pairs than a single day's ~36 stations
can provide, while still tracking the seasonal (e.g. monsoon vs. dry
season) change in spatial correlation structure, since the window is
centred on the calendar day, not fixed across the year.

Workflow per target date
-------------------------
1. For every date within the window, fit rainfall ~ a + b * elevation
   (OLS across reporting stations) and take the residuals.
2. Pool all residual pairs (within each day only -- pairs are never
   formed across different days) across the whole window into shared
   distance bins.
3. Fit a theoretical variogram model (variogram.fit_best_variogram) to
   the pooled bins.
4. Separately, fit the drift for the target date itself -- this is what
   actually gets used as the external drift / detrended field for
   kriging that day, and its correlation strength decides whether
   Kriging with External Drift is justified or Ordinary Kriging should
   be used instead.
"""

import numpy as np
import pandas as pd

from variogram import pairwise_distances, fit_best_variogram


###############################################################################
# Elevation drift for a single day
###############################################################################

def fit_daily_drift(values, elevation, min_stations=4):
    """
    OLS fit of `values ~ a + b * elevation` across stations reporting a
    non-null value on this day.

    Parameters
    ----------
    values : pandas Series indexed by station
    elevation : pandas Series indexed by station (same index universe)
    min_stations : minimum number of reporting stations required to fit

    Returns
    -------
    dict with keys: a, b, r, n, residuals (Series aligned to `values`
    index, NaN where not fitted/not reporting), or None if too few
    stations reported.
    """

    common = values.index.intersection(elevation.index)
    v = values.reindex(common)
    z = elevation.reindex(common)

    ok = v.notna() & z.notna()
    n = int(ok.sum())

    if n < min_stations:
        return None

    vv = v[ok].to_numpy(dtype=float)
    zz = z[ok].to_numpy(dtype=float)

    X = np.column_stack([np.ones(n), zz])
    beta, *_ = np.linalg.lstsq(X, vv, rcond=None)
    a, b = beta

    pred = a + b * zz
    resid_ok = vv - pred

    if np.std(vv) > 0 and np.std(pred) > 0:
        r = float(np.corrcoef(vv, pred)[0, 1])
    else:
        r = 0.0

    residuals = pd.Series(np.nan, index=values.index)
    residuals.loc[ok.index[ok]] = resid_ok

    return {"a": float(a), "b": float(b), "r": r, "n": n, "residuals": residuals}


def drift_is_significant(fit, r_threshold=0.3, min_stations=8):
    """
    Simple, dependency-free heuristic for whether the elevation drift is
    worth using for a given day: minimum reporting stations + minimum
    correlation strength. (A formal t-test on r would need scipy.stats;
    this threshold rule is the pragmatic substitute.)
    """
    if fit is None:
        return False
    return (fit["n"] >= min_stations) and (abs(fit["r"]) >= r_threshold)


###############################################################################
# Moving window over calendar day-of-year
###############################################################################

def _calendar_doy(dates):
    """Day-of-year on a fixed non-leap reference year (Feb 29 -> Feb 28),
    so the window is purely about month/day, not tied to leap years."""
    ref = []
    for m, d in zip(dates.month, dates.day):
        if m == 2 and d == 29:
            d = 28
        ref.append(pd.Timestamp(year=2001, month=m, day=d).dayofyear)
    return np.array(ref)


def moving_window_mask(dates, target_date, window_days=7):
    """
    Boolean mask selecting all dates within +/- window_days of
    target_date's calendar day (month/day), across all years, with
    circular wraparound at the Dec/Jan boundary.
    """
    dates = pd.DatetimeIndex(dates)
    doy = _calendar_doy(dates)
    target_doy = _calendar_doy(pd.DatetimeIndex([target_date]))[0]

    diff = np.abs(doy - target_doy)
    circ = np.minimum(diff, 366 - diff)

    return circ <= window_days


###############################################################################
# Pooled residual variogram over the moving window
###############################################################################

def pooled_residual_variogram(
        rain_df, elevation, coords_x, coords_y,
        target_date,
        window_days=7,
        n_lags=12,
        max_lag=None,
        estimator="matheron",
        min_stations_per_day=4):
    """
    Build the climatological experimental variogram of elevation-drift
    residuals, pooled over a +/- window_days window of the target
    calendar day across all years present in rain_df.

    Returns
    -------
    dict: lag_centers, gamma, counts, n_days_used, best_fit, all_fits
    """

    mask = moving_window_mask(rain_df.index, target_date, window_days)
    window_dates = rain_df.index[mask]

    if max_lag is None:
        d = pairwise_distances(coords_x.to_numpy(), coords_y.to_numpy())
        max_lag = d.max() * (2.0 / 3.0)

    bin_edges = np.linspace(0, max_lag, n_lags + 1)

    sum_stat = np.zeros(n_lags)
    sum_dist = np.zeros(n_lags)
    count = np.zeros(n_lags, dtype=int)
    n_days_used = 0

    for date in window_dates:
        fit = fit_daily_drift(rain_df.loc[date], elevation, min_stations=min_stations_per_day)
        if fit is None:
            continue

        resid = fit["residuals"]
        ok = resid.notna()
        if ok.sum() < 2:
            continue

        x = coords_x.reindex(resid.index)[ok].to_numpy(dtype=float)
        y = coords_y.reindex(resid.index)[ok].to_numpy(dtype=float)
        r = resid[ok].to_numpy(dtype=float)

        dist = pairwise_distances(x, y)
        diff = r[:, None] - r[None, :]
        iu = np.triu_indices(len(r), k=1)
        d = dist[iu]
        dv = diff[iu]

        bin_idx = np.digitize(d, bin_edges) - 1
        n_days_used += 1

        for b in range(n_lags):
            sel = bin_idx == b
            m = sel.sum()
            if m == 0:
                continue
            count[b] += m
            sum_dist[b] += d[sel].sum()
            if estimator == "matheron":
                sum_stat[b] += np.sum(dv[sel] ** 2)
            elif estimator == "cressie":
                sum_stat[b] += np.sum(np.sqrt(np.abs(dv[sel])))
            else:
                raise ValueError("estimator must be 'matheron' or 'cressie'")

    lag_centers = np.full(n_lags, np.nan)
    gamma = np.full(n_lags, np.nan)

    populated = count > 0
    lag_centers[populated] = sum_dist[populated] / count[populated]

    if estimator == "matheron":
        gamma[populated] = sum_stat[populated] / (2 * count[populated])
    else:
        mean_root = sum_stat[populated] / count[populated]
        gamma[populated] = 0.5 * (mean_root ** 4) / (0.457 + 0.494 / count[populated])

    best_fit, all_fits = fit_best_variogram(lag_centers, gamma, count)

    return {
        "lag_centers": lag_centers,
        "gamma": gamma,
        "counts": count,
        "bin_edges": bin_edges,
        "n_days_used": n_days_used,
        "best_fit": best_fit,
        "all_fits": all_fits,
    }


###############################################################################
# Pooled variogram of raw rainfall (no elevation drift) -- used for the
# Ordinary Kriging fallback on days/seasons where the elevation drift
# isn't significant.
###############################################################################

def pooled_raw_variogram(
        rain_df, coords_x, coords_y,
        target_date,
        window_days=7,
        n_lags=12,
        max_lag=None,
        estimator="matheron",
        min_stations_per_day=4):
    """
    Same climatological pooling as pooled_residual_variogram, but on the
    raw rainfall values directly (no elevation-drift removal). Use this
    to build the variogram for a plain Ordinary Kriging fallback.
    """

    mask = moving_window_mask(rain_df.index, target_date, window_days)
    window_dates = rain_df.index[mask]

    if max_lag is None:
        d = pairwise_distances(coords_x.to_numpy(), coords_y.to_numpy())
        max_lag = d.max() * (2.0 / 3.0)

    bin_edges = np.linspace(0, max_lag, n_lags + 1)

    sum_stat = np.zeros(n_lags)
    sum_dist = np.zeros(n_lags)
    count = np.zeros(n_lags, dtype=int)
    n_days_used = 0

    for date in window_dates:
        day = rain_df.loc[date]
        ok = day.notna()
        if ok.sum() < min_stations_per_day:
            continue

        common = coords_x.index.intersection(day.index[ok])
        x = coords_x.reindex(common).to_numpy(dtype=float)
        y = coords_y.reindex(common).to_numpy(dtype=float)
        r = day.reindex(common).to_numpy(dtype=float)

        dist = pairwise_distances(x, y)
        diff = r[:, None] - r[None, :]
        iu = np.triu_indices(len(r), k=1)
        d = dist[iu]
        dv = diff[iu]

        bin_idx = np.digitize(d, bin_edges) - 1
        n_days_used += 1

        for b in range(n_lags):
            sel = bin_idx == b
            m = sel.sum()
            if m == 0:
                continue
            count[b] += m
            sum_dist[b] += d[sel].sum()
            if estimator == "matheron":
                sum_stat[b] += np.sum(dv[sel] ** 2)
            elif estimator == "cressie":
                sum_stat[b] += np.sum(np.sqrt(np.abs(dv[sel])))
            else:
                raise ValueError("estimator must be 'matheron' or 'cressie'")

    lag_centers = np.full(n_lags, np.nan)
    gamma = np.full(n_lags, np.nan)

    populated = count > 0
    lag_centers[populated] = sum_dist[populated] / count[populated]

    if estimator == "matheron":
        gamma[populated] = sum_stat[populated] / (2 * count[populated])
    else:
        mean_root = sum_stat[populated] / count[populated]
        gamma[populated] = 0.5 * (mean_root ** 4) / (0.457 + 0.494 / count[populated])

    best_fit, all_fits = fit_best_variogram(lag_centers, gamma, count)

    return {
        "lag_centers": lag_centers,
        "gamma": gamma,
        "counts": count,
        "bin_edges": bin_edges,
        "n_days_used": n_days_used,
        "best_fit": best_fit,
        "all_fits": all_fits,
    }
