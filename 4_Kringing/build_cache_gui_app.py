# -*- coding: utf-8 -*-
"""
Build Variogram Cache GUI Application

A graphical interface for the CLI entry point: builds cache/variogram_cache.csv
sourced from the filtered rainfall dataset.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import pandas as pd

# =============================================================================
# AUTO-PATH RESOLUTION 
# Automatically links the required local Python files from the parent directory.
# =============================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # Should point to 'Day1'
kriging_pkg_dir = os.path.join(parent_dir, "kriging_interpolate_pkg")

# Add paths so Python can find your custom modules
sys.path.append(parent_dir)
sys.path.append(kriging_pkg_dir)
sys.path.append(current_dir) # Just in case variogram_cache is in the same folder

try:
    from projection_utils import load_projected_stations
    from variogram_cache import build_doy_cache
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    print(f"Make sure 'projection_utils.py' and 'variogram_cache.py' are accessible.")
    sys.exit(1)
# =============================================================================


class PrintLogger:
    """Redirects console print statements to the GUI text box."""
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)  # Auto-scroll to bottom
        
    def flush(self):
        pass


class BuildCacheApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Build Variogram Cache Tool")
        self.geometry("800x650")
        
        # --- Variables with defaults matching the original script ---
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
        self.var_time_budget = tk.DoubleVar(value=35.0) # From CLI arg
        
        self.setup_ui()
        
        # Redirect standard output to our text box
        sys.stdout = PrintLogger(self.log_text)

    def setup_ui(self):
        # Create Tab Control
        tabControl = ttk.Notebook(self)
        
        self.tab_main = ttk.Frame(tabControl)
        self.tab_desc = ttk.Frame(tabControl)
        
        tabControl.add(self.tab_main, text='Cache Builder Settings')
        tabControl.add(self.tab_desc, text='Variable Descriptions')
        tabControl.pack(expand=1, fill="both")
        
        self.setup_main_tab()
        self.setup_desc_tab()

    def setup_main_tab(self):
        # --- Input / Output Files Frame ---
        file_frame = ttk.LabelFrame(self.tab_main, text="Input / Output Configuration")
        file_frame.pack(fill="x", padx=10, pady=5)

        # Station File
        ttk.Label(file_frame, text="Station File:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_station_file, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.var_station_file, "CSV files", "*.csv")).grid(row=0, column=2, padx=5, pady=5)

        # Rain File
        ttk.Label(file_frame, text="Rain File:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_rain_file, width=50).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.var_rain_file, "CSV files", "*.csv")).grid(row=1, column=2, padx=5, pady=5)

        # Output CSV
        ttk.Label(file_frame, text="Output Cache CSV:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_output_csv, width=50).grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Save As...", command=self.browse_save_as).grid(row=2, column=2, padx=5, pady=5)

        # --- Parameters Frame ---
        var_frame = ttk.LabelFrame(self.tab_main, text="Calculation Parameters")
        var_frame.pack(fill="x", padx=10, pady=5)

        # Row 0
        ttk.Label(var_frame, text="Window Days (+/-):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_window_days, width=15).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(var_frame, text="Number of Lags:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_n_lags, width=15).grid(row=0, column=3, padx=5, pady=5)

        # Row 1
        ttk.Label(var_frame, text="Estimator Formula:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        combo_est = ttk.Combobox(var_frame, textvariable=self.var_estimator, values=["matheron", "cressie"], width=13, state="readonly")
        combo_est.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(var_frame, text="Checkpoint Every (Days):").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_checkpoint, width=15).grid(row=1, column=3, padx=5, pady=5)

        # Row 2 (Time Budget)
        ttk.Label(var_frame, text="Time Budget (Seconds):").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_time_budget, width=15).grid(row=2, column=1, padx=5, pady=5)

        # Run Button
        self.btn_run = ttk.Button(self.tab_main, text="Build Variogram Cache", command=self.start_analysis)
        self.btn_run.pack(pady=10)

        # Console Log
        ttk.Label(self.tab_main, text="Process Log:").pack(anchor="w", padx=10)
        self.log_text = scrolledtext.ScrolledText(self.tab_main, height=12, state='normal', font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

    def setup_desc_tab(self):
        desc = """
        === Variogram Cache Builder (Filtered Rainfall) ===

        This tool computes the climatological variogram from the FILTERED rainfall 
        dataset (instead of the original raw dataset). It replaces the command-line 
        version of `build_variogram_cache.py`.

        1. Time Budget (Seconds):
        This restricts how long the script is allowed to run. If set to 35.0, the script 
        will safely pause and save its progress to the Cache CSV after 35 seconds. 
        You can re-run the app, and it will resume where it left off, allowing you 
        to break a massive job into smaller, manageable chunks.

        2. Checkpoint Every (Days):
        How often to write progress to the hard drive. For example, '10' means 
        the CSV file is updated every 10 calculated days.

        3. Window Days (+/-):
        The moving window size for pulling historical records. A value of 7 means 
        pooling 15 days total (7 before, 7 after, plus the day itself).

        4. Number of Lags / Estimator Formula:
        Settings used to bin distances and fit the semivariogram curve (Matheron 
        is the classical robust estimator; Cressie is less sensitive to outliers).
        """
        lbl = ttk.Label(self.tab_desc, text=desc, justify="left", font=("Consolas", 10))
        lbl.pack(padx=20, pady=20, anchor="nw")

    def browse_file(self, string_var, file_type_name, extension):
        file_path = filedialog.askopenfilename(filetypes=[(file_type_name, extension), ("All files", "*.*")])
        if file_path:
            string_var.set(file_path)

    def browse_save_as(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if file_path:
            self.var_output_csv.set(file_path)

    def start_analysis(self):
        self.btn_run.config(state="disabled")
        print("Starting Cache Build Process...")
        
        # Run in a separate thread so GUI doesn't freeze
        thread = threading.Thread(target=self.process_data)
        thread.daemon = True
        thread.start()

    def process_data(self):
        try:
            # Fetch variables from GUI
            station_file = self.var_station_file.get()
            rain_file = self.var_rain_file.get()
            out_csv = self.var_output_csv.get()
            
            window_days = self.var_window_days.get()
            n_lags = self.var_n_lags.get()
            estimator = self.var_estimator.get()
            checkpoint = self.var_checkpoint.get()
            time_budget = self.var_time_budget.get()

            # Ensure cache directory exists
            out_dir = os.path.dirname(out_csv)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

            print(f"Loading Stations from: {station_file}")
            stations = load_projected_stations(station_file)
            
            print(f"Loading Rain Data from: {rain_file}")
            rain = pd.read_csv(rain_file, index_col=0, parse_dates=True)
            rain.columns = rain.columns.astype(stations.index.dtype)

            print(f"\nBuilding day-of-year variogram cache from FILTERED rainfall...")
            print(f"Parameters: window=+/-{window_days}d, n_lags={n_lags}, estimator={estimator}")
            print(f"Time Budget Limit: {time_budget} seconds.")
            print("-" * 50)
            
            # Flush equivalent - GUI logger auto-updates
            
            # Call the imported cache builder function
            build_doy_cache(
                rain, stations,
                window_days=window_days, 
                n_lags=n_lags, 
                estimator=estimator,
                out_csv=out_csv,
                checkpoint_every=checkpoint,
                time_budget_s=time_budget
            )

            print("-" * 50)
            print("Process finished for this run.")
            messagebox.showinfo("Complete", "Cache building routine finished successfully!\n"
                                "If the time budget ran out, run it again to resume.")

        except Exception as e:
            print(f"\nERROR: {str(e)}")
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
            
        finally:
            self.btn_run.config(state="normal") # Re-enable run button


if __name__ == "__main__":
    app = BuildCacheApp()
    app.mainloop()