# -*- coding: utf-8 -*-
"""
run_batch_all_years.py

CLI entry point: krige every day of every year in the FILTERED rainfall
record (../filtered_stations_v2_pkg/rain_filtered.pkl -- the 99%-CI,
15-year-floor filtered dataset, see filtered_stations_v2_pkg/README.md)
and write netcdf_out/rainfall_kriged_<year>.nc for each year.

Otherwise identical to kriging_batch_pkg/run_batch_all_years.py: same
KED/OK method (batch_daily_kriging.process_year, copied unchanged from
kriging_batch_pkg/), same variogram-cache lookup mechanism -- only the
source rainfall file (and therefore this run's own variogram cache,
built fresh in cache/variogram_cache.csv by build_variogram_cache.py)
differ.

Resumable and time-budgeted: years whose output file already exists are
skipped, and processing stops once `time_budget_s` has elapsed (so this
can safely be re-run repeatedly until every year is done).

Requires cache/variogram_cache.csv to already exist -- run
build_variogram_cache.py first.

Usage:
    python run_batch_all_years.py [time_budget_seconds] [start_year] [end_year]
"""

import os
import sys
import time
import pandas as pd

import paths  # noqa: F401
from dem import read_dem
from projection_utils import load_projected_stations
from batch_daily_kriging import process_year

STATION_FILE = "../station_info.csv"
DEM_FILE = "demtopo900utm45n.txt"
# CSV-input variant (2026-09-27): sourced from rain_2005_2012.csv (2005-2012
# subset, copied into this folder) instead of the pickle the original
# kriging_standalone_pkg used.
RAIN_FILE = "../rain_2005_2012.csv"
CACHE_PATH = "cache/variogram_cache.csv"
OUT_DIR = "netcdf_out"


def main():
    time_budget = float(sys.argv[1]) if len(sys.argv) > 1 else 38.0

    if not os.path.exists(CACHE_PATH):
        raise SystemExit(
            f"{CACHE_PATH} not found -- run build_variogram_cache.py first.")

    stations = load_projected_stations(STATION_FILE)
    dem = read_dem(DEM_FILE)
    rain = pd.read_csv(RAIN_FILE, index_col=0, parse_dates=True)
    rain.columns = rain.columns.astype(stations.index.dtype)

    all_years = sorted(rain.index.year.unique())
    if len(sys.argv) > 3:
        start_year, end_year = int(sys.argv[2]), int(sys.argv[3])
        all_years = [y for y in all_years if start_year <= y <= end_year]

    t_start = time.time()
    done, skipped = 0, 0

    for year in all_years:
        out_path = os.path.join(OUT_DIR, f"rainfall_kriged_{year}.nc")
        if os.path.exists(out_path):
            skipped += 1
            continue

        if (time.time() - t_start) > time_budget:
            print(f"Time budget reached after {done} year(s) this call "
                  f"({skipped} already done). Re-run to continue.")
            return

        process_year(year, rain, stations, dem, cache_path=CACHE_PATH, out_dir=OUT_DIR)
        done += 1

    print(f"All requested years complete: {done} processed this call, "
          f"{skipped} were already done.")


if __name__ == "__main__":
    main()
