# kriging_standalone_pkg -- CSV-input variant, cache rebuilt from the 2005-2012 subset

This is the training-copy variant of `kriging_standalone_pkg` (originally
built in `rainfall_kriging/`, sibling of `kriging_batch_filtered_2026-09-02_pkg/`,
where it reads rainfall from a pickle covering 1980-2025 and reuses that
package's pre-fitted, full-46-year variogram cache unchanged). This copy is
different in two deliberate ways, both by explicit request:

1. Rainfall and station metadata are read from **CSV**, not pickle.
2. The day-of-year variogram cache is **rebuilt from scratch, from only the
   2005-2012 CSV** -- it is NOT the frozen full-record cache the original
   package reuses. This is a deliberate departure from this project's usual
   "always reuse the full-record cache, never rebuild from a short subset"
   rule (see the top of the project's methodology notes) -- done here
   because the training copy is meant to demonstrate the *whole* pipeline,
   cache-building step included, on a small, fast, self-contained dataset.
   The resulting cache is legitimately weaker/noisier than the production
   46-year cache (see Caveat below) -- fine for training, not a substitute
   for the real archives.

## Folder layout (as of this variant)

```
training_materials_kriging_2005_2012/rainfall_kriging/
├── station_info.csv              <- read by every script in the package, via "../"
├── rain_2005_2012.csv             <- read by every script in the package, via "../"
├── demtopo900utm45n.txt           <- also exists as a LOCAL copy inside the package (unchanged since the package was first made standalone)
└── kriging_standalone_pkg/
    ├── build_variogram_cache.py   <- STATION_FILE/RAIN_FILE point one level up
    ├── run_batch_all_years.py     <- STATION_FILE/RAIN_FILE point one level up
    ├── run_kriging_example_filtered.py  <- STATION_FILE/RAIN_FILE point one level up
    ├── demtopo900utm45n.txt       <- DEM stays LOCAL (not changed -- only station/rain were asked to move up)
    ├── cache/variogram_cache.csv  <- REBUILT from the 2005-2012 CSV (see below), not copied from the original package
    ├── netcdf_out/                <- rainfall_kriged_2005.nc .. rainfall_kriged_2012.nc (all 8 years)
    ├── outputs/                   <- diagnostic figures
    └── (all other .py modules: engine + batch driver, copied unchanged, see history below)
```

**No copies of `station_info.csv` or `rain_2005_2012.csv` are kept inside
`kriging_standalone_pkg/` any more** -- they were briefly duplicated in an
earlier pass, then removed once the scripts were pointed at the parent
folder's copies instead, per instruction ("don't touch anything inside the
packaged folder" -- interpreted as: don't add/keep data-file copies there;
the three CLI scripts themselves DO need editing, since pointing them one
level up is the actual ask). `demtopo900utm45n.txt` is left as it was
(local, inside the package) -- only `station_info.csv`/the rain file were
asked to move up.

## What changed in the code, exactly (2026-09-27, this pass)

Three files, `STATION_FILE`/`RAIN_FILE` constants only -- no solver, drift,
or variogram logic touched:

- **`build_variogram_cache.py`**: `STATION_FILE = "station_info.csv"` ->
  `"../station_info.csv"`; `RAIN_FILE = "rain_2005_2012.csv"` ->
  `"../rain_2005_2012.csv"`.
- **`run_batch_all_years.py`**: same two constants, same change.
- **`run_kriging_example_filtered.py`**: same two constants, same change
  (`DEM_FILE` untouched in all three -- DEM stays local).

(Earlier pass, still in effect: `pd.read_pickle(RAIN_FILE)` ->
`pd.read_csv(RAIN_FILE, index_col=0, parse_dates=True)` in all three
scripts, plus the pre-existing `rain.columns = rain.columns.astype(stations.index.dtype)`
line right after it, which is what makes a CSV's text column headers match
`station_info.csv`'s integer `Station` column -- see the history section
below for why that line matters.)

## Cache rebuilt from the 2005-2012 subset (this pass)

Ran, from inside `kriging_standalone_pkg/`:

```
python build_variogram_cache.py 60      # run twice; time-budgeted/resumable, 365/365 day-of-year rows in ~68s total
python run_batch_all_years.py 300 2005 2012
```

`cache/variogram_cache.csv` now holds a variogram fitted purely from the
2005-2012 rainfall record (max 120 days pooled per day-of-year: 15-day
window x 8 years, vs. the production cache's ~690 days from 46 years). All
8 years' NetCDFs (`netcdf_out/rainfall_kriged_2005.nc` .. `_2012.nc`) were
regenerated with this new cache -- the stale test output and cache from the
earlier (reused-full-cache) pass were deleted first, so nothing here is
left over from before.

**Verification**: `run_kriging_example_filtered.py 2012-07-15` (live
recompute, not using the cache file at all -- see below) now matches
`cache/variogram_cache.csv`'s row for that calendar day to full float
precision: nugget=43.07726743583963, sill=495.7189241963825,
range=105473.7755997243, exponential, 120 days pooled, OK method (r=0.052).
(Note: 2012 is a leap year, so pandas' own day-of-year for 2012-07-15 is
197, but the cache's day-of-year numbering folds Feb 29 into Feb 28 --
described in the project's methodology notes -- so the matching row is
`doy=196`, not 197; checked both rows above and below to confirm this is
the right one, not a coincidence.) This match is expected and is the
correct outcome now: unlike the earlier pass (frozen 46-year cache vs. a
live recompute over only 8 years, which legitimately disagreed), cache and
live recompute now source from the exact same 2005-2012 data, so they
agree exactly, the same way the original full-record package's cache and
live recompute always have.

## Caveat (kept from the earlier pass, now describing the cache itself rather than a mismatch)

This cache is fitted from only 8 years instead of 46 -- day-of-year bins
pool at most 120 raw days (15-day window x 8 years) instead of ~690,
meaningfully noisier per the same reasoning documented in the project's
methodology notes ("reuse the cache, never rebuild from a short subset").
That tradeoff was made deliberately here, per explicit instruction, so this
copy is self-contained for training/demonstration purposes end-to-end
(including the cache-build step) rather than reusing a cache from data
outside this folder. It is not a recommendation to do this for the real
1980-2025 archives.

## Usage

    python build_variogram_cache.py [time_budget_seconds]   # re-run if you regenerate ../rain_2005_2012.csv; resumable
    python run_batch_all_years.py [time_budget_seconds] [start_year] [end_year]
    python run_kriging_example_filtered.py [YYYY-MM-DD]      # pick a date inside 2005-01-01..2012-12-31

All three must be run with this folder (`kriging_standalone_pkg/`) as the
working directory -- `STATION_FILE`/`RAIN_FILE` are `"../station_info.csv"`/
`"../rain_2005_2012.csv"`, relative to this folder.

## CSV format expected by `../rain_2005_2012.csv`

```
Station_ID,909,1030,1036,...,1122
2005-01-01,0.0,0.0,0.0,...,
2005-01-02,0.0,0.0,0.0,...,
...
```
First column header can be anything (read via `index_col=0`) but must hold
dates parseable by `pd.read_csv(..., parse_dates=True)`; the remaining
column headers must be the station IDs exactly as they appear in
`../station_info.csv`'s `Station` column; a blank cell means missing.

## History (earlier passes, kept for traceability)

- **Made standalone from `kriging_batch_filtered_2026-09-02_pkg` +
  `kriging_interpolate_pkg` (2026-09-27, in `rainfall_kriging/`)**: every
  dependency flattened into one folder, `paths.py` made a no-op stub,
  `STATION_FILE`/`DEM_FILE`/`RAIN_FILE` repointed from `"../..."` to local
  filenames. Verified byte-for-byte identical NetCDF output and exact
  variogram reproduction against the original multi-folder package.
- **Copied into this training folder + switched pickle to CSV (2026-09-27,
  earlier pass today)**: `RAIN_FILE` repointed at `rain_2005_2012.csv`,
  `pd.read_pickle` -> `pd.read_csv`. Verified batch output byte-identical
  to the pre-switch pickle-based run for 2012. At that point
  `station_info.csv`/`rain_2005_2012.csv` were duplicated INTO this folder
  and `cache/variogram_cache.csv` was still the ORIGINAL full-46-year cache,
  copied in unchanged.
- **This pass**: cache rebuilt from only the 2005-2012 data (see above);
  `station_info.csv`/`rain_2005_2012.csv` duplicates removed from inside
  this folder; the three CLI scripts now read both files from one level up
  instead.
