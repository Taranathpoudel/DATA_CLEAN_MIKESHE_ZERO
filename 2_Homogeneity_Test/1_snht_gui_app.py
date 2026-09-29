# -*- coding: utf-8 -*-
"""
SNHT PyHomogeneity GUI Application
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg') # Use non-interactive backend for saving plots in a GUI
import matplotlib.pyplot as plt
import pyhomogeneity as hg

class PrintLogger:
    """Utility class to redirect print statements to the GUI text box."""
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END) # Auto-scroll to bottom
        
    def flush(self):
        pass

class SNHTApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Rainfall Homogeneity Tester (SNHT)")
        self.geometry("750x600")
        
        # Variables with defaults
        self.var_input = tk.StringVar(value="")
        self.var_output = tk.StringVar(value=os.path.join(os.getcwd(), "snht_output"))
        self.var_alpha = tk.DoubleVar(value=0.05)
        self.var_min_days = tk.IntVar(value=330)
        self.var_sim = tk.IntVar(value=20000)
        self.var_candidate = tk.StringVar(value="1030")
        
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
        frame = ttk.LabelFrame(self.tab_main, text="Input / Output Configuration")
        frame.pack(fill="x", padx=10, pady=10)

        # Input CSV
        ttk.Label(frame, text="Input CSV File:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.var_input, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(frame, text="Browse", command=self.browse_input).grid(row=0, column=2, padx=5, pady=5)

        # Output Dir
        ttk.Label(frame, text="Output Directory:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.var_output, width=50).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(frame, text="Browse", command=self.browse_output).grid(row=1, column=2, padx=5, pady=5)

        # Variables Frame
        var_frame = ttk.LabelFrame(self.tab_main, text="Test Parameters")
        var_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(var_frame, text="ALPHA (Significance Level):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_alpha, width=15).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(var_frame, text="MIN_DAYS (Days/Year):").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_min_days, width=15).grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(var_frame, text="SIM (Monte Carlo Sims):").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_sim, width=15).grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(var_frame, text="CANDIDATE (Station ID):").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(var_frame, textvariable=self.var_candidate, width=15).grid(row=1, column=3, padx=5, pady=5)

        # Run Button
        self.btn_run = ttk.Button(self.tab_main, text="Run Analysis", command=self.start_analysis)
        self.btn_run.pack(pady=10)

        # Console Log
        ttk.Label(self.tab_main, text="Process Log:").pack(anchor="w", padx=10)
        self.log_text = scrolledtext.ScrolledText(self.tab_main, height=12, state='normal')
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

    def setup_desc_tab(self):
        desc_text = """
        === Variable Descriptions ===

        1. Input CSV File: 
        The path to your daily rainfall data file in CSV format. The first column 
        must contain dates, and subsequent columns represent station IDs.

        2. Output Directory:
        The folder where all the generated graphs (.png) and result tables (.csv, .txt) 
        will be saved. It will be created automatically if it doesn't exist.

        3. ALPHA (Significance Level):
        The probability of rejecting the null hypothesis when it is true. 
        Default is 0.05 (representing a 95% confidence interval).

        4. MIN_DAYS:
        The minimum number of recorded daily data points required to consider 
        a year 'complete'. If a year has fewer days than this, it's dropped. 
        Default is 330 (~90% of the year).

        5. SIM (Simulations):
        The number of Monte Carlo simulations run by pyhomogeneity to calculate 
        the p-value. Higher numbers are more accurate but take longer. 
        Default is 20000.

        6. CANDIDATE (Station ID):
        The specific station you want to analyze for relative homogeneity. 
        The script builds a reference from its neighbors to see if changes 
        are regional or specific to this single station.
        """
        lbl = ttk.Label(self.tab_desc, text=desc_text, justify="left", font=("Consolas", 10))
        lbl.pack(padx=20, pady=20, anchor="nw")

    def browse_input(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if file_path:
            self.var_input.set(file_path)

    def browse_output(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.var_output.set(dir_path)

    def start_analysis(self):
        if not self.var_input.get():
            messagebox.showerror("Error", "Please select an Input CSV file.")
            return

        # Disable button to prevent multiple clicks
        self.btn_run.config(state="disabled")
        self.log_text.delete(1.0, tk.END)
        print("Starting analysis... Please wait.")
        
        # Run in a separate thread so GUI doesn't freeze
        thread = threading.Thread(target=self.process_data)
        thread.daemon = True
        thread.start()

    def run_snht(self, series, alpha, sim):
        """Run pyhomogeneity SNHT on an annual series (index = year)."""
        s = series.dropna()
        if len(s) < 5: 
            return None # Skip if too little data
            
        res = hg.snht_test(s.values, alpha=alpha, sim=sim)
        years = s.index.to_numpy()
        return {
            "n_years": len(s),
            "T": res.T,
            "p_value": res.p,
            "inhomogeneous": bool(res.h),
            "last_year_before_break": int(years[res.cp - 1]),
            "break_year": int(years[res.cp]),
            "mean_before": res.avg.mu1,
            "mean_after": res.avg.mu2,
        }

    def process_data(self):
        try:
            # Fetch variables
            input_csv = self.var_input.get()
            out_dir = self.var_output.get()
            alpha = self.var_alpha.get()
            min_days = self.var_min_days.get()
            sim = self.var_sim.get()
            candidate = self.var_candidate.get()

            np.random.seed(42)
            os.makedirs(out_dir, exist_ok=True)

            print(f"Reading data from {input_csv}...")
            daily = pd.read_csv(input_csv, index_col=0)
            daily = daily[daily.index.notna()]
            daily.index = pd.to_datetime(daily.index)
            
            # Ensure column names (station IDs) are strings
            daily.columns = daily.columns.astype(str)

            print("Calculating annual totals...")
            by_year = daily.groupby(daily.index.year)
            annual = by_year.sum(min_count=1)
            n_days = by_year.count()
            annual = annual.where(n_days >= min_days)
            annual.index.name = "Year"

            if candidate not in annual.columns:
                raise ValueError(f"Candidate station '{candidate}' not found in the dataset headers.")

            print("\nRunning SNHT test on each station...")
            snht_results = {}
            for st in annual.columns:
                res = self.run_snht(annual[st], alpha, sim)
                if res:
                    snht_results[st] = res
                    
            snht = pd.DataFrame(snht_results).T
            snht.index.name = "Station"
            print("Completed Absolute SNHT Tests.")

            print("\nGenerating absolute plots...")
            stations = list(annual.columns)
            fig, axes = plt.subplots(len(stations), 1, figsize=(10, 2.3 * len(stations)), sharex=True)
            if len(stations) == 1: axes = [axes] # Handle single station case
            
            for ax, st in zip(axes, stations):
                if st not in snht.index: continue
                r = snht.loc[st]
                s = annual[st].dropna()
                color = "red" if r["inhomogeneous"] else "tab:blue"
                ax.plot(s.index, s.values, "o-", color="gray", ms=3, lw=1)
                ax.hlines(r["mean_before"], s.index.min(), r["break_year"] - 0.5, color=color, lw=2)
                ax.hlines(r["mean_after"], r["break_year"] - 0.5, s.index.max(), color=color, lw=2)
                ax.axvline(r["break_year"] - 0.5, color=color, ls="--")
                status = "INHOMOGENEOUS" if r["inhomogeneous"] else "homogeneous"
                ax.set_title(f"Station {st}: break {r['break_year']}, p = {r['p_value']:.3f} ({status})",
                             fontsize=9, color=color)
                ax.set_ylabel("mm/yr")
                
            axes[-1].set_xlabel("Year")
            fig.suptitle("SNHT test on annual rainfall (lines = mean before/after break)")
            fig.tight_layout()
            fig.savefig(os.path.join(out_dir, "B1_snht_all_stations.png"), dpi=150)
            plt.close(fig)

            print("\nRunning Relative Homogeneity test...")
            neighbours = [st for st in annual.columns if st != candidate]
            
            if not neighbours:
                print("No neighbours found. Skipping relative homogeneity tests.")
            else:
                norm = annual / annual.mean()
                corr = annual.corr()[candidate][neighbours]
                
                weights = corr.clip(lower=0)
                w_present = norm[neighbours].notna().mul(weights, axis=1).sum(axis=1)
                reference = norm[neighbours].mul(weights, axis=1).sum(axis=1) / w_present
                reference[norm[neighbours].notna().sum(axis=1) < 2] = np.nan
                
                ratio = (norm[candidate] / reference).rename("ratio")
                rel = self.run_snht(ratio, alpha, sim)
                abs_res = snht.loc[candidate]
                
                if not rel["inhomogeneous"]:
                    verdict = "Homogeneous relative to neighbours -> absolute break is likely regional/climatic"
                elif abs(rel["break_year"] - abs_res["break_year"]) <= 3:
                    verdict = "Break also found relative to neighbours -> likely a station-specific problem"
                else:
                    verdict = "Relative break found in a different year -> inspect station history"

                print(f"Verdict for {candidate}: {verdict}")

                # Plot D
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
                ax1.plot(norm.index, norm[candidate], "o-", label=f"Station {candidate}")
                ax1.plot(reference.index, reference, "s-", label="Neighbour reference")
                ax1.axhline(1, color="gray", lw=0.8)
                ax1.axvline(abs_res["break_year"] - 0.5, color="red", ls="--",
                            label=f"Absolute SNHT break {abs_res['break_year']} (p={abs_res['p_value']:.3f})")
                ax1.set_ylabel("Annual rain / long-term mean")
                ax1.set_title(f"Station {candidate} vs neighbours ({', '.join(neighbours)})")
                ax1.legend(fontsize=8)

                r_vals = ratio.dropna()
                ax2.bar(r_vals.index, r_vals.values - 1, bottom=1, color="gray")
                bp = rel["break_year"] - 0.5
                ax2.hlines(rel["mean_before"], r_vals.index.min() - 0.5, bp, color="k", lw=2)
                ax2.hlines(rel["mean_after"], bp, r_vals.index.max() + 0.5, color="k", lw=2)
                ax2.axvline(bp, color="k", ls="--")
                ax2.set_ylabel("Ratio (station / reference)")
                ax2.set_xlabel("Year")
                ax2.set_title(f"Relative SNHT: break {rel['break_year']}, p = {rel['p_value']:.3f}\n{verdict}",
                              fontsize=9)
                fig.tight_layout()
                fig.savefig(os.path.join(out_dir, f"D_relative_homogeneity_{candidate}.png"), dpi=150)
                plt.close(fig)

                # Save Data
                rel_table = pd.DataFrame({
                    f"station_{candidate}_normalised": norm[candidate],
                    "neighbour_reference": reference,
                    "ratio": ratio,
                })
                rel_table.to_csv(os.path.join(out_dir, f"C_relative_series_{candidate}.csv"), float_format="%.3f")

                with open(os.path.join(out_dir, f"C_relative_result_{candidate}.txt"), "w") as f:
                    f.write(f"Relative homogeneity test for station {candidate}\n")
                    f.write(f"Neighbours: {', '.join(neighbours)}\n")
                    f.write("Correlations: " + ", ".join(f"{k}={v:.2f}" for k, v in corr.items()) + "\n\n")
                    f.write("Absolute SNHT: break {}, p = {:.4f}\n".format(abs_res["break_year"], abs_res["p_value"]))
                    f.write("Relative SNHT: break {}, p = {:.4f}\n".format(rel["break_year"], rel["p_value"]))
                    f.write(f"Verdict: {verdict}\n")

            # Final Output Savings
            annual.to_csv(os.path.join(out_dir, "A_annual_totals.csv"), float_format="%.1f")
            snht.to_csv(os.path.join(out_dir, "B_snht_results.csv"))
            
            print(f"\nSUCCESS! All outputs written to:\n{os.path.abspath(out_dir)}")
            messagebox.showinfo("Complete", "Analysis completed successfully!")

        except Exception as e:
            print(f"\nERROR: {str(e)}")
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
            
        finally:
            self.btn_run.config(state="normal") # Re-enable run button


if __name__ == "__main__":
    app = SNHTApp()
    app.mainloop()