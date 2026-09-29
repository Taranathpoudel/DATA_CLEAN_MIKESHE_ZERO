# -*- coding: utf-8 -*-
"""
CSV to MIKE DFS0 Converter GUI Application
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from pathlib import Path
import pandas as pd
import mikeio


class PrintLogger:
    """Redirects console print statements to the GUI text box."""
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)  # Auto-scroll to bottom
        
    def flush(self):
        pass


class CsvToDfs0App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CSV to MIKE DFS0 Converter")
        self.geometry("750x580") # slightly taller for extra text
        
        # --- Variables with defaults ---
        self.var_input_csv = tk.StringVar(value=os.path.join(os.getcwd(), "subbasin_rain.csv"))
        self.var_output_dir = tk.StringVar(value=os.path.join(os.getcwd(), "rainfall_MIKE"))
        self.var_variable = tk.StringVar(value="rainfall")  # Default dropdown value
        
        self.setup_ui()
        
        # Redirect stdout to text box
        sys.stdout = PrintLogger(self.log_text)

    def setup_ui(self):
        # Tabs
        tabControl = ttk.Notebook(self)
        self.tab_main = ttk.Frame(tabControl)
        self.tab_desc = ttk.Frame(tabControl)
        
        tabControl.add(self.tab_main, text='Converter Settings')
        tabControl.add(self.tab_desc, text='Variable Descriptions')
        tabControl.pack(expand=1, fill="both")
        
        self.setup_main_tab()
        self.setup_desc_tab()

    def setup_main_tab(self):
        # Input / Output Frame
        frame = ttk.LabelFrame(self.tab_main, text="Input / Output Configuration")
        frame.pack(fill="x", padx=10, pady=10)

        # Input CSV
        ttk.Label(frame, text="Input CSV File:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.var_input_csv, width=55).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(frame, text="Browse File", command=self.browse_input_csv).grid(row=0, column=2, padx=5, pady=5)

        # Output Directory
        ttk.Label(frame, text="Output Directory:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.var_output_dir, width=55).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(frame, text="Browse Dir", command=self.browse_output_dir).grid(row=1, column=2, padx=5, pady=5)

        # Variable Type Dropdown (ADDED 'Discharge' HERE)
        ttk.Label(frame, text="Variable Type:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        combo_var = ttk.Combobox(
            frame, 
            textvariable=self.var_variable, 
            values=["rainfall", "temperature", "Evapotranspiration", "Discharge"], 
            state="readonly",
            width=25
        )
        combo_var.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        # Run Button
        self.btn_run = ttk.Button(self.tab_main, text="Convert to DFS0", command=self.start_conversion)
        self.btn_run.pack(pady=10)

        # Process Log Console
        ttk.Label(self.tab_main, text="Process Log:").pack(anchor="w", padx=10)
        self.log_text = scrolledtext.ScrolledText(self.tab_main, height=12, state='normal', font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

    def setup_desc_tab(self):
        desc = """
        === Variables & Inputs Descriptions ===

        1. Input CSV File:
        The path to your time series data in CSV format. 
        IMPORTANT: Your CSV file MUST have a column named "Date". All other columns 
        will be treated as individual sub-basins (or stations).

        2. Output Directory:
        The folder where all the newly created MIKE .dfs0 files will be saved. 

        3. Variable Type:
        This dictates how the data is written into the MIKE DFS0 file using the EUM.

        -> 'rainfall'
           Sets EUM Type to Rainfall (Unit: millimeters).
           Data Value Type: "StepAccumulated".

        -> 'temperature'
           Sets EUM Type to Temperature (Unit: degree_Celsius).
           Data Value Type: "Instantaneous".

        -> 'Evapotranspiration'
           Sets EUM Type to Evaporation (Unit: millimeters).
           Data Value Type: "StepAccumulated".

        -> 'Discharge'
           Sets EUM Type to Discharge (Unit: cubic meters per second / m³/s).
           Data Value Type: "Instantaneous".
        """
        lbl = ttk.Label(self.tab_desc, text=desc, justify="left", font=("Consolas", 10))
        lbl.pack(padx=20, pady=20, anchor="nw")

    def browse_input_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            self.var_input_csv.set(path)

    def browse_output_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.var_output_dir.set(path)

    def start_conversion(self):
        # Validate inputs
        if not self.var_input_csv.get():
            messagebox.showerror("Error", "Please select an Input CSV file.")
            return
            
        if not self.var_output_dir.get():
            messagebox.showerror("Error", "Please select an Output Directory.")
            return

        # Disable run button during processing
        self.btn_run.config(state="disabled")
        self.log_text.delete(1.0, tk.END)
        print("Starting CSV to DFS0 conversion...")
        
        # Run conversion in background thread to prevent UI freezing
        thread = threading.Thread(target=self.process_data)
        thread.daemon = True
        thread.start()

    def process_data(self):
        try:
            # Fetch variables from the GUI
            input_csv = self.var_input_csv.get()
            output_dir = Path(self.var_output_dir.get())
            variable = self.var_variable.get()

            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)

            print(f"Reading CSV file: {input_csv}...")
            df = pd.read_csv(input_csv)

            if "Date" not in df.columns:
                raise ValueError("The CSV file MUST contain a column named 'Date'.")

            # Format Date and index
            print("Formatting Datetime index...")
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date").sort_index()

            print(f"Creating DFS0 files for variable: {variable}")
            
            # Loop through each subbasin column
            for subbasin in df.columns:
                ts = df[subbasin]

                # Create MIKE DataArray based on the selected variable
                if variable == "temperature":
                    da = mikeio.DataArray(
                        ts.values,
                        time=ts.index,
                        item=mikeio.ItemInfo(
                            subbasin,
                            mikeio.EUMType.Temperature,
                            mikeio.EUMUnit.degree_Celsius,
                            data_value_type="Instantaneous"
                        )
                    )
                elif variable == "rainfall":
                    da = mikeio.DataArray(
                        ts.values,
                        time=ts.index,
                        item=mikeio.ItemInfo(
                            subbasin,
                            mikeio.EUMType.Rainfall,
                            mikeio.EUMUnit.millimeter,
                            data_value_type="StepAccumulated",
                        )
                    )
                elif variable == "Evapotranspiration":
                    da = mikeio.DataArray(
                        ts.values,
                        time=ts.index,
                        item=mikeio.ItemInfo(
                            subbasin,
                            mikeio.EUMType.Evaporation,
                            mikeio.EUMUnit.millimeter,
                            data_value_type="StepAccumulated",
                        )
                    )
                # --- NEW DISCHARGE BLOCK ADDED HERE ---
                elif variable == "Discharge":
                    da = mikeio.DataArray(
                        ts.values,
                        time=ts.index,
                        item=mikeio.ItemInfo(
                            subbasin,
                            mikeio.EUMType.Discharge,
                            mikeio.EUMUnit.meter_pow_3_per_sec,
                            data_value_type="Instantaneous",
                        )
                    )

                # Output filename
                output_file = output_dir / f"{subbasin}.dfs0"

                # Write DFS0
                da.to_dfs(str(output_file))
                print(f"Created: {output_file.name}")

            print(f"\nSUCCESS! All DFS0 files generated in:\n{output_dir.absolute()}")
            messagebox.showinfo("Complete", "DFS0 conversion completed successfully!")

        except Exception as e:
            print(f"\nERROR: {str(e)}")
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
            
        finally:
            self.btn_run.config(state="normal")


if __name__ == "__main__":
    app = CsvToDfs0App()
    app.mainloop()