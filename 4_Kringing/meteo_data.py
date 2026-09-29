# -*- coding: utf-8 -*-
"""
meteo_data.py

Read rainfall or temperature time-series.
"""

import pandas as pd


###############################################################################
# Read meteorological data
###############################################################################

def read_meteo_data(filename):
    """
    Read rainfall or temperature data.

    Parameters
    ----------
    filename : str

    Returns
    -------
    DataFrame

    Index = datetime

    Columns = station names
    """

    #############################################################
    # Read file
    #############################################################

    if filename.lower().endswith(".csv"):

        df = pd.read_csv(

            filename,

            index_col=0,

            parse_dates=True

        )

    elif filename.lower().endswith((".xls", ".xlsx")):

        df = pd.read_excel(

            filename,

            index_col=0

        )

        df.index = pd.to_datetime(df.index)

    elif filename.lower().endswith(".pkl"):

        df = pd.read_pickle(filename)

    else:

        raise ValueError("Unsupported file format.")

    #############################################################
    # Sort by date
    #############################################################

    df = df.sort_index()

    return df


###############################################################################
# Check station names
###############################################################################

def check_station_names(data_df, station_gdf):
    """
    Check whether every station in the data exists
    in the metadata.
    """

    missing = list(

        set(data_df.columns) -

        set(station_gdf.index)

    )

    if len(missing):

        raise ValueError(

            "Stations missing from metadata:\n"

            + "\n".join(sorted(missing))

        )

    return True

if __name__ == "__main__":
    pass