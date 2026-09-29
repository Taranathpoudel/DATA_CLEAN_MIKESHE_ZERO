# -*- coding: utf-8 -*-
"""
Created on Jul 2026

@author: dibes
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

class DEM:
    """
    Read an ESRI ASCII Grid DEM.

    Returns
    -------
    dem.header : dict
    dem.z      : 2D elevation array
    dem.x      : 2D longitude/X coordinates
    dem.y      : 2D latitude/Y coordinates
    dem.df     : DataFrame of X,Y,Z
    """

    def __init__(self, filename):

        self.filename = filename

        self.header = None
        self.z = None
        self.x = None
        self.y = None
        self.df = None

        self.read()


    ###########################################################################
    # Read DEM
    ###########################################################################

    def read(self):

        header = {}

        with open(self.filename, "r") as f:

            # Read first six header lines
            for _ in range(6):

                key, value = f.readline().split()

                header[key.lower()] = float(value)

            # Read elevation values
            z = np.loadtxt(f)

        ncols = int(header["ncols"])
        nrows = int(header["nrows"])

        cellsize = header["cellsize"]

        nodata = header.get("nodata_value", -9999)

        # Convert NoData to NaN
        z = z.astype(float)
        z[z == nodata] = np.nan

        #######################################################################
        # X coordinates
        #######################################################################

        if "xllcorner" in header:

            x0 = header["xllcorner"] + cellsize / 2

        else:

            x0 = header["xllcenter"]

        #######################################################################
        # Y coordinates
        #######################################################################

        if "yllcorner" in header:

            y0 = header["yllcorner"] + cellsize / 2

        else:

            y0 = header["yllcenter"]

        #######################################################################
        # Coordinate vectors
        #######################################################################

        x = x0 + np.arange(ncols) * cellsize

        # ASCII grid starts from top row
        ymax = y0 + (nrows - 1) * cellsize

        y = ymax - np.arange(nrows) * cellsize

        #######################################################################
        # Meshgrid
        #######################################################################

        xx, yy = np.meshgrid(x, y)

        #######################################################################
        # Save
        #######################################################################

        self.header = header

        self.x = xx

        self.y = yy

        self.z = z

        #######################################################################
        # Create DataFrame
        #######################################################################

        self.df = pd.DataFrame({

            "X": xx.ravel(),

            "Y": yy.ravel(),

            "Z": z.ravel()

        })

    def coarsen(self, new_cellsize):
        """
        Coarsen DEM using arithmetic averaging.

        Parameters
        ----------
        new_cellsize : float

            Desired output cell size.

        Returns
        -------
        DEM
            Coarsened DEM.
        """

        ###############################################################
        # Original resolution
        ###############################################################

        old_cellsize = self.header["cellsize"]

        factor = new_cellsize / old_cellsize

        if abs(factor - round(factor)) > 1e-8:

            raise ValueError(
                "new_cellsize must be an integer multiple "
                "of the original cell size."
            )

        factor = int(round(factor))

        ###############################################################
        # Trim to complete blocks
        ###############################################################

        nrows = (self.z.shape[0] // factor) * factor

        ncols = (self.z.shape[1] // factor) * factor

        z = self.z[:nrows, :ncols]

        ###############################################################
        # Average blocks
        ###############################################################

        z = z.reshape(
            nrows // factor,
            factor,
            ncols // factor,
            factor
        )
        ###############################################################
        # Arithmetic mean ignoring NaNs
        ###############################################################

        valid = np.isfinite(z)

        count = np.sum(
            valid,
            axis=(1, 3)
        )

        total = np.nansum(
            z,
            axis=(1, 3)
        )

        z_coarse = np.full(
            count.shape,
            np.nan,
            dtype=float
        )

        good = count > 0

        z_coarse[good] = (
            total[good] /
            count[good]
        )
        # z_coarse = np.nanmean(
        #     z,
        #     axis=(1, 3)
        # )

        ###############################################################
        # New coordinates
        ###############################################################

        x = self.x[:nrows:factor, :ncols:factor]

        y = self.y[:nrows:factor, :ncols:factor]

        offset = (factor - 1) * old_cellsize / 2

        x = x + offset

        y = y - offset

        ###############################################################
        # Create new DEM object
        ###############################################################

        dem = DEM.__new__(DEM)

        dem.filename = self.filename

        dem.header = self.header.copy()

        dem.header["ncols"] = z_coarse.shape[1]

        dem.header["nrows"] = z_coarse.shape[0]

        dem.header["cellsize"] = new_cellsize

        dem.z = z_coarse

        dem.x = x

        dem.y = y

        dem.df = pd.DataFrame({

            "X": x.ravel(),

            "Y": y.ravel(),

            "Z": z_coarse.ravel()

        })

        return dem

    ###########################################################################
    # Write DEM
    ###########################################################################

    def write(self, filename):
        """
        Write DEM to an ESRI ASCII Grid.

        Parameters
        ----------
        filename : str
        """

        nodata = self.header.get(
            "nodata_value",
            -9999
        )

        z = self.z.copy()

        z[np.isnan(z)] = nodata

        ###############################################################
        # Lower-left corner
        ###############################################################

        cellsize = self.header["cellsize"]

        xllcorner = self.x[0, 0] - cellsize / 2

        yllcorner = (
            self.y[-1, 0]
            - cellsize / 2
        )

        ###############################################################
        # Write file
        ###############################################################

        with open(filename, "w") as f:

            f.write(f"ncols         {self.z.shape[1]}\n")

            f.write(f"nrows         {self.z.shape[0]}\n")

            f.write(f"xllcorner     {xllcorner:.6f}\n")

            f.write(f"yllcorner     {yllcorner:.6f}\n")

            f.write(f"cellsize      {cellsize}\n")

            f.write(f"NODATA_value  {nodata}\n")

            np.savetxt(
                f,
                z,
                fmt="%.3f"
            )


###############################################################################
# Utility Function
###############################################################################

def read_dem(filename):
    """
    Read DEM.

    Parameters
    ----------
    filename : str

    Returns
    -------
    dem : DEM class
    """
    return DEM(filename)


###########################################################################
# Coarsen DEM
###########################################################################


if __name__ == "__main__":
    testfile = r"E:\ADB_WECS\8_py\data_climate\demtopo900utm45n.txt"
    dem_test= read_dem(testfile)
    plt.imshow(dem_test.z)
    plt.imshow(dem_test.x)
    plt.imshow(dem_test.y)
    print(dem_test)

    # dem = read_dem(testfile)

    # dem900 = dem.coarsen(900)

    # dem900.write(r"E:\ADB_WECS\8_py\data_climate\demtopo900utm45n.txt")
