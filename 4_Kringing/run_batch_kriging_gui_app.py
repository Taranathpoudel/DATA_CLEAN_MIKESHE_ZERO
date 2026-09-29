# -*- coding: utf-8 -*-
"""
Batch Daily Kriging GUI Application

A graphical interface to krige every day of every year in the rainfall record
and write a NetCDF file per year. 
"""

import os
import sys
import time
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
sys.path.append(current_dir) 

try:
    from dem import read_dem
    from projection_utils import load_projected_stations
    from batch_daily_kriging import process_year
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    print(f"Make sure 'dem.py', 'batch_daily_kriging.py', etc., are accessible.")
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


class BatchKrigingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Batch Daily Kriging Tool (All Years)")
        self.geometry("850x700")
        
        # --- Variables with defaults matching the original script ---
        default_station = os.path.join(parent_dir, "station_info.csv")
        default_dem = os.path.join(parent_dir, "demtopo900utm45n.txt")
        default_rain = os.path.join(parent_dir, "rain_2005_2012.csv")
        default_cache = os.path.join(current_dir, "cache", "variogram_cache.csv")
        default_out = os.path.join(current_dir, "netcdf_out")
        
        self.var_station_file = tk.StringVar(value=default_station)
        self.var_dem_file = tk.StringVar(value=default_dem)
        self.var_rain_file = tk.StringVar(value=default_rain)
        self.var_cache_file = tk.StringVar(value=default_cache)
        self.var_output_dir = tk.StringVar(value=default_out)
        
        self.var_time_budget = tk.DoubleVar(value=38.0)
        self.var_start_year = tk.StringVar(value="")
        self.var_end_year = tk.StringVar(value="")
        
        self.setup_ui()
        
        # Redirect standard output to our text box
        sys.stdout = PrintLogger(self.log_text)

    def setup_ui(self):
        # Create Tab Control
        tabControl = ttk.Notebook(self)
        
        self.tab_main = ttk.Frame(tabControl)
        self.tab_desc = ttk.Frame(tabControl)
        
        tabControl.add(self.tab_main, text='Batch Kriging Settings')
        tabControl.add(self.tab_desc, text='Variable Descriptions')
        tabControl.pack(expand=1, fill="both")
        
        self.setup_main_tab()
        self.setup_desc_tab()

    def setup_main_tab(self):
        # --- Input / Output Files Frame ---
        file_frame = ttk.LabelFrame(self.tab_main, text="Input / Output Configuration")
        file_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(file_frame, text="Station File:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_station_file, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.var_station_file, "CSV files", "*.csv")).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(file_frame, text="DEM File:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_dem_file, width=50).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.var_dem_file, "Text files", "*.txt")).grid(row=1, column=2, padx=5, pady=5)

        ttk.Label(file_frame, text="Rain File:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_rain_file, width=50).grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.var_rain_file, "CSV files", "*.csv")).grid(row=2, column=2, padx=5, pady=5)

        ttk.Label(file_frame, text="Variogram Cache:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_cache_file, width=50).grid(row=3, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_file(self.var_cache_file, "CSV files", "*.csv")).grid(row=3, column=2, padx=5, pady=5)

        ttk.Label(file_frame, text="Output Directory:").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.var_output_dir, width=50).grid(row=4, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_dir).grid(row=4, column=2, padx=5, pady=5)

        # --- Parameters Frame ---
        var_frame = ttk.LabelFrame(self.tab_main, text="Calculation Parameters")
        var_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(var_frame, text="Time Budget (Secs):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_time_budget, width=15).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(var_frame, text="Start Year (Optional):").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_start_year, width=15).grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(var_frame, text="End Year (Optional):").grid(row=0, column=4, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_end_year, width=15).grid(row=0, column=5, padx=5, pady=5)

        # Run Button
        self.btn_run = ttk.Button(self.tab_main, text="Run Batch Kriging", command=self.start_analysis)
        self.btn_run.pack(pady=10)

        # Console Log
        ttk.Label(self.tab_main, text="Process Log:").pack(anchor="w", padx=10)
        self.log_text = scrolledtext.ScrolledText(self.tab_main, height=12, state='normal', font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

    def setup_desc_tab(self):
        desc = """
        === Batch Daily Kriging Interpolator ===

        This tool loops through your entire rainfall dataset (e.g. 2005-2012) and 
        applies kriging interpolation across the Digital Elevation Model (DEM) for 
        every single day. It generates a NetCDF file (.nc) for each year processed.

        1. Prerequisites:
        You MUST have already generated the Variogram Cache file using the previous 
        tool. If the Variogram Cache file is missing, this script will stop.

        2. Resumable & Time Budget:
        Kriging thousands of days takes significant processing time. To avoid burning 
        out your CPU or freezing, this tool limits processing to your "Time Budget".
        If a NetCDF output for a year already exists in the Output Directory, the 
        tool simply skips it. You can safely run this tool repeatedly; it will 
        always pick up exactly where it left off.

        3. Start & End Year (Optional):
        If left blank, the tool processes all years found in the rainfall dataset.
        If you enter e.g. Start=2008 and End=2010, it will only process that range.
        """
        lbl = ttk.Label(self.tab_desc, text=desc, justify="left", font=("Consolas", 10))
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
        self.btn_run.config(state="disabled")
        self.log_text.delete(1.0, tk.END)
        print("Starting Batch Kriging Process...")
        
        # Run in a separate thread to keep GUI responsive
        thread = threading.Thread(target=self.process_data)
        thread.daemon = True
        thread.start()

    def process_data(self):
        try:
            # 1. Fetch Variables
            station_file = self.var_station_file.get()
            dem_file = self.var_dem_file.get()
            rain_file = self.var_rain_file.get()
            cache_path = self.var_cache_file.get()
            out_dir = self.var_output_dir.get()
            
            time_budget = self.var_time_budget.get()
            start_year_str = self.var_start_year.get().strip()
            end_year_str = self.var_end_year.get().strip()

            os.makedirs(out_dir, exist_ok=True)

            # 2. Validation
            if not os.path.exists(cache_path):
                raise FileNotFoundError(
                    f"Variogram cache not found at:\n{cache_path}\n"
                    "Please run the Build Variogram Cache Tool first."
                )

            # 3. Load Datasets
            print("Loading Stations...")
            stations = load_projected_stations(station_file)
            
            print("Loading DEM...")
            dem = read_dem(dem_file)
            
            print("Loading Rain Data...")
            rain = pd.read_csv(rain_file, index_col=0, parse_dates=True)
            rain.columns = rain.columns.astype(stations.index.dtype)

            # 4. Filter Years
            all_years = sorted(rain.index.year.unique())
            
            if start_year_str and end_year_str:
                start_year = int(start_year_str)
                end_year = int(end_year_str)
                all_years = [y for y in all_years if start_year <= y <= end_year]
                print(f"Filtered target years: {start_year} to {end_year}")
            else:
                print(f"Targeting all available years: {min(all_years)} to {max(all_years)}")

            # 5. Begin Processing Loop
            print(f"\nStarting calculations with a {time_budget} second limit.")
            t_start = time.time()
            done, skipped = 0, 0

            for year in all_years:
                out_path = os.path.join(out_dir, f"rainfall_kriged_{year}.nc")
                
                if os.path.exists(out_path):
                    print(f"Skipping {year} - file already exists.")
                    skipped += 1
                    continue

                if (time.time() - t_start) > time_budget:
                    print(f"\nTime budget reached after processing {done} year(s) "
                          f"({skipped} already done). Re-run to continue.")
                    messagebox.showinfo("Time Budget Reached", 
                                        f"Paused after processing {done} year(s).\n"
                                        f"Re-run the tool to continue where it left off.")
                    return

                print(f"\n--- Processing Year: {year} ---")
                process_year(year, rain, stations, dem, cache_path=cache_path, out_dir=out_dir)
                done += 1

            # 6. Completion
            print(f"\nAll requested years complete: {done} processed this call, "
                  f"{skipped} were already done.")
            messagebox.showinfo("Complete", "Batch Kriging completed all requested years successfully!")

        except Exception as e:
            print(f"\nERROR: {str(e)}")
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
            
        finally:
            self.btn_run.config(state="normal")


if __name__ == "__main__":
    app = BatchKrigingApp()
    app.mainloop()