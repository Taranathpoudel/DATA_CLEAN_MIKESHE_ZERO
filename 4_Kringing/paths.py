# -*- coding: utf-8 -*-
"""
paths.py (standalone package)

No-op. In kriging_batch_filtered_2026-09-02_pkg, this module inserted
sibling folders (kriging_interpolate_pkg/, kriging_batch_pkg/) onto
sys.path so this package could import their modules without copying them.

In this standalone package every dependency (dem.py, projection_utils.py,
climatology.py, kriging.py, variogram.py, meteo_data.py,
station_metadata.py, plotting.py, netcdf_writer.py, netcdf_reader.py) has
been copied directly into this same folder, so Python's default sys.path
(which always includes the running script's own directory) already finds
them -- no path manipulation is needed. This file is kept only so the
`import paths` line in the other scripts (unchanged, for traceability
against the original package) still works.
"""
