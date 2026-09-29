# -*- coding: utf-8 -*-
"""
batch_daily_kriging.py

Interpolates rainfall onto the DEM grid for every day in a year (Kriging
with External Drift, falling back to Ordinary Kriging exactly as in
kriging_interpolate_pkg -- see that package's README for the method
rationale), using the PRE-COMPUTED day-of-year variogram cache
(variogram_cache.py) instead of rebuilding the climatological variogram
per day. Writes one NetCDF file per year: rainfall(time,y,x) [mm] and
kriging_variance(time,y,x) [mm^2] (the per-cell kriging error estimate),
plus small per-day metadata (method used, reporting-station count,
elevation-rainfall correlation).
"""

import os
import time
import numpy as np
import pandas as pd

import paths  # noqa: F401
from dem import read_dem
from projection_utils import load_projected_stations
from climatology import fit_daily_drift, drift_is_significant
from kriging import ordinary_kriging_predict, external_drift_kriging_predict
from variogram_cache import get_cached_variogram
from netcdf_writer import write_year_netcdf

TIME_EPOCH = pd.Timestamp("1980-01-01")
R_THRESHOLD = 0.3
MIN_STATIONS_FOR_DRIFT = 8
MIN_STATIONS_TO_INTERPOLATE = 4


def process_year(
        year, rain, stations, dem,
        cache_path="cache/variogram_cache.csv",
        out_dir="netcdf_out",
        log_fn=print):
    """
    Krige every day of `year` and write netcdf_out/rainfall_kriged_<year>.nc.
    Returns the output path, or None if the year had no data.
    """

    dates = rain.index[rain.index.year == year]
    if len(dates) == 0:
        log_fn(f"{year}: no rainfall data, skipping.")
        return None

    ny, nx = dem.z.shape
    n = len(dates)

    rainfall_arr = np.full((n, ny, nx), np.nan, dtype="f4")
    variance_arr = np.full((n, ny, nx), np.nan, dtype="f4")
    method_flag = np.full(n, -1, dtype="i4")       # -1=no data, 0=OK, 1=KED
    n_reporting = np.zeros(n, dtype="i4")
    corr_r = np.full(n, np.nan, dtype="f4")

    t0 = time.time()

    for i, date in enumerate(dates):
        day = rain.loc[date]
        reporting = day.index[day.notna()].intersection(stations.index)
        n_reporting[i] = len(reporting)

        if len(reporting) < MIN_STATIONS_TO_INTERPOLATE:
            continue

        x = stations.loc[reporting, "Xp"].to_numpy()
        y = stations.loc[reporting, "Yp"].to_numpy()
        z = stations.loc[reporting, "Z"].to_numpy()
        v = day.loc[reporting].to_numpy()

        drift_fit = fit_daily_drift(day, stations["Z"], min_stations=4)
        corr_r[i] = drift_fit["r"] if drift_fit else np.nan
        use_ked = drift_is_significant(
            drift_fit, r_threshold=R_THRESHOLD, min_stations=MIN_STATIONS_FOR_DRIFT)
        method = "ked" if use_ked else "ok"

        try:
            vfit = get_cached_variogram(date, method, cache_path=cache_path)
        except (KeyError, ValueError):
            # cache miss for the preferred method -- try the other one
            # before giving up on the day entirely
            other = "ok" if method == "ked" else "ked"
            try:
                vfit = get_cached_variogram(date, other, cache_path=cache_path)
                use_ked = (other == "ked")
            except (KeyError, ValueError):
                continue

        if use_ked:
            zhat, var = external_drift_kriging_predict(x, y, v, z, dem.x, dem.y, dem.z, vfit)
        else:
            zhat, var = ordinary_kriging_predict(x, y, v, dem.x, dem.y, vfit)
            # Unlike KED, plain OK never touches dem.z, so it doesn't
            # automatically stop at the DEM's valid (non-rectangular)
            # extent the way KED incidentally does via the elevation
            # term -- mask it explicitly so both methods cover the same
            # domain and no OK day silently extrapolates past it.
            invalid = ~np.isfinite(dem.z)
            zhat[invalid] = np.nan
            var[invalid] = np.nan

        rainfall_arr[i] = np.clip(zhat, 0, None).astype("f4")
        variance_arr[i] = var.astype("f4")
        method_flag[i] = 1 if use_ked else 0

    elapsed = time.time() - t0

    time_days = (dates - TIME_EPOCH).days.to_numpy(dtype="i4")
    x1d = dem.x[0, :].astype("f8")
    y1d = dem.y[:, 0].astype("f8")

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"rainfall_kriged_{year}.nc")

    write_year_netcdf(
        out_path,
        time_days, f"days since {TIME_EPOCH.date()}",
        x1d, y1d, "EPSG:32645",
        variables={
            "rainfall": {
                "data": rainfall_arr, "dims": ("time", "y", "x"),
                "long_name": "Kriged daily rainfall", "units": "mm",
                "fill_value": np.nan,
            },
            "kriging_variance": {
                "data": variance_arr, "dims": ("time", "y", "x"),
                "long_name": "Kriging estimation variance (error estimate)",
                "units": "mm^2", "fill_value": np.nan,
            },
            "method_flag": {
                "data": method_flag.astype("f4"), "dims": ("time",),
                "long_name": "-1=no interpolation (too few stations), 0=Ordinary Kriging, 1=Kriging with External Drift",
                "units": "1", "fill_value": -1.0,
            },
            "n_stations_reporting": {
                "data": n_reporting.astype("f4"), "dims": ("time",),
                "long_name": "Number of stations reporting on this day",
                "units": "count", "fill_value": 0.0,
            },
            "elevation_rainfall_r": {
                "data": corr_r.astype("f4"), "dims": ("time",),
                "long_name": "Elevation-rainfall correlation used for the KED/OK decision",
                "units": "1", "fill_value": np.nan,
            },
        },
        global_attrs={
            "title": f"Daily kriged rainfall, {year}",
            "summary": (
                "Kriging with External Drift (elevation), falling back to "
                "Ordinary Kriging when the daily elevation-rainfall "
                "correlation is weak; variogram from a 15-day moving-window "
                "climatology, precomputed per day-of-year."
            ),
            "r_threshold_for_ked": R_THRESHOLD,
            "min_stations_for_ked": MIN_STATIONS_FOR_DRIFT,
        },
    )

    log_fn(f"{year}: {n} days, wrote {out_path} ({elapsed:.1f}s kriging compute)")
    return out_path
