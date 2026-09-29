# -*- coding: utf-8 -*-
"""
build_variogram_cache.py

CLI entry point: builds cache/variogram_cache.csv (see
variogram_cache.py), sourced from the FILTERED rainfall dataset
(../filtered_stations_v2_pkg/rain_filtered.pkl) instead of the original
../kriging_interpolate_pkg/rain_fixed.pkl used by kriging_batch_pkg.

This must be rebuilt from scratch here (not reused from
kriging_batch_pkg/cache/variogram_cache.csv) because the filtered
dataset's residuals differ from the original wherever a station was
truncated to post-breakpoint-only data (20 of the 105 stations across
rain/tmax/tmin/rh -- 2 of 36 rainfall stations specifically: 919, 1043
-- see filtered_stations_v2_pkg/README.md).

Run once; re-run only if the underlying filtered rainfall record
changes or you want a different window/lag/estimator setting.
"""

import os
import sys
import pandas as pd

import paths  # noqa: F401
from projection_utils import load_projected_stations
from variogram_cache import build_doy_cache

STATION_FILE = "../station_info.csv"
# CSV-input variant (2026-09-27): sourced from rain_2005_2012.csv (2005-2012
# subset, copied into this folder) instead of the pickle the original
# kriging_standalone_pkg used.
RAIN_FILE = "../rain_2005_2012.csv"

WINDOW_DAYS = 7
N_LAGS = 12
ESTIMATOR = "matheron"


def main():
    os.makedirs("cache", exist_ok=True)

    time_budget = float(sys.argv[1]) if len(sys.argv) > 1 else 35.0

    stations = load_projected_stations(STATION_FILE)
    rain = pd.read_csv(RAIN_FILE, index_col=0, parse_dates=True)
    rain.columns = rain.columns.astype(stations.index.dtype)

    print(f"Building day-of-year variogram cache from FILTERED rainfall "
          f"(window=+/-{WINDOW_DAYS}d, n_lags={N_LAGS}, estimator={ESTIMATOR}, "
          f"time_budget={time_budget}s) ...")
    sys.stdout.flush()

    build_doy_cache(
        rain, stations,
        window_days=WINDOW_DAYS, n_lags=N_LAGS, estimator=ESTIMATOR,
        out_csv="cache/variogram_cache.csv",
        checkpoint_every=10,
        time_budget_s=time_budget,
    )


if __name__ == "__main__":
    main()
