# -*- coding: utf-8 -*-
"""
netcdf_writer.py

Writes gridded daily rainfall (+ kriging variance) time series to NetCDF.

Uses the `netCDF4` package if it's installed (preferred: robust,
compressed, full CF support). If it isn't available, falls back to a
small self-contained NetCDF3 "classic" format writer implemented here
directly from the file-format specification (no external dependency) --
NetCDF3 classic files are readable by netCDF4, xarray, GDAL, QGIS, CDO,
Panoply, etc.

Only what this project needs is implemented: a handful of named
dimensions (one of which may be an unlimited "record"/time dimension),
float32/float64/int32 variables, and simple global/variable attributes.
"""

import os
import struct
import numpy as np

try:
    import netCDF4 as _netCDF4
    _HAVE_NETCDF4 = True
except Exception:
    _HAVE_NETCDF4 = False


###############################################################################
# Public entry point
###############################################################################

def write_year_netcdf(
        filename,
        time_days, time_units,
        x, y, crs_wkt,
        variables,
        global_attrs=None):
    """
    Write one year's worth of gridded daily fields to a NetCDF file.

    Parameters
    ----------
    filename : str
    time_days : 1D int array, length n_time (the record dimension)
    time_units : str, e.g. "days since 1980-01-01"
    x, y : 1D coordinate arrays (projected metres), length nx, ny
    crs_wkt : str, well-known text of the projected CRS (stored as an
        attribute for reference; not a full CF grid_mapping variable)
    variables : dict of name -> dict(data=array, dims=("time","y","x") or
        ("time",), long_name=..., units=..., fill_value=...)
        Arrays with a leading "time" dim must have length n_time.
    global_attrs : dict, optional
    """

    # Write to a temp path and rename into place at the end, so a run that
    # gets interrupted mid-write (e.g. a wall-clock cutoff) never leaves a
    # partial file sitting at `filename` that a resume check would
    # mistake for a completed, valid file.
    tmp_filename = filename + ".tmp"
    try:
        if _HAVE_NETCDF4:
            _write_with_netCDF4(tmp_filename, time_days, time_units, x, y, crs_wkt,
                                 variables, global_attrs)
        else:
            _write_netcdf3_classic(tmp_filename, time_days, time_units, x, y, crs_wkt,
                                    variables, global_attrs)
        os.replace(tmp_filename, filename)
    except BaseException:
        if os.path.exists(tmp_filename):
            os.remove(tmp_filename)
        raise


def _write_with_netCDF4(filename, time_days, time_units, x, y, crs_wkt,
                         variables, global_attrs):
    ds = _netCDF4.Dataset(filename, "w", format="NETCDF4_CLASSIC")
    try:
        ds.createDimension("time", None)
        ds.createDimension("y", len(y))
        ds.createDimension("x", len(x))

        v = ds.createVariable("time", "i4", ("time",))
        v.units = time_units
        v.long_name = "time"
        v[:] = np.asarray(time_days, dtype="i4")

        vx = ds.createVariable("x", "f8", ("x",))
        vx.units = "m"
        vx.long_name = "projected easting"
        vx[:] = np.asarray(x, dtype="f8")

        vy = ds.createVariable("y", "f8", ("y",))
        vy.units = "m"
        vy.long_name = "projected northing"
        vy[:] = np.asarray(y, dtype="f8")

        for name, spec in variables.items():
            dims = spec["dims"]
            fill = spec.get("fill_value", np.float32(np.nan))
            var = ds.createVariable(name, "f4", dims, fill_value=fill,
                                     zlib=True, complevel=4)
            if "long_name" in spec:
                var.long_name = spec["long_name"]
            if "units" in spec:
                var.units = spec["units"]
            var[:] = spec["data"]

        ds.crs_wkt = crs_wkt
        for k, val in (global_attrs or {}).items():
            setattr(ds, k, val)
    finally:
        ds.close()


###############################################################################
# NetCDF3 classic writer (no external dependency)
###############################################################################

NC_BYTE, NC_CHAR, NC_SHORT, NC_INT, NC_FLOAT, NC_DOUBLE = 1, 2, 3, 4, 5, 6
NC_DIMENSION, NC_VARIABLE, NC_ATTRIBUTE = 10, 11, 12

_DTYPE_TO_NCTYPE = {
    np.dtype("int32"): (NC_INT, 4, ">i4"),
    np.dtype("float32"): (NC_FLOAT, 4, ">f4"),
    np.dtype("float64"): (NC_DOUBLE, 8, ">f8"),
    np.dtype("int16"): (NC_SHORT, 2, ">i2"),
    np.dtype("int8"): (NC_BYTE, 1, ">i1"),
}


def _pad4(n):
    return (4 - (n % 4)) % 4


def _pack_name(name):
    b = name.encode("ascii")
    out = struct.pack(">i", len(b)) + b
    out += b"\x00" * _pad4(len(b))
    return out


def _pack_numeric_attr(nc_type, values):
    _, size, fmt = [(k, s, f) for k, (t, s, f) in _DTYPE_TO_NCTYPE.items() if t == nc_type][0]
    values = np.atleast_1d(np.asarray(values)).astype(fmt)
    out = struct.pack(">i", nc_type) + struct.pack(">i", len(values))
    out += values.tobytes()
    out += b"\x00" * _pad4(len(values) * size)
    return out


def _pack_text_attr(text):
    b = text.encode("ascii", errors="replace")
    out = struct.pack(">i", NC_CHAR) + struct.pack(">i", len(b)) + b
    out += b"\x00" * _pad4(len(b))
    return out


def _pack_attr_value(value):
    if isinstance(value, str):
        return _pack_text_attr(value)
    if isinstance(value, (int, np.integer)):
        return _pack_numeric_attr(NC_INT, np.array([value], dtype=">i4"))
    if isinstance(value, (float, np.floating)):
        return _pack_numeric_attr(NC_DOUBLE, np.array([value], dtype=">f8"))
    raise TypeError(f"Unsupported attribute type: {type(value)}")


def _pack_att_list(attrs):
    if not attrs:
        return struct.pack(">ii", 0, 0)
    out = struct.pack(">ii", NC_ATTRIBUTE, len(attrs))
    for k, v in attrs.items():
        out += _pack_name(k)
        out += _pack_attr_value(v)
    return out


def _write_netcdf3_classic(filename, time_days, time_units, x, y, crs_wkt,
                            variables, global_attrs):

    ny, nx = len(y), len(x)
    n_time = len(time_days)

    global_attrs = dict(global_attrs or {})
    global_attrs.setdefault("crs_wkt", crs_wkt)
    global_attrs.setdefault("Conventions", "CF-1.8 (partial, hand-written)")

    # ---- assemble the full variable table (coords + data variables) ----
    # each entry: name, dims(tuple of dim names), dtype, attrs, data(ndarray)
    dim_lengths = {"time": 0, "y": ny, "x": nx}  # time is the unlimited dim
    dim_order = ["time", "y", "x"]

    coord_vars = [
        ("time", ("time",), np.asarray(time_days, dtype=">i4"),
         {"units": time_units, "long_name": "time"}),
        ("y", ("y",), np.asarray(y, dtype=">f8"),
         {"units": "m", "long_name": "projected northing"}),
        ("x", ("x",), np.asarray(x, dtype=">f8"),
         {"units": "m", "long_name": "projected easting"}),
    ]

    data_vars = []
    for name, spec in variables.items():
        dims = spec["dims"]
        data = np.asarray(spec["data"], dtype=">f4")
        attrs = {}
        if "long_name" in spec:
            attrs["long_name"] = spec["long_name"]
        if "units" in spec:
            attrs["units"] = spec["units"]
        attrs["_FillValue"] = float(spec.get("fill_value", np.nan))
        data_vars.append((name, dims, data, attrs))

    all_vars = coord_vars + data_vars

    # split into fixed (non-record) and record variables
    fixed_vars = [v for v in all_vars if v[1][0] != "time"]
    record_vars = [v for v in all_vars if v[1][0] == "time"]

    def dtype_for(data):
        # match by kind+itemsize regardless of byte order
        return _DTYPE_TO_NCTYPE[data.dtype.newbyteorder("=")]

    def var_vsize(dims, data, is_record):
        # bytes for ONE record's worth of data (excluding the record dim
        # itself), padded to a multiple of 4
        nc_type, size, _ = dtype_for(data)
        if is_record:
            n_per_record = int(np.prod(data.shape[1:])) if data.ndim > 1 else 1
        else:
            n_per_record = int(np.prod(data.shape))
        raw = n_per_record * size
        return raw + _pad4(raw)

    # ---- header: magic + numrecs ----
    header = b"CDF" + bytes([1])
    header += struct.pack(">i", n_time)

    # ---- dim_list ----
    header += struct.pack(">ii", NC_DIMENSION, len(dim_order))
    for d in dim_order:
        header += _pack_name(d)
        header += struct.pack(">i", dim_lengths[d])

    # ---- global attributes ----
    header += _pack_att_list(global_attrs)

    # ---- var_list (need begin offsets, so build in two passes) ----
    var_entries = []
    for name, dims, data, attrs in fixed_vars + record_vars:
        is_record = dims[0] == "time"
        nc_type, size, _ = dtype_for(data)
        vsize = var_vsize(dims, data, is_record)
        var_entries.append({
            "name": name, "dims": dims, "data": data, "attrs": attrs,
            "nc_type": nc_type, "size": size, "vsize": vsize,
            "is_record": is_record,
        })

    # header bytes for var_list, with placeholder begins, to get total header size
    def render_var_list(entries):
        out = struct.pack(">ii", NC_VARIABLE, len(entries))
        for e in entries:
            out += _pack_name(e["name"])
            out += struct.pack(">i", len(e["dims"]))
            for d in e["dims"]:
                out += struct.pack(">i", dim_order.index(d))
            out += _pack_att_list(e["attrs"])
            out += struct.pack(">i", e["nc_type"])
            out += struct.pack(">i", e["vsize"])
            out += struct.pack(">i", e["begin"])
        return out

    for e in var_entries:
        e["begin"] = 0
    header_wo_begin = header + render_var_list(var_entries)
    header_size = len(header_wo_begin)

    # now assign real begin offsets: fixed vars first (each vsize bytes,
    # in order), then record vars (each contributes vsize bytes PER RECORD,
    # interleaved across all record vars for each record)
    offset = header_size
    for e in var_entries:
        if not e["is_record"]:
            e["begin"] = offset
            offset += e["vsize"]
    record_block_start = offset
    record_stride = sum(e["vsize"] for e in var_entries if e["is_record"])
    running = record_block_start
    for e in var_entries:
        if e["is_record"]:
            e["begin"] = running
            running += e["vsize"]

    header = header + render_var_list(var_entries)
    assert len(header) == header_size

    # ---- data section ----
    with open(filename, "wb") as f:
        f.write(header)

        # fixed variables, in order
        for e in var_entries:
            if e["is_record"]:
                continue
            raw = e["data"].tobytes()
            f.write(raw)
            f.write(b"\x00" * _pad4(len(raw)))

        # Record variables, interleaved per record. Built as ONE
        # vectorised numpy buffer (not a Python loop with one f.write()
        # per record per variable) -- with a year's worth of daily grids
        # that Python-level loop is thousands of tiny operations and
        # dominates runtime; this does it as a handful of bulk array
        # copies instead.
        rec_entries = [e for e in var_entries if e["is_record"]]
        record_stride = sum(e["vsize"] for e in rec_entries)
        combined = np.zeros((n_time, record_stride), dtype=np.uint8)

        var_offset = 0
        for e in rec_entries:
            flat = np.ascontiguousarray(e["data"]).reshape(n_time, -1).view(np.uint8)
            combined[:, var_offset:var_offset + flat.shape[1]] = flat
            var_offset += e["vsize"]  # advance by the (possibly padded) vsize

        f.write(combined.tobytes())
        f.flush()
        os.fsync(f.fileno())
