# -*- coding: utf-8 -*-
"""
Variogram Cache Builder GUI Application
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import numpy as np
import pandas as pd

# =============================================================================
# AUTO-PATH RESOLUTION 
# Automatically links the required local Python files from the parent directory.
# =============================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # Should point to 'Day1'
kriging_pkg_dir = os.path.join(parent_dir, "kriging_interpolate_pkg")

sys.path.append(parent_dir)
sys.path.append(kriging_pkg_dir)

try:
    from projection_utils import load_projected_stations
    from climatology import pooled_residual_variogram, pooled_raw_variogram, _calendar_doy
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    print(f"Make sure 'climatology.py', etc., are located in:\n{kriging_pkg_dir}")
    sys.exit(1)
# =============================================================================

CACHE_COLUMNS = [
    "doy", "month", "day",
    "ked_model", "ked_nugget", "ked_sill", "ked_range", "ked_rmse", "ked_n_days",
    "ok_model", "ok_nugget", "ok_sill", "ok_range", "ok_rmse", "ok_n_days",
]


class PrintLogger:
    """Redirects console print statements to the GUI text box."""
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)  
        
    def flush(self):
        pass


class VariogramCacheApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Variogram Cache Builder")
        self.geometry("800x600")
        
        # Default Paths mapped to parent directory
        default_station = os.path.join(parent_dir, "station_info.csv")
        default_rain = os.path.join(parent_dir, "rain_2005_2012.csv")
        default_out = os.path.join(current_dir, "cache", "variogram_cache.csv")
        
        self.var_station_file = tk.StringVar(value=default_station)
        self.var_rain_file = tk.StringVar(value=default_rain)
        self.var_output_csv = tk.StringVar(value=default_out)
        
        self.var_window_days = tk.IntVar(value=7)
        self.var_n_lags = tk.IntVar(value=12)
        self.var_estimator = tk.StringVar(value="matheron")
        self.var_checkpoint = tk.IntVar(value=10)
        
        self.setup_ui()
        sys.stdout = PrintLogger(self.log_text)

    def setup_ui(self):
        tabControl = ttk.Notebook(self)
        self.tab_main = ttk.Frame(tabControl)
        self.tab_desc = ttk.Frame(tabControl)
        
        tabControl.add(self.tab_main, text='Cache Builder Settings')
        tabControl.add(self.tab_desc, text='Variable Descriptions')
        tabControl.pack(expand=1, fill="both")
        
        self.setup_main_tab()
        self.setup_desc_tab()

    def setup_main_tab(self):
        # --- File Selection Frame ---
        file_frame = ttk.LabelFrame(self.tab_main, text="Input / Output Configuration")
        file_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(file_frame, text="Station File:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_station_file, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.var_station_file, "CSV files", "*.csv")).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(file_frame, text="Rain File:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_rain_file, width=50).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.var_rain_file, "CSV files", "*.csv")).grid(row=1, column=2, padx=5, pady=5)

        ttk.Label(file_frame, text="Output Cache CSV:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_output_csv, width=50).grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Save As...", command=self.browse_save_as).grid(row=2, column=2, padx=5, pady=5)

        # --- Parameters Frame ---
        var_frame = ttk.LabelFrame(self.tab_main, text="Calculation Parameters")
        var_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(var_frame, text="Window Days (+/-):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_window_days, width=15).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(var_frame, text="Number of Lags:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_n_lags, width=15).grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(var_frame, text="Estimator Formula:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        combo_est = ttk.Combobox(var_frame, textvariable=self.var_estimator, values=["matheron", "cressie"], width=13, state="readonly")
        combo_est.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(var_frame, text="Checkpoint Every (Days):").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_checkpoint, width=15).grid(row=1, column=3, padx=5, pady=5)

        # Run Button
        self.btn_run = ttk.Button(self.tab_main, text="Build Variogram Cache", command=self.start_analysis)
        self.btn_run.pack(pady=10)

        # Console Log
        ttk.Label(self.tab_main, text="Process Log:").pack(anchor="w", padx=10)
        self.log_text = scrolledtext.ScrolledText(self.tab_main, height=12, state='normal', font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

    def setup_desc_tab(self):
        desc = """
        === Variogram Cache Builder ===

        This tool precomputes the climatological variogram (spherical/exponential fit) 
        for every day of the year (1..365). This is a computationally expensive step 
        but it only needs to be done ONCE. 

        Once built, your daily kriging interpolations can look up the cached values 
        in milliseconds rather than recalculating them from scratch every time.

        1. Station / Rain Files:
        The historical dataset used to pool variances. 'Rain File' contains daily totals,
        while 'Station File' contains the geographical coordinates (X, Y, Z).

        2. Output Cache CSV:
        Where to save the calculated 365 days of parameters.
        **Resumable:** If the calculation is stopped or crashed, running the app again 
        pointing to the *same* Output Cache CSV will pick up exactly where it left off.

        3. Window Days & Lags:
        Window Days sets how many days before/after a given date to pool together 
        (e.g., 7 means a 15-day window). Lags dictate the spatial binning resolution.

        4. Checkpoint Every (Days):
        How often to save progress to the CSV file. If set to 10, the CSV is updated 
        and saved every 10 calculated days.
        """
        lbl = ttk.Label(self.tab_desc, text=desc, justify="left", font=("Consolas", 10))
        lbl.pack(padx=20, pady=20, anchor="nw")

    def browse_file(self, string_var, file_type_name, extension):
        path = filedialog.askopenfilename(filetypes=[(file_type_name, extension), ("All files", "*.*")])
        if path:
            string_var.set(path)

    def browse_save_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if path:
            self.var_output_csv.set(path)

    def start_analysis(self):
        self.btn_run.config(state="disabled")
        print("Initializing Variogram Cache Build...")
        
        thread = threading.Thread(target=self.process_data)
        thread.daemon = True
        thread.start()

    def process_data(self):
        try:
            # 1. Load variables
            station_file = self.var_station_file.get()
            rain_file = self.var_rain_file.get()
            out_csv = self.var_output_csv.get()
            
            window_days = self.var_window_days.get()
            n_lags = self.var_n_lags.get()
            estimator = self.var_estimator.get()
            checkpoint_every = self.var_checkpoint.get()
            
            # Ensure output folder exists
            out_dir = os.path.dirname(out_csv)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

            # 2. Load Data
            print(f"Loading Stations from {station_file}...")
            stations = load_projected_stations(station_file)
            
            print(f"Loading Rain Data from {rain_file}...")
            rain = pd.read_csv(rain_file, index_col=0, parse_dates=True)
            rain.columns = rain.columns.astype(stations.index.dtype)

            # 3. Build logic
            print("\nStarting 365-day Variogram Calculation...")
            print("Note: This is an expensive operation and may take time.")
            
            ref_dates = pd.date_range("2001-01-01", "2001-12-31", freq="D")

            if os.path.exists(out_csv):
                existing = pd.read_csv(out_csv)
                rows = existing.to_dict("records")
                done_doys = set(existing["doy"].tolist())
                print(f"Resuming from existing cache: {len(done_doys)}/365 days already processed.")
            else:
                rows = []
                done_doys = set()

            t_start = time.time()
            n_computed_this_call = 0

            for i, d in enumerate(ref_dates):
                doy = int(_calendar_doy(pd.DatetimeIndex([d]))[0])

                if doy in done_doys:
                    continue

                # KED Calculation
                try:
                    ked = pooled_residual_variogram(
                        rain, stations["Z"], stations["Xp"], stations["Yp"], d,
                        window_days=window_days, n_lags=n_lags, estimator=estimator)
                    ked_fit, ked_n = ked["best_fit"], ked["n_days_used"]
                except Exception as e:
                    print(f"  [doy {doy}] KED fit failed: {e}")
                    ked_fit, ked_n = None, 0

                # OK Calculation
                try:
                    ok = pooled_raw_variogram(
                        rain, stations["Xp"], stations["Yp"], d,
                        window_days=window_days, n_lags=n_lags, estimator=estimator)
                    ok_fit, ok_n = ok["best_fit"], ok["n_days_used"]
                except Exception as e:
                    print(f"  [doy {doy}] OK fit failed: {e}")
                    ok_fit, ok_n = None, 0

                # Log results
                row = {"doy": doy, "month": d.month, "day": d.day, "ked_n_days": ked_n, "ok_n_days": ok_n}
                for prefix, fit in (("ked", ked_fit), ("ok", ok_fit)):
                    for key in ("model", "nugget", "sill", "range", "rmse"):
                        row[f"{prefix}_{key}"] = fit[key] if fit else np.nan
                        
                rows.append(row)
                done_doys.add(doy)
                n_computed_this_call += 1

                # Checkpointing
                if n_computed_this_call % checkpoint_every == 0:
                    elapsed = time.time() - t_start
                    print(f"{len(done_doys)}/365 day-of-year variograms done (doy={doy}, {elapsed:.0f}s elapsed this run)")
                    pd.DataFrame(rows, columns=CACHE_COLUMNS).sort_values("doy").to_csv(out_csv, index=False)

            # Final Save
            if n_computed_this_call > 0:
                df_final = pd.DataFrame(rows, columns=CACHE_COLUMNS).sort_values("doy").reset_index(drop=True)
                df_final.to_csv(out_csv, index=False)
                
            print(f"\n{len(done_doys)}/365 total days calculated.")
            print(f"SUCCESS! Wrote cache file to:\n{os.path.abspath(out_csv)}")
            messagebox.showinfo("Complete", "Variogram Cache successfully built and saved!")

        except Exception as e:
            print(f"\nERROR: {str(e)}")
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
            
        finally:
            self.btn_run.config(state="normal")


# =============================================================================
# EXPORTABLE FUNCTIONS
# Kept intact so this file can still be imported as a module by other scripts.
# =============================================================================

_CACHE_MEMO = {}

def load_doy_cache(path="cache/variogram_cache.csv"):
    if path not in _CACHE_MEMO:
        df = pd.read_csv(path)
        _CACHE_MEMO[path] = df.set_index("doy")
    return _CACHE_MEMO[path]

def get_cached_variogram(date, method, cache_path="cache/variogram_cache.csv"):
    """
    Fetch the precomputed variogram fit for the day-of-year of `date`.
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

if __name__ == "__main__":
    app = VariogramCacheApp()
    app.mainloop()