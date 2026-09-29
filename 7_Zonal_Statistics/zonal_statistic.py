# -*- coding: utf-8 -*-
"""
Zonal Statistics NetCDF to CSV GUI Application
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr
from rasterio.features import geometry_mask
from affine import Affine

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for safely saving plots in a GUI
import matplotlib.pyplot as plt


class PrintLogger:
    """Redirects console print statements to the GUI text box."""
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)  # Auto-scroll to bottom
        
    def flush(self):
        pass


class ZonalStatistics:
    """
    Compute zonal statistics from a NetCDF raster.
    Statistics are calculated for every polygon and every timestep.
    """
    def __init__(self, netcdf_file, shapefile, polygon_field):
        self.netcdf_file = netcdf_file
        self.shapefile = shapefile
        self.polygon_field = polygon_field

        # Read NetCDF
        self.ds = xr.open_dataset(netcdf_file)
        
        # Variable name (assume first data variable)
        self.variable = list(self.ds.data_vars)[0]

        # Coordinates
        self.x = self.ds.x.values
        self.y = self.ds.y.values

        # Read polygons
        self.gdf = gpd.read_file(shapefile)

        # Affine transform
        dx = self.x[1] - self.x[0]
        dy = self.y[0] - self.y[1]
        self.transform = Affine(
            dx, 0, self.x.min() - dx / 2,
            0, -dy, self.y.max() + dy / 2
        )

        # Precompute masks
        self._build_masks()

    def _build_masks(self):
        """Rasterize polygons into boolean masks."""
        self.masks = {}
        shape = (len(self.y), len(self.x))

        for _, row in self.gdf.iterrows():
            mask = geometry_mask(
                [row.geometry],
                transform=self.transform,
                invert=True,
                out_shape=shape
            )
            self.masks[row[self.polygon_field]] = mask

        print(f"Loaded {len(self.masks)} polygons from shapefile.")

    def mean(self):
        """
        Mean value for every polygon and every time.
        If all raster values within a basin are NaN for a given date,
        the result is set to NaN and the date and basin are reported.
        """
        data = self.ds[self.variable]
        results = []

        for t in range(data.sizes["time"]):
            raster = data.isel(time=t).values
            date = pd.Timestamp(data.time.values[t])
            record = {"Date": date}

            for basin, mask in self.masks.items():
                values = raster[mask]
                
                # Check for completely missing data
                valid_values = values[~np.isnan(values)]

                if len(valid_values) == 0:
                    print(f"WARNING: No valid data | Date: {date.strftime('%Y-%m-%d')} | Basin: {basin} | Valid pixels: 0")
                    record[basin] = np.nan
                else:
                    record[basin] = np.nanmean(values)

            results.append(record)

        return pd.DataFrame(results)


class ZonalStatsApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NetCDF Zonal Statistics Extractor")
        self.geometry("850x650")
        
        # --- Variables with defaults ---
        self.var_nc_folder = tk.StringVar(value=os.path.join(os.getcwd(), "Data", "rainfall"))
        self.var_shapefile = tk.StringVar(value=os.path.join(os.getcwd(), "Catchment.shp"))
        self.var_output_csv = tk.StringVar(value=os.path.join(os.getcwd(), "outputs", "basin_rainfall.csv"))
        self.var_polygon_field = tk.StringVar(value="Cat_Name")
        
        self.setup_ui()
        
        # Redirect stdout to text box
        sys.stdout = PrintLogger(self.log_text)

    def setup_ui(self):
        # Tabs
        tabControl = ttk.Notebook(self)
        self.tab_main = ttk.Frame(tabControl)
        self.tab_desc = ttk.Frame(tabControl)
        
        tabControl.add(self.tab_main, text='Run Extraction')
        tabControl.add(self.tab_desc, text='Variable Descriptions')
        tabControl.pack(expand=1, fill="both")
        
        self.setup_main_tab()
        self.setup_desc_tab()

    def setup_main_tab(self):
        frame = ttk.LabelFrame(self.tab_main, text="Input / Output Configuration")
        frame.pack(fill="x", padx=10, pady=10)

        # NetCDF Folder
        ttk.Label(frame, text="NetCDF Folder:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.var_nc_folder, width=60).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(frame, text="Browse Dir", command=self.browse_nc_folder).grid(row=0, column=2, padx=5, pady=5)

        # Shapefile
        ttk.Label(frame, text="Shapefile (.shp):").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.var_shapefile, width=60).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(frame, text="Browse File", command=self.browse_shapefile).grid(row=1, column=2, padx=5, pady=5)

        # Output CSV
        ttk.Label(frame, text="Output CSV:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.var_output_csv, width=60).grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(frame, text="Save As...", command=self.browse_output_csv).grid(row=2, column=2, padx=5, pady=5)

        # Polygon Field
        ttk.Label(frame, text="Polygon Field (e.g., Cat_Name):").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.var_polygon_field, width=20).grid(row=3, column=1, sticky="w", padx=5, pady=5)

        # Run Button
        self.btn_run = ttk.Button(self.tab_main, text="Run Zonal Statistics", command=self.start_analysis)
        self.btn_run.pack(pady=10)

        # Log
        ttk.Label(self.tab_main, text="Process Log:").pack(anchor="w", padx=10)
        self.log_text = scrolledtext.ScrolledText(self.tab_main, height=15, state='normal', font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

    def setup_desc_tab(self):
        desc = """
        === Variables & Inputs Descriptions ===

        1. NetCDF Folder:
        The directory containing your yearly (or daily/monthly) `.nc` files. The 
        tool will scan this folder for all files ending in '.nc' and process them 
        in chronological order.

        2. Shapefile (.shp):
        The geospatial vector file containing your catchment or sub-basin polygons. 
        It MUST be in the same Coordinate Reference System (CRS) as the NetCDF grids.

        3. Output CSV:
        The file path where the merged tabular data will be saved. The application 
        will also generate two plots (Annual & Monthly) and save them as PNG images 
        in the exact same directory as this CSV file.

        4. Polygon Field:
        The attribute column inside your Shapefile that contains the names or IDs 
        of your sub-basins. For example, if your shapefile's attribute table has a 
        column called "Cat_Name", enter "Cat_Name" here. This will be used as the 
        column headers in the final Output CSV.
        """
        lbl = ttk.Label(self.tab_desc, text=desc, justify="left", font=("Consolas", 10))
        lbl.pack(padx=20, pady=20, anchor="nw")

    def browse_nc_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.var_nc_folder.set(path)

    def browse_shapefile(self):
        path = filedialog.askopenfilename(filetypes=[("Shapefiles", "*.shp"), ("All files", "*.*")])
        if path:
            self.var_shapefile.set(path)

    def browse_output_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if path:
            self.var_output_csv.set(path)

    def start_analysis(self):
        self.btn_run.config(state="disabled")
        self.log_text.delete(1.0, tk.END)
        print("Starting Zonal Statistics Extraction...")
        
        # Run in background thread
        thread = threading.Thread(target=self.process_data)
        thread.daemon = True
        thread.start()

    def process_data(self):
        try:
            nc_folder = Path(self.var_nc_folder.get())
            shape_file = self.var_shapefile.get()
            out_csv = self.var_output_csv.get()
            poly_field = self.var_polygon_field.get()
            
            # Ensure output directory exists
            out_dir = os.path.dirname(out_csv)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

            nc_files = sorted(nc_folder.glob("*.nc"))
            if not nc_files:
                raise FileNotFoundError(f"No .nc files found in {nc_folder}")

            all_var = []
            print(f"Found {len(nc_files)} NetCDF files. Processing...")

            for netcdf_file in nc_files:
                print(f"\nProcessing: {netcdf_file.name}")
                zs = ZonalStatistics(
                    netcdf_file=str(netcdf_file),
                    shapefile=shape_file,
                    polygon_field=poly_field
                )
                
                var = zs.mean()
                var.index = pd.to_datetime(var['Date'])
                var.drop("Date", axis=1, inplace=True)
                all_var.append(var)

            print("\nCombining all years...")
            var_df = pd.concat(all_var)
            var_df = var_df.sort_index()

            print("Applying filter (values <= 0.1 set to 0) and rounding...")
            var_df[var_df <= 0.1] = 0
            var_df = var_df.round(2)

            print("\nPreview of extracted data:")
            print(var_df.head())

            var_df.to_csv(out_csv, index=True, index_label="Date")
            print(f"\nData successfully saved to: {out_csv}")

            # ---------------------------------------------------------
            # Generate and Save Plots automatically
            # ---------------------------------------------------------
            print("Generating diagnostic plots...")
            
            # 1. Annual Plot
            rainfall_annual = var_df.groupby(var_df.index.year).sum()
            rainfall_annual = np.ceil(rainfall_annual)
            
            fig1, ax1 = plt.subplots(figsize=(12, 6))
            rainfall_annual.plot(ax=ax1, marker='o')
            ax1.set_title("Annual Sum per Sub-basin")
            ax1.set_ylabel("Value / Rainfall")
            ax1.set_xlabel("Year")
            ax1.grid(True, linestyle='--', alpha=0.6)
            fig1.tight_layout()
            
            plot1_path = os.path.join(out_dir, "annual_summary_plot.png")
            fig1.savefig(plot1_path, dpi=150)
            plt.close(fig1)

            # 2. Monthly Climatology Plot
            rainfall_monthly = var_df.groupby(by=[var_df.index.year, var_df.index.month]).sum().groupby(level=1).mean()
            
            fig2, ax2 = plt.subplots(figsize=(12, 6))
            rainfall_monthly.plot(ax=ax2, marker='s')
            ax2.set_title("Mean Monthly Climatology per Sub-basin")
            ax2.set_ylabel("Average Value / Rainfall")
            ax2.set_xlabel("Month")
            ax2.set_xticks(range(1, 13))
            ax2.grid(True, linestyle='--', alpha=0.6)
            fig2.tight_layout()
            
            plot2_path = os.path.join(out_dir, "monthly_climatology_plot.png")
            fig2.savefig(plot2_path, dpi=150)
            plt.close(fig2)
            
            print(f"Plots saved:\n -> {plot1_path}\n -> {plot2_path}")
            
            messagebox.showinfo("Complete", "Zonal Statistics successfully calculated and exported!")

        except Exception as e:
            print(f"\nERROR: {str(e)}")
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
            
        finally:
            self.btn_run.config(state="normal")


if __name__ == "__main__":
    app = ZonalStatsApp()
    app.mainloop()