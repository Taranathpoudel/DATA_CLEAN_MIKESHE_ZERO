# -*- coding: utf-8 -*-
"""
projection_utils.py

Loads station metadata and returns projected (UTM 45N / EPSG:32645)
coordinates alongside elevation.

Primary path: reuse station_metadata.read_station_metadata (geopandas +
pyproj), exactly as used elsewhere in this project.

Fallback path: if geopandas/pyproj are not installed in the environment
running this script, coordinates are projected with a self-contained
implementation of the standard UTM Transverse Mercator formulas
(WGS84 ellipsoid). This keeps the rest of the Kriging pipeline runnable
even on a machine where geopandas isn't set up, while producing results
that agree with pyproj to within centimetres.
"""

import numpy as np
import pandas as pd

try:
    from station_metadata import read_station_metadata
    _HAVE_GEOPANDAS = True
except Exception:
    _HAVE_GEOPANDAS = False


###############################################################################
# Manual WGS84 -> UTM (fallback, no external deps)
###############################################################################

def _latlon_to_utm(lat_deg, lon_deg, zone=45):
    """
    Standard Snyder/UTM transverse Mercator formulas, WGS84 ellipsoid.
    Vectorised over numpy arrays. Accurate to ~1 cm within a UTM zone.
    """

    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    k0 = 0.9996

    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    lon0 = np.radians(zone * 6 - 183)

    N = a / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    T = np.tan(lat) ** 2
    C = ep2 * np.cos(lat) ** 2
    A = np.cos(lat) * (lon - lon0)

    M = a * (
        (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * lat
        - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * np.sin(2 * lat)
        + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * np.sin(4 * lat)
        - (35 * e2 ** 3 / 3072) * np.sin(6 * lat)
    )

    easting = k0 * N * (
        A + (1 - T + C) * A ** 3 / 6
        + (5 - 18 * T + T ** 2 + 72 * C - 58 * ep2) * A ** 5 / 120
    ) + 500000.0

    northing = k0 * (
        M + N * np.tan(lat) * (
            A ** 2 / 2
            + (5 - T + 9 * C + 4 * C ** 2) * A ** 4 / 24
            + (61 - 58 * T + T ** 2 + 600 * C - 330 * ep2) * A ** 6 / 720
        )
    )

    # Northern hemisphere (Nepal): no false northing offset needed.
    return easting, northing


###############################################################################
# Public loader
###############################################################################

def load_projected_stations(filename, target_crs="EPSG:32645"):
    """
    Read station metadata (Station, X=lon, Y=lat, Z=elevation) and return
    a DataFrame indexed by Station with projected Xp, Yp columns (metres)
    and Z (elevation, m).

    Uses geopandas/pyproj if available; otherwise falls back to a manual
    UTM 45N projection (target_crs is then assumed/forced to EPSG:32645).
    """

    if _HAVE_GEOPANDAS:
        gdf = read_station_metadata(filename, target_crs=target_crs)
        return pd.DataFrame({
            "Xp": gdf["Xp"],
            "Yp": gdf["Yp"],
            "Z": gdf["Z"],
        })

    # ---- fallback ----
    df = pd.read_csv(filename)
    required = ["Station", "X", "Y", "Z"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    easting, northing = _latlon_to_utm(df["Y"].to_numpy(), df["X"].to_numpy())

    out = pd.DataFrame({
        "Station": df["Station"],
        "Xp": easting,
        "Yp": northing,
        "Z": df["Z"].to_numpy(dtype=float),
    }).set_index("Station")

    return out


if __name__ == "__main__":
    df = load_projected_stations("../station_info.csv")
    print("geopandas available:", _HAVE_GEOPANDAS)
    print(df.head())
    print("Xp range:", df.Xp.min(), df.Xp.max())
    print("Yp range:", df.Yp.min(), df.Yp.max())
