# -*- coding: utf-8 -*-
"""
Kriging Filtered GUI Application

A graphical interface for the single-date diagnostic Kriging demo.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for safely saving plots in a GUI
import matplotlib.pyplot as plt

# --- Local Package Imports (Kept exactly as requested) ---
import paths  # noqa: F401
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


class PrintLogger:
    """Redirects console print statements to the GUI text box."""
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)  # Auto-scroll to bottom
        
    def flush(self):
        pass


class KrigingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Filtered Kriging Interpolation Tool")
        self.geometry("850x700")
        
        # Variables with defaults matching the original script
        self.var_dem_file = tk.StringVar(value="../demtopo900utm45n.txt")
        self.var_station_file = tk.StringVar(value="../station_info.csv")
        self.var_rain_file = tk.StringVar(value="../rain_2005_2012.csv")
        self.var_output_dir = tk.StringVar(value="outputs")
        
        self.var_target_date = tk.StringVar(value="2009-07-20")
        self.var_window_days = tk.IntVar(value=7)
        self.var_n_lags = tk.IntVar(value=12)
        self.var_estimator = tk.StringVar(value="matheron")
        self.var_r_threshold = tk.DoubleVar(value=0.3)
        self.var_min_stations = tk.IntVar(value=8)
        
        self.setup_ui()
        
        # Redirect standard output to our text box
        sys.stdout = PrintLogger(self.log_text)

    def setup_ui(self):
        # Create Tab Control
        tabControl = ttk.Notebook(self)
        
        self.tab_main = ttk.Frame(tabControl)
        self.tab_desc = ttk.Frame(tabControl)
        
        tabControl.add(self.tab_main, text='Main Settings & Run')
        tabControl.add(self.tab_desc, text='Variable Descriptions')
        tabControl.pack(expand=1, fill="both")
        
        self.setup_main_tab()
        self.setup_desc_tab()

    def setup_main_tab(self):
        # --- Input / Output Files Frame ---
        file_frame = ttk.LabelFrame(self.tab_main, text="Input / Output Configuration")
        file_frame.pack(fill="x", padx=10, pady=5)

        # DEM File
        ttk.Label(file_frame, text="DEM File:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_dem_file, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.var_dem_file, "Text files", "*.txt")).grid(row=0, column=2, padx=5, pady=5)

        # Station File
        ttk.Label(file_frame, text="Station File:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_station_file, width=50).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.var_station_file, "CSV files", "*.csv")).grid(row=1, column=2, padx=5, pady=5)

        # Rain File
        ttk.Label(file_frame, text="Rain File:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_rain_file, width=50).grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.var_rain_file, "CSV files", "*.csv")).grid(row=2, column=2, padx=5, pady=5)

        # Output Dir
        ttk.Label(file_frame, text="Output Directory:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_output_dir, width=50).grid(row=3, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_dir).grid(row=3, column=2, padx=5, pady=5)

        # --- Parameters Frame ---
        var_frame = ttk.LabelFrame(self.tab_main, text="Kriging Parameters")
        var_frame.pack(fill="x", padx=10, pady=5)

        # Row 0
        ttk.Label(var_frame, text="Target Date (YYYY-MM-DD):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_target_date, width=15).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(var_frame, text="Window Days (+/-):").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_window_days, width=15).grid(row=0, column=3, padx=5, pady=5)

        # Row 1
        ttk.Label(var_frame, text="Number of Lags:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_n_lags, width=15).grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(var_frame, text="Estimator Formula:").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        combo_est = ttk.Combobox(var_frame, textvariable=self.var_estimator, values=["matheron", "cressie"], width=13)
        combo_est.grid(row=1, column=3, padx=5, pady=5)

        # Row 2
        ttk.Label(var_frame, text="R Threshold (Drift):").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_r_threshold, width=15).grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(var_frame, text="Min Stations for Drift:").grid(row=2, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_min_stations, width=15).grid(row=2, column=3, padx=5, pady=5)

        # Run Button
        self.btn_run = ttk.Button(self.tab_main, text="Run Kriging Interpolation", command=self.start_analysis)
        self.btn_run.pack(pady=10)

        # Console Log
        ttk.Label(self.tab_main, text="Process Log:").pack(anchor="w", padx=10)
        self.log_text = scrolledtext.ScrolledText(self.tab_main, height=12, state='normal', font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

    def setup_desc_tab(self):
        desc_text = """
        === Kriging Variable Descriptions ===

        1. DEM / Station / Rain Files:
        Paths to your underlying data. The DEM should be a grid text file. Stations 
        contains projected coordinates (Xp, Yp, Z). Rain contains filtered daily totals.

        2. Target Date (YYYY-MM-DD):
        The specific day you want to run the spatial interpolation and plotting for.
        Must exist within the temporal bounds of your provided rainfall dataset.

        3. Window Days (+/-):
        The script pools data from this many days before and after the Target Date
        (across all years in the record) to compute a robust climatological variogram.
        E.g., 7 means a 15-day window.

        4. Number of Lags:
        The number of distance bins (lags) to group station pairs into when plotting 
        and fitting the experimental semivariogram.

        5. Estimator Formula:
        The mathematical formula used to estimate semivariance. "matheron" is the 
        classical robust estimator. "cressie" is a robust alternative for outliers.

        6. R Threshold (Drift):
        The absolute Pearson correlation threshold between rainfall and elevation. 
        If the correlation is above this threshold, Kriging with External Drift (KED) 
        is used. If it's below, Ordinary Kriging (OK) is used.

        7. Min Stations for Drift:
        The minimum number of valid stations required to even attempt calculating 
        the elevation drift.
        """
        lbl = ttk.Label(self.tab_desc, text=desc_text, justify="left", font=("Consolas", 10))
        lbl.pack(padx=20, pady=20, anchor="nw")

    def browse_file(self, string_var, file_type_name, extension):
        file_path = filedialog.askopenfilename(filetypes=[(file_type_name, extension), ("All files", "*.*")])
        if file_path:
            string_var.set(file_path)

    def browse_dir(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.var_output_dir.set(dir_path)

    def start_analysis(self):
        # Disable button to prevent double-clicking
        self.btn_run.config(state="disabled")
        self.log_text.delete(1.0, tk.END)
        print("Starting Kriging Process...")
        
        # Run process in a thread so the GUI doesn't freeze
        thread = threading.Thread(target=self.process_data)
        thread.daemon = True
        thread.start()

    def process_data(self):
        try:
            # Fetch variables from GUI
            dem_file = self.var_dem_file.get()
            station_file = self.var_station_file.get()
            rain_file = self.var_rain_file.get()
            out_dir = self.var_output_dir.get()
            
            t_date_str = self.var_target_date.get()
            window_days = self.var_window_days.get()
            n_lags = self.var_n_lags.get()
            estimator = self.var_estimator.get()
            r_threshold = self.var_r_threshold.get()
            min_stations = self.var_min_stations.get()

            os.makedirs(out_dir, exist_ok=True)

            print(f"Loading DEM from {dem_file}...")
            dem = read_dem(dem_file)
            
            print(f"Loading Stations from {station_file}...")
            stations = load_projected_stations(station_file)
            
            print(f"Loading Rain Data from {rain_file}...")
            rain = pd.read_csv(rain_file, index_col=0, parse_dates=True)
            rain.columns = rain.columns.astype(stations.index.dtype)

            target_date = pd.Timestamp(t_date_str)
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

            print("Calculating Elevation drift...")
            drift_fit = fit_daily_drift(day, stations["Z"], min_stations=4)
            use_ked = drift_is_significant(
                drift_fit, r_threshold=r_threshold, min_stations=min_stations)

            method = "ked" if use_ked else "ok"
            print(f"Elevation-rainfall correlation r={drift_fit['r']:.3f} "
                  f"(n={drift_fit['n']})  ->  method = {method.upper()}")

            print(f"Building climatological variogram (Window: +/-{window_days} days)...")
            if use_ked:
                vgram = pooled_residual_variogram(
                    rain, stations["Z"], stations["Xp"], stations["Yp"],
                    target_date, window_days=window_days, n_lags=n_lags, estimator=estimator)
            else:
                vgram = pooled_raw_variogram(
                    rain, stations["Xp"], stations["Yp"],
                    target_date, window_days=window_days, n_lags=n_lags, estimator=estimator)

            vfit = vgram["best_fit"]
            print(f"Climatological variogram, filtered dataset ({vgram['n_days_used']} days pooled, "
                  f"window=+/-{window_days}d):\n{vfit}")

            print("Kriging onto the DEM grid...")
            if use_ked:
                zhat, var = external_drift_kriging_predict(
                    x, y, v, z, dem.x, dem.y, dem.z, vfit)
            else:
                zhat, var = ordinary_kriging_predict(x, y, v, dem.x, dem.y, vfit)

            zhat = np.clip(zhat, 0, None)

            print("Performing Leave-one-out cross-validation...")
            cv = leave_one_out_cv(x, y, v, z, vfit, method=method)
            print(f"LOO cross-validation: RMSE={cv['rmse']:.2f} mm  "
                  f"MAE={cv['mae']:.2f} mm  bias={cv['bias']:.2f} mm")

            print("Generating diagnostic plots...")
            fig, axes = plt.subplots(2, 2, figsize=(13, 12))

            plot_drift(stations["Z"], day, drift_fit,
                       title=f"Elevation-rainfall drift on {target_date.date()} (filtered dataset)",
                       ax=axes[0, 0])

            plot_variogram(vgram,
                           title=f"Climatological variogram, filtered dataset (+/-{window_days}d window, "
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

            out_path = os.path.join(out_dir, f"kriging_filtered_{target_date.date()}.png")
            fig.savefig(out_path, dpi=150)
            plt.close(fig) # Free memory safely
            
            print(f"\nSUCCESS! Saved diagnostic figure to:\n{os.path.abspath(out_path)}")
            messagebox.showinfo("Complete", "Kriging Interpolation completed successfully!\nCheck the Output Directory.")

        except Exception as e:
            print(f"\nERROR: {str(e)}")
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
            
        finally:
            self.btn_run.config(state="normal") # Re-enable the run button


if __name__ == "__main__":
    app = KrigingApp()
    app.mainloop()