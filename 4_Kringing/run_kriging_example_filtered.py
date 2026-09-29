# -*- coding: utf-8 -*-
"""
run_kriging_example_filtered.py

Same single-date diagnostic demo as
../kriging_interpolate_pkg/run_kriging_example.py, but sourced from the
FILTERED rainfall dataset (../filtered_stations_v2_pkg/rain_filtered.pkl)
instead of ../kriging_interpolate_pkg/rain_fixed.pkl -- so the climatological
variogram it builds (and the station values it krige's) reflect the
99%-CI, clean-neighbour-pool, 15-year-floor filtered data, matching what
the batch run in this same package used.

kriging_interpolate_pkg/ itself is left completely untouched -- this
script only imports its reusable modules (dem.py, meteo_data.py,
projection_utils.py, climatology.py, kriging.py, plotting.py), exactly
the way paths.py already does for the batch scripts in this package.

Note on "the new variogram": there is no separate cached-variogram file
to "load" here -- cache/variogram_cache.csv (built by
build_variogram_cache.py) stores only the FITTED model parameters
(nugget/sill/range) per day-of-year, not the raw experimental
semivariance cloud this diagnostic plot needs. This script instead
recomputes the climatological variogram live from the filtered rainfall,
with the exact same window (+/-7 days), lag count (12) and estimator
(matheron) build_variogram_cache.py used -- so for any given date it
produces the SAME fitted variogram as the cache (deterministic, same
inputs/formula), just computed on demand with the full diagnostic detail
available for plotting.

Usage:
    python run_kriging_example_filtered.py [YYYY-MM-DD]
    (defaults to 2025-07-15, same as the original demo)
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import paths  # noqa: F401  (adds ../kriging_interpolate_pkg to sys.path)
from dem import read_dem
from projection_utils import load_projected_stations
from climatology import (
    fit_daily_drift, drift_is_significant,
    pooled_residual_variogram, pooled_raw_variogram,
)
from kriging import (
    ordinary_kriging_predict, external_drift_kriging_predict,
    leave_one_out_cv,
)
from plotting import plot_drift, plot_variogram, plot_kriged_surface, plot_cross_validation


###############################################################################
# Config
###############################################################################

DEM_FILE = "../demtopo900utm45n.txt"
STATION_FILE = "../station_info.csv"
# CSV-input variant (2026-09-27): sourced from rain_2005_2012.csv (2005-2012
# subset, copied into this folder) instead of the pickle the original
# kriging_standalone_pkg used.
RAIN_FILE = "../rain_2005_2012.csv"   # <-- the 2005-2012 CSV subset, one level up

WINDOW_DAYS = 7          # +/- 7 days -> 15-day window (same as build_variogram_cache.py)
N_LAGS = 12
ESTIMATOR = "matheron"
R_THRESHOLD = 0.3
MIN_STATIONS_FOR_DRIFT = 8

OUTPUT_DIR = "outputs"


def run(target_date):

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    ###########################################################################
    # Load data
    ###########################################################################

    dem = read_dem(DEM_FILE)
    stations = load_projected_stations(STATION_FILE)
    rain = pd.read_csv(RAIN_FILE, index_col=0, parse_dates=True)
    rain.columns = rain.columns.astype(stations.index.dtype)

    target_date = pd.Timestamp(target_date)
    if target_date not in rain.index:
        raise ValueError(f"{target_date.date()} not found in rainfall record "
                          f"({rain.index.min().date()} to {rain.index.max().date()})")

    day = rain.loc[target_date]
    reporting = day.index[day.notna()].intersection(stations.index)

    x = stations.loc[reporting, "Xp"].to_numpy()
    y = stations.loc[reporting, "Yp"].to_numpy()
    z = stations.loc[reporting, "Z"].to_numpy()
    v = day.loc[reporting].to_numpy()

    print(f"Target date: {target_date.date()}  "
          f"({len(reporting)} of {len(stations)} stations reporting, FILTERED dataset)")

    ###########################################################################
    # Elevation drift: decide KED vs. OK
    ###########################################################################

    drift_fit = fit_daily_drift(day, stations["Z"], min_stations=4)
    use_ked = drift_is_significant(
        drift_fit, r_threshold=R_THRESHOLD, min_stations=MIN_STATIONS_FOR_DRIFT)

    method = "ked" if use_ked else "ok"
    print(f"Elevation-rainfall correlation r={drift_fit['r']:.3f} "
          f"(n={drift_fit['n']})  ->  method = {method.upper()}")

    ###########################################################################
    # Climatological variogram (15-day moving window, all years pooled,
    # FROM THE FILTERED RESIDUAL POOL -- this is "the new variogram")
    ###########################################################################

    if use_ked:
        vgram = pooled_residual_variogram(
            rain, stations["Z"], stations["Xp"], stations["Yp"],
            target_date, window_days=WINDOW_DAYS, n_lags=N_LAGS, estimator=ESTIMATOR)
    else:
        vgram = pooled_raw_variogram(
            rain, stations["Xp"], stations["Yp"],
            target_date, window_days=WINDOW_DAYS, n_lags=N_LAGS, estimator=ESTIMATOR)

    vfit = vgram["best_fit"]
    print(f"Climatological variogram, filtered dataset ({vgram['n_days_used']} days pooled, "
          f"window=+/-{WINDOW_DAYS}d): {vfit}")

    ###########################################################################
    # Krige onto the DEM grid
    ###########################################################################

    if use_ked:
        zhat, var = external_drift_kriging_predict(
            x, y, v, z, dem.x, dem.y, dem.z, vfit)
    else:
        zhat, var = ordinary_kriging_predict(x, y, v, dem.x, dem.y, vfit)

    zhat = np.clip(zhat, 0, None)

    ###########################################################################
    # Leave-one-out cross-validation
    ###########################################################################

    cv = leave_one_out_cv(x, y, v, z, vfit, method=method)
    print(f"LOO cross-validation: RMSE={cv['rmse']:.2f} mm  "
          f"MAE={cv['mae']:.2f} mm  bias={cv['bias']:.2f} mm")

    ###########################################################################
    # Figure
    ###########################################################################

    fig, axes = plt.subplots(2, 2, figsize=(13, 12))

    plot_drift(stations["Z"], day, drift_fit,
               title=f"Elevation-rainfall drift on {target_date.date()} (filtered dataset)",
               ax=axes[0, 0])

    plot_variogram(vgram,
                    title=f"Climatological variogram, filtered dataset (+/-{WINDOW_DAYS}d window, "
                          f"{vgram['n_days_used']} days pooled)",
                    ax=axes[0, 1])

    plot_kriged_surface(dem.x, dem.y, zhat,
                         stations_x=x, stations_y=y, stations_v=v,
                         title=f"Kriged rainfall ({method.upper()}), {target_date.date()}, filtered",
                         ax=axes[1, 0])

    plot_cross_validation(cv, ax=axes[1, 1])

    fig.suptitle(f"Rainfall Kriging (FILTERED dataset) -- {target_date.date()}  "
                 f"(method: {method.upper()})", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])

    out_path = f"{OUTPUT_DIR}/kriging_filtered_{target_date.date()}.png"
    fig.savefig(out_path, dpi=150)
    print(f"Saved figure to {out_path}")

    return {
        "zhat": zhat, "var": var, "dem": dem, "vgram": vgram,
        "vfit": vfit, "cv": cv, "method": method, "drift_fit": drift_fit,
    }


if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else "2009-07-20"
    run(date_arg)
