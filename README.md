# Everything_Arranged — Full Pipeline Guide

> **Purpose:** End-to-end rainfall data processing pipeline: raw station CSVs → homogeneity testing → spatial kriging interpolation → zonal statistics → MIKE DFS0 files ready for hydrological modelling.

---

## 📁 Folder Structure at a Glance

```
Everything_Arranged/
│
├── 1_Datas/                          ← RAW INPUT DATA (start here)
│   └── rain_selected_stations.csv
│
├── 2_Homogeneity_Test/               ← STEP 1 SCRIPT: Run SNHT test GUI
│   ├── 1_Run_Homogenity_test.bat
│   ├── 1_snht_gui_app.py
│   └── Output/                       ← (GUI writes here by default)
│
├── 3_Homogeneity_Test_Output/        ← STEP 1 OUTPUT (copy here manually, or from GUI)
│   ├── A_annual_totals.csv
│   ├── B_snht_results.csv
│   ├── B1_snht_all_stations.png
│   ├── C_relative_result_1030.txt
│   ├── C_relative_series_1030.csv
│   └── D_relative_homogeneity_1030.png
│
├── 4_Kringing/                       ← STEP 2 SCRIPTS: Variogram + Kriging GUIs
│   ├── 2_Variogram_cache_Builder.bat
│   ├── 3_build_Variogram_cache.bat
│   ├── 4_Run_One_Kringing.bat
│   ├── 5_run_batch_kriging_gui_app.bat
│   ├── [all .py engine files]
│   ├── demtopo900utm45n.txt          ← DEM stays LOCAL here
│   ├── cache/variogram_cache.csv     ← built by step 2a
│   ├── netcdf_out/                   ← kriged NetCDFs per year
│   └── outputs/                      ← diagnostic PNG figures
│
├── 5_Input_data_kringing/            ← INPUT STAGING for Kriging steps
│   ├── 1_homogeneity_test_output/    ← copy_from_homogeneity_output.bat
│   ├── 2_Input_for_Variogram_Cache_Builder_data/  ← copy_inputs_for_variogram_cache_builder.bat
│   ├── 3_Input_for_Build_Varogram_Cache/          ← copy_inputs_for_build_variogram_cache.bat
│   ├── 4_Input_Run_one_kringing/                  ← copy_inputs_for_run_one_kriging.bat
│   └── 5_Input_Run_Batch_Kringing/                ← copy_inputs_for_batch_kriging.bat
│
├── 6_Kringing_Output/                ← STEP 2 OUTPUT (kriged NetCDFs + cache)
│   ├── cache/variogram_cache.csv
│   ├── netcdf_out/                   ← rainfall_kriged_YYYY.nc files
│   └── outputs/                      ← diagnostic plots
│
├── 7_Zonal_Statistics/               ← STEP 3 SCRIPT: Zonal stats GUI
│   ├── 3_Run_Zonal_Statistics.cmd
│   └── zonal_statistic.py
│
├── 8_Input_Data_Zonal_Statistics/    ← INPUT STAGING for Zonal Statistics
│   ├── copy_netcdf_from_kriging_output.bat
│   ├── netcdf_out/                   ← *.nc copied here from 6_Kringing_Output
│   └── shapefile/                    ← catchment shapefile (placed manually)
│
├── 9_Zonal_Statistics_Output/        ← STEP 3 OUTPUT
│   └── csv_for_netcdf0/              ← subbasin_rain.csv and plots
│
├── 10_write_dfs0_file/               ← STEP 4 SCRIPT: CSV to DFS0 GUI
│   ├── Run_write_dfs0.cmd
│   └── 4_write_dsf0.py
│
├── 11_Input_Files_dfs0/              ← INPUT STAGING for DFS0 conversion
│   ├── copy_csv_from_zonal_statistics.bat
│   └── csv_for_netcdf0/              ← *.csv copied here from 9_Zonal_Statistics_Output
│
└── 12_write_dfs0_file_output/        ← STEP 4 OUTPUT: final .dfs0 files
```

---

## 🔄 Pipeline Overview

Each stage produces outputs that become the **inputs of the next stage**. The `.bat` files listed in the staging folders automate the file copying between stages — double-click them instead of copying manually.

```
[1_Datas]
    │  rain_selected_stations.csv
    ▼
[STEP 1] 2_Homogeneity_Test  →  3_Homogeneity_Test_Output
    │  A_annual_totals.csv, B_snht_results.csv, station CSVs, PNGs
    ▼
[STEP 2a] Variogram Cache Builder  (reads from 5_Input_data_kringing/2_ and 3_)
    │  cache/variogram_cache.csv
    ▼
[STEP 2b] Run One Kriging / Batch Kriging  (reads from 5_Input_data_kringing/4_ and 5_)
    │  6_Kringing_Output/netcdf_out/rainfall_kriged_YYYY.nc
    ▼
[STEP 3] Zonal Statistics  (reads NetCDFs + shapefile from 8_Input_Data_Zonal_Statistics)
    │  9_Zonal_Statistics_Output/csv_for_netcdf0/subbasin_rain.csv
    ▼
[STEP 4] Write DFS0  (reads CSVs from 11_Input_Files_dfs0/csv_for_netcdf0)
    │  12_write_dfs0_file_output/*.dfs0
    ▼
  [MIKE Hydrological Model]
```

---

## 🚀 Step-by-Step Instructions

### Step 0 — Place Raw Data

Put your raw daily rainfall CSV in `1_Datas/`:

```
1_Datas/rain_selected_stations.csv
```

**Expected format:**
```
Station_ID,909,1030,1036,...,1122
2005-01-01,0.0,0.0,0.0,...,
2005-01-02,0.0,0.0,0.0,...,
```
- First column: dates (any header name, `index_col=0`)
- Remaining columns: one column per station; column headers = Station IDs
- Blank cell = missing value

Also place your static files in `1_Datas/` if not already there:
- `station_info.csv` — station metadata with a `Station` integer column
- `demtopo900utm45n.txt` — DEM/topography grid in UTM Zone 45N

---

### Step 1 — Homogeneity Test (SNHT)

**Script:** `2_Homogeneity_Test/`
**Launcher:** Double-click `1_Run_Homogenity_test.bat`

This opens a GUI (`1_snht_gui_app.py`) with:

| Parameter | Description | Default |
|---|---|---|
| **Input CSV** | Your `rain_selected_stations.csv` from `1_Datas/` | *(browse)* |
| **Output Directory** | Where to save results | `snht_output/` |
| **ALPHA** | Significance level for SNHT test | `0.05` |
| **MIN_DAYS** | Min valid days/year to include a year | `330` |
| **SIM** | Monte Carlo simulations for p-value | `20000` |
| **CANDIDATE** | Station ID for relative homogeneity analysis | `1030` |

**Outputs written to `3_Homogeneity_Test_Output/`:**

| File | Description |
|---|---|
| `A_annual_totals.csv` | Annual rainfall totals per station |
| `B_snht_results.csv` | SNHT test results (T-stat, p-value, break year, means) |
| `B1_snht_all_stations.png` | Plot: absolute SNHT for all stations |
| `C_relative_series_<ID>.csv` | Station vs neighbour reference time series |
| `C_relative_result_<ID>.txt` | Verdict text for the candidate station |
| `D_relative_homogeneity_<ID>.png` | Plot: relative SNHT for the candidate station |

> The SNHT (Standard Normal Homogeneity Test) detects abrupt shifts in a station's long-term record caused by non-climatic factors (station relocation, instrument change, observer change). The relative test compares the candidate station to its neighbours to distinguish real climate signals from station-specific breaks.

---

### Step 2a — Build Variogram Cache

**Script:** `4_Kringing/`
**Launchers:**
- GUI: `2_Variogram_cache_Builder.bat` → opens `variogram_cache_gui_app.py`
- CLI wrapper: `3_build_Variogram_cache.bat` → opens `build_cache_gui_app.py`

**Before running — copy inputs (double-click these first):**
```
5_Input_data_kringing\2_Input_for_Variogram_Cache_Builder_data\
    copy_inputs_for_variogram_cache_builder.bat

5_Input_data_kringing\3_Input_for_Build_Varogram_Cache\
    copy_inputs_for_build_variogram_cache.bat
```
These bat files copy `rain_2005_2012.csv`, `station_info.csv`, and `demtopo900utm45n.txt` from `1_Datas/` into the staging folders.

**What it does:**
Fits an exponential variogram model for each calendar day-of-year (365 rows) using a ±7-day pooling window. Writes `4_Kringing/cache/variogram_cache.csv`.

**CLI usage (run from inside `4_Kringing/`):**
```
python build_variogram_cache.py [time_budget_seconds]
```

The cache builder is **resumable** — it checkpoints every 10 rows. If interrupted, re-run and it continues from where it stopped. Run with a time budget of `60` seconds per call for safe interactive sessions.

---

### Step 2b — Run Kriging (Single Date or Batch)

**Script:** `4_Kringing/`

#### Single date (for inspection / verification):
**Launcher:** `4_Run_One_Kringing.bat` → `2_kriging_gui_app.py`

**Before running — copy inputs:**
```
5_Input_data_kringing\4_Input_Run_one_kringing\
    copy_inputs_for_run_one_kriging.bat
```

#### Full batch (all years):
**Launcher:** `5_run_batch_kriging_gui_app.bat` → `run_batch_kriging_gui_app.py`

**Before running — copy inputs:**
```
5_Input_data_kringing\5_Input_Run_Batch_Kringing\
    copy_inputs_for_batch_kriging.bat
```

> **Important:** Run **Step 2a first** — the batch bat also copies `variogram_cache.csv` from `6_Kringing_Output/cache/` into the staging folder. If the cache does not exist yet the bat will warn you.

**Inputs read by kriging scripts:**

| File | Location |
|---|---|
| `station_info.csv` | `../station_info.csv` (one level up from `4_Kringing/`) |
| `rain_2005_2012.csv` | `../rain_2005_2012.csv` (one level up from `4_Kringing/`) |
| `demtopo900utm45n.txt` | **local** inside `4_Kringing/` |
| `cache/variogram_cache.csv` | `4_Kringing/cache/` |

**CLI usage (run from inside `4_Kringing/`):**
```
python run_kriging_example_filtered.py YYYY-MM-DD
python run_batch_all_years.py [time_budget_s] [start_year] [end_year]
```

**Outputs written to `6_Kringing_Output/`:**

| Location | Description |
|---|---|
| `netcdf_out/rainfall_kriged_YYYY.nc` | Kriged daily rainfall grid per year |
| `cache/variogram_cache.csv` | Day-of-year fitted variogram parameters |
| `outputs/*.png` | Diagnostic kriging maps |

> The kriging uses **KED (Kriging with External Drift)** where terrain elevation (DEM) acts as a covariate, falling back to **OK (Ordinary Kriging)** when the KED system is ill-conditioned. The variogram cache is pre-fitted per calendar day-of-year to avoid refitting on every day of the batch run. The batch runner is resumable — years whose output `.nc` file already exists are skipped automatically.

---

### Step 3 — Zonal Statistics (NetCDF → Subbasin CSVs)

**Script:** `7_Zonal_Statistics/`
**Launcher:** Double-click `3_Run_Zonal_Statistics.cmd`

**Before running — copy inputs:**
```
8_Input_Data_Zonal_Statistics\
    copy_netcdf_from_kriging_output.bat
```
This copies all `*.nc` files from `6_Kringing_Output/netcdf_out/` into `8_Input_Data_Zonal_Statistics/netcdf_out/`.

> **Important:** **Manually place** your catchment shapefile inside `8_Input_Data_Zonal_Statistics/shapefile/` before running. It must be in the **same CRS (coordinate system)** as the kriged NetCDF grids (UTM Zone 45N, EPSG:32645).

**GUI inputs:**

| Parameter | Description | Default |
|---|---|---|
| **NetCDF Folder** | Folder containing `*.nc` files | browse to `8_Input_Data_Zonal_Statistics/netcdf_out/` |
| **Shapefile (.shp)** | Catchment polygon shapefile | browse to `8_Input_Data_Zonal_Statistics/shapefile/` |
| **Output CSV** | Where to save the result | `9_Zonal_Statistics_Output/csv_for_netcdf0/subbasin_rain.csv` |
| **Polygon Field** | Shapefile attribute column for basin names | `Cat_Name` |

**What it does:**
For every time step in every NetCDF, computes the **area-weighted mean** rainfall value inside each catchment polygon. Produces a single merged CSV with `Date` as the index and one column per sub-basin.

**Outputs written to `9_Zonal_Statistics_Output/csv_for_netcdf0/`:**

| File | Description |
|---|---|
| `subbasin_rain.csv` | Daily mean rainfall per sub-basin |
| `annual_summary_plot.png` | Annual total per sub-basin |
| `monthly_climatology_plot.png` | Mean monthly climatology per sub-basin |

> Output values ≤ 0.1 mm are set to `0` and results are rounded to 2 decimal places. Dates with no valid kriged pixels inside a basin are reported as `NaN` with a WARNING in the log.

---

### Step 4 — Write DFS0 Files (CSV → MIKE Format)

**Script:** `10_write_dfs0_file/`
**Launcher:** Double-click `Run_write_dfs0.cmd`

**Before running — copy inputs:**
```
11_Input_Files_dfs0\
    copy_csv_from_zonal_statistics.bat
```
This copies all `*.csv` files from `9_Zonal_Statistics_Output/csv_for_netcdf0/` into `11_Input_Files_dfs0/csv_for_netcdf0/`.

**GUI inputs:**

| Parameter | Description | Default |
|---|---|---|
| **Input CSV** | The subbasin rainfall CSV | browse to `11_Input_Files_dfs0/csv_for_netcdf0/subbasin_rain.csv` |
| **Output Directory** | Where DFS0 files are saved | `12_write_dfs0_file_output/` |
| **Variable Type** | EUM type for MIKE | `rainfall` |

> **Important:** The CSV **must contain a column named `Date`**. All other columns are treated as individual sub-basins and each gets its own `.dfs0` file.

**Variable type → MIKE EUM mapping:**

| Selection | EUM Type | EUM Unit | Data Value Type |
|---|---|---|---|
| `rainfall` | Rainfall | millimeter | StepAccumulated |
| `temperature` | Temperature | degree_Celsius | Instantaneous |
| `Evapotranspiration` | Evaporation | millimeter | StepAccumulated |
| `Discharge` | Discharge | m³/s | Instantaneous |

**Outputs written to `12_write_dfs0_file_output/`:**

| File | Description |
|---|---|
| `<subbasin_name>.dfs0` | One MIKE DFS0 file per sub-basin column |

---

## 🔁 Automated Copy Bat Files — Quick Reference

These bat files eliminate manual file copying between stages. Run them **before** the script at each stage.

| Bat File | Located In | Copies FROM → TO |
|---|---|---|
| `copy_from_homogeneity_output.bat` | `5_Input_data_kringing/1_homogeneity_test_output/` | `3_Homogeneity_Test_Output/*` → here |
| `copy_inputs_for_variogram_cache_builder.bat` | `5_Input_data_kringing/2_Input_for_Variogram_Cache_Builder_data/` | `1_Datas/{rain, station, dem}` → here |
| `copy_inputs_for_build_variogram_cache.bat` | `5_Input_data_kringing/3_Input_for_Build_Varogram_Cache/` | `1_Datas/{rain, station}` → here |
| `copy_inputs_for_run_one_kriging.bat` | `5_Input_data_kringing/4_Input_Run_one_kringing/` | `1_Datas/{rain, station, dem}` → here |
| `copy_inputs_for_batch_kriging.bat` | `5_Input_data_kringing/5_Input_Run_Batch_Kringing/` | `1_Datas/{rain, station, dem}` + `6_Kringing_Output/cache/variogram_cache.csv` → here |
| `copy_netcdf_from_kriging_output.bat` | `8_Input_Data_Zonal_Statistics/` | `6_Kringing_Output/netcdf_out/*.nc` → `netcdf_out/` |
| `copy_csv_from_zonal_statistics.bat` | `11_Input_Files_dfs0/` | `9_Zonal_Statistics_Output/csv_for_netcdf0/*.csv` → `csv_for_netcdf0/` |

All bat files use **relative paths** and work regardless of where the project folder is located on disk. They check that the source folder exists and print a clear error if the upstream step has not been run yet.

---

## 🐍 Environment & Dependencies

All Python scripts run inside the `mikehydro` conda environment:

```bash
conda activate mikehydro
```

| Package | Used In |
|---|---|
| `pandas`, `numpy` | All steps |
| `matplotlib` | Steps 1, 3 |
| `pyhomogeneity` | Step 1 (SNHT test) |
| `scipy` (via kriging engine) | Step 2 (variogram fitting, kriging) |
| `xarray`, `netCDF4` | Step 2 (write NetCDF), Step 3 (read NetCDF) |
| `geopandas`, `rasterio`, `affine` | Step 3 (zonal statistics) |
| `mikeio` | Step 4 (write DFS0) |

---

## ⚠️ Common Issues

| Problem | Likely Cause | Fix |
|---|---|---|
| `rain_2005_2012.csv not found` | Copy bat not run | Run the relevant `copy_*.bat` in the input staging folder |
| `variogram_cache.csv not found` | Step 2a not run yet | Run `3_build_Variogram_cache.bat` in `4_Kringing/` first |
| `No .nc files found` | Copy bat not run | Run `copy_netcdf_from_kriging_output.bat` in `8_Input_Data_Zonal_Statistics/` |
| `Column 'Date' not found` in DFS0 step | Wrong CSV format | Ensure your zonal stats output CSV has a `Date` column |
| `Candidate station not found` | Station ID mismatch | Check CANDIDATE in Step 1 GUI matches a column header in your CSV |
| NetCDF CRS mismatch in zonal stats | Shapefile in wrong projection | Reproject shapefile to **UTM Zone 45N (EPSG:32645)** |
| GUI freezes during processing | Normal — processing runs in background thread | Wait; progress appears in the Process Log box |

---

## 📋 Required File Formats

### `rain_selected_stations.csv` / `rain_2005_2012.csv`
```
Station_ID,909,1030,1036,...,1122
2005-01-01,0.0,0.0,0.0,...,
2005-01-02,0.0,,0.0,...,       <- blank = missing
```

### `station_info.csv`
Must contain at minimum:
- `Station` column — integer IDs matching CSV column headers
- `Easting`, `Northing` columns — UTM Zone 45N coordinates in metres
- `Elevation` column — metres above sea level

### `subbasin_rain.csv` (Zonal Stats output / DFS0 input)
```
Date,Basin_A,Basin_B,...
2005-01-01,3.25,1.80,...
2005-01-02,0.00,0.00,...
```
- `Date` column header is **required** for the DFS0 writer
- Other columns = sub-basin names; each becomes a separate `.dfs0` file
