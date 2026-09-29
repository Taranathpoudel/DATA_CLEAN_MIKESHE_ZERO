# -*- coding: utf-8 -*-
"""
variogram_cache.py

Precomputes and caches the climatological variogram (spherical/
exponential fit, from the 15-day moving-window pooling in
kriging_interpolate_pkg/climatology.py) for every day of the year
(1..365, leap-day folded into Feb 28 -- see climatology._calendar_doy),
for BOTH the KED-residual variant and the plain-rainfall OK variant.

This is the expensive step (pools ~690 days of station pairs per
day-of-year); it only needs to be done ONCE. Every actual calendar date
that shares a day-of-year (e.g. every 15 July from 1980-2025) then just
looks up its row instead of recomputing the pooled variogram -- this is
what makes the full 1980-2025 daily batch run in build_daily_kriging.py
feasible.
"""

import os
import time
import numpy as np
import pandas as pd

import paths  # noqa: F401  (adds kriging_interpolate_pkg to sys.path)
from climatology import pooled_residual_variogram, pooled_raw_variogram, _calendar_doy

CACHE_COLUMNS = [
    "doy", "month", "day",
    "ked_model", "ked_nugget", "ked_sill", "ked_range", "ked_rmse", "ked_n_days",
    "ok_model", "ok_nugget", "ok_sill", "ok_range", "ok_rmse", "ok_n_days",
]


###############################################################################
# Build
###############################################################################

def build_doy_cache(
        rain, stations,
        window_days=7, n_lags=12, estimator="matheron",
        out_csv="cache/variogram_cache.csv",
        checkpoint_every=10,
        time_budget_s=None,
        log_fn=print):
    """
    Compute the pooled climatological variogram for every day-of-year and
    write it to `out_csv` (checkpointed every `checkpoint_every` days so a
    long run can be monitored / resumed).

    Resumable: if `out_csv` already has some days-of-year computed, those
    are skipped. `time_budget_s`, if given, stops the run (after
    checkpointing) once that many seconds have elapsed, so this can be
    called repeatedly -- each call picking up where the last left off --
    to fit inside a short execution window.
    """

    ref_dates = pd.date_range("2001-01-01", "2001-12-31", freq="D")  # 365 days

    if os.path.exists(out_csv):
        existing = pd.read_csv(out_csv)
        rows = existing.to_dict("records")
        done_doys = set(existing["doy"].tolist())
    else:
        rows = []
        done_doys = set()

    t_start = time.time()
    n_computed_this_call = 0

    for i, d in enumerate(ref_dates):
        doy = int(_calendar_doy(pd.DatetimeIndex([d]))[0])

        if doy in done_doys:
            continue

        if time_budget_s is not None and (time.time() - t_start) > time_budget_s:
            log_fn(f"Time budget reached: {len(done_doys)}/365 done so far, "
                   f"stopping before doy={doy}. Re-run to continue.")
            break

        try:
            ked = pooled_residual_variogram(
                rain, stations["Z"], stations["Xp"], stations["Yp"], d,
                window_days=window_days, n_lags=n_lags, estimator=estimator)
            ked_fit, ked_n = ked["best_fit"], ked["n_days_used"]
        except Exception as e:
            log_fn(f"  [doy {doy}] KED fit failed: {e}")
            ked_fit, ked_n = None, 0

        try:
            ok = pooled_raw_variogram(
                rain, stations["Xp"], stations["Yp"], d,
                window_days=window_days, n_lags=n_lags, estimator=estimator)
            ok_fit, ok_n = ok["best_fit"], ok["n_days_used"]
        except Exception as e:
            log_fn(f"  [doy {doy}] OK fit failed: {e}")
            ok_fit, ok_n = None, 0

        row = {"doy": doy, "month": d.month, "day": d.day, "ked_n_days": ked_n, "ok_n_days": ok_n}
        for prefix, fit in (("ked", ked_fit), ("ok", ok_fit)):
            for key in ("model", "nugget", "sill", "range", "rmse"):
                row[f"{prefix}_{key}"] = fit[key] if fit else np.nan
        rows.append(row)
        done_doys.add(doy)
        n_computed_this_call += 1

        if n_computed_this_call % checkpoint_every == 0:
            elapsed = time.time() - t_start
            log_fn(f"{len(done_doys)}/365 day-of-year variograms done "
                   f"(doy={doy}, {elapsed:.0f}s elapsed this call)")
            pd.DataFrame(rows, columns=CACHE_COLUMNS).sort_values("doy").to_csv(out_csv, index=False)

    df = pd.DataFrame(rows, columns=CACHE_COLUMNS).sort_values("doy").reset_index(drop=True)
    df.to_csv(out_csv, index=False)
    log_fn(f"{len(done_doys)}/365 total done. Wrote {out_csv} "
           f"({time.time()-t_start:.0f}s this call).")
    return df


###############################################################################
# Fetch
###############################################################################

_CACHE_MEMO = {}


def load_doy_cache(path="cache/variogram_cache.csv"):
    if path not in _CACHE_MEMO:
        df = pd.read_csv(path)
        _CACHE_MEMO[path] = df.set_index("doy")
    return _CACHE_MEMO[path]


def get_cached_variogram(date, method, cache_path="cache/variogram_cache.csv"):
    """
    Fetch the precomputed variogram fit for the day-of-year of `date`.

    Parameters
    ----------
    date : any pandas-parseable date
    method : "ked" or "ok"

    Returns
    -------
    dict with keys model/nugget/sill/range (ready for kriging.py), plus
    n_days (how many days were pooled to build it).
    """

    df = load_doy_cache(cache_path)
    doy = int(_calendar_doy(pd.DatetimeIndex([pd.Timestamp(date)]))[0])

    if doy not in df.index:
        raise KeyError(f"day-of-year {doy} not found in variogram cache {cache_path}")

    row = df.loc[doy]
    prefix = "ked" if method == "ked" else "ok"

    if pd.isna(row[f"{prefix}_model"]):
        raise ValueError(f"No cached {method.upper()} variogram for day-of-year {doy} "
                          f"(fit failed when the cache was built).")

    return {
        "model": row[f"{prefix}_model"],
        "nugget": float(row[f"{prefix}_nugget"]),
        "sill": float(row[f"{prefix}_sill"]),
        "range": float(row[f"{prefix}_range"]),
        "rmse": float(row[f"{prefix}_rmse"]),
        "n_days": int(row[f"{prefix}_n_days"]),
    }
