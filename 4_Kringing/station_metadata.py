# -*- coding: utf-8 -*-
"""
Created on Jul 2026

@author: dibes
station_metadata.py

Read station coordinates and project them from
WGS84 to a projected coordinate system.
"""


import pandas as pd
import geopandas as gpd

###############################################################################
# Read station metadata
###############################################################################

def read_station_metadata(
        filename,
        target_crs="EPSG:32645",
        source_crs="EPSG:4326"):
    """
    Read station metadata and project coordinates.

    Parameters
    ----------
    filename : str
        CSV, Excel or Pickle file.

    target_crs : str
        Target projected CRS.
        Example:
            "EPSG:32645"

    source_crs : str, optional
        CRS of the input coordinates.
        Default is WGS84 ("EPSG:4326").

    Input file
    ----------
    Station | X | Y | Z

    X : Longitude (degrees)
    Y : Latitude (degrees)
    Z : Elevation (m)

    Returns
    -------
    geopandas.GeoDataFrame
        Index = Station

        Additional columns:
            Xp : Projected X coordinate
            Yp : Projected Y coordinate
    """

    ####################################################################
    # Read file
    ####################################################################

    ext = filename.lower()

    if ext.endswith(".csv"):
        df = pd.read_csv(filename)

    elif ext.endswith((".xls", ".xlsx")):
        df = pd.read_excel(filename)

    elif ext.endswith(".pkl"):
        df = pd.read_pickle(filename)

    else:
        raise ValueError(f"Unsupported file format: {filename}")

    ####################################################################
    # Check required columns
    ####################################################################

    required = ["Station", "X", "Y", "Z"]

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    ####################################################################
    # Create GeoDataFrame
    ####################################################################
    print(df["X"])
    print(df["Y"])
    print(df["Z"])

    gdf = gpd.GeoDataFrame(
        df.copy(),
        geometry=gpd.points_from_xy(
            x=df["X"],
            y=df["Y"]
        ),
        crs=source_crs
    )
    print(gdf.crs)
    print()

    ####################################################################
    # Reproject
    ####################################################################

    gdf = gdf.to_crs(target_crs)

    ####################################################################
    # Store projected coordinates
    ####################################################################

    gdf["Xp"] = gdf.geometry.x
    gdf["Yp"] = gdf.geometry.y

    ####################################################################
    # Set station as index
    ####################################################################

    gdf.set_index("Station", inplace=True)

    ####################################################################
    # Diagnostics
    ####################################################################

    print("\nStation Coordinate Summary")
    print("-------------------------------------")
    print("Source CRS :", source_crs)
    print("Target CRS :", target_crs)

    print("\nOriginal coordinates")
    print(gdf[["X", "Y"]].head())

    print("\nProjected coordinates")
    print(gdf[["Xp", "Yp"]].head())

    print("\nProjected coordinate ranges")
    print(f"Xp : {gdf['Xp'].min():,.2f} -> {gdf['Xp'].max():,.2f}")
    print(f"Yp : {gdf['Yp'].min():,.2f} -> {gdf['Yp'].max():,.2f}")

    return gdf

if __name__ == "__main__":
    testfile = r"E:\ADB_WECS\8_py\data_climate\station_info.csv"
    station_info_test= read_station_metadata(testfile)
    print(station_info_test)