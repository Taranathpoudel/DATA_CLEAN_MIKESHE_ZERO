# -*- coding: utf-8 -*-
"""
netcdf_reader.py

Minimal pure-python NetCDF3-classic reader (companion to
netcdf_writer.py's fallback writer). Reads back dims, global attrs, and
all variables (record and fixed) into numpy arrays.

If `netCDF4` is installed, `open_netcdf` uses it instead (handles both
NETCDF4_CLASSIC files written by netcdf_writer.py's netCDF4 path, and
plain NetCDF3 files).
"""

import struct
import numpy as np

try:
    import netCDF4 as _netCDF4
    _HAVE_NETCDF4 = True
except Exception:
    _HAVE_NETCDF4 = False


NC_BYTE, NC_CHAR, NC_SHORT, NC_INT, NC_FLOAT, NC_DOUBLE = 1, 2, 3, 4, 5, 6
NC_DIMENSION, NC_VARIABLE, NC_ATTRIBUTE = 10, 11, 12

_NCTYPE_TO_DTYPE = {
    NC_BYTE: (">i1", 1), NC_CHAR: (">S1", 1), NC_SHORT: (">i2", 2),
    NC_INT: (">i4", 4), NC_FLOAT: (">f4", 4), NC_DOUBLE: (">f8", 8),
}


def open_netcdf(filename):
    """
    Returns a dict: {"dims": {name: length}, "attrs": {...},
                       "vars": {name: {"data": ndarray, "attrs": {...}}}}
    """
    if _HAVE_NETCDF4:
        try:
            return _read_with_netCDF4(filename)
        except Exception:
            pass
    return _read_netcdf3_classic(filename)


def _read_with_netCDF4(filename):
    ds = _netCDF4.Dataset(filename, "r")
    out = {"dims": {}, "attrs": {}, "vars": {}}
    try:
        for name, dim in ds.dimensions.items():
            out["dims"][name] = len(dim)
        for k in ds.ncattrs():
            out["attrs"][k] = getattr(ds, k)
        for name, var in ds.variables.items():
            out["vars"][name] = {
                "data": var[:].filled(np.nan) if hasattr(var[:], "filled") else np.asarray(var[:]),
                "attrs": {k: getattr(var, k) for k in var.ncattrs()},
            }
    finally:
        ds.close()
    return out


class _Reader:
    def __init__(self, buf):
        self.buf = buf
        self.pos = 0

    def read(self, n):
        b = self.buf[self.pos:self.pos + n]
        self.pos += n
        return b

    def i4(self):
        return struct.unpack(">i", self.read(4))[0]

    def name(self):
        n = self.i4()
        s = self.read(n).decode("ascii")
        pad = (4 - (n % 4)) % 4
        self.read(pad)
        return s


def _read_att_list(r):
    tag = r.i4()
    nelems = r.i4()
    attrs = {}
    if tag == 0:
        return attrs
    for _ in range(nelems):
        name = r.name()
        nc_type = r.i4()
        n = r.i4()
        dtype, size = _NCTYPE_TO_DTYPE[nc_type]
        raw = r.read(n * size)
        pad = (4 - ((n * size) % 4)) % 4
        r.read(pad)
        if nc_type == NC_CHAR:
            val = raw.decode("ascii", errors="replace")
        else:
            val = np.frombuffer(raw, dtype=dtype)
            val = val[0] if len(val) == 1 else val
        attrs[name] = val
    return attrs


def _read_netcdf3_classic(filename):
    with open(filename, "rb") as f:
        buf = f.read()

    r = _Reader(buf)
    magic = r.read(3)
    version = r.read(1)
    assert magic == b"CDF", "Not a NetCDF3 classic file"

    numrecs = r.i4()

    dim_tag = r.i4()
    n_dims = r.i4()
    dims = {}
    dim_order = []
    record_dim_name = None
    for _ in range(n_dims):
        name = r.name()
        length = r.i4()
        if length == 0:
            record_dim_name = name
        dims[name] = length if length != 0 else numrecs
        dim_order.append(name)

    global_attrs = _read_att_list(r)

    var_tag = r.i4()
    n_vars = r.i4()
    var_entries = []
    for _ in range(n_vars):
        name = r.name()
        ndims = r.i4()
        dimids = [r.i4() for _ in range(ndims)]
        attrs = _read_att_list(r)
        nc_type = r.i4()
        vsize = r.i4()
        begin = r.i4()
        var_entries.append({
            "name": name, "dims": [dim_order[i] for i in dimids],
            "attrs": attrs, "nc_type": nc_type, "vsize": vsize, "begin": begin,
        })

    # the record dimension is whichever dim had raw length 0 in the header
    record_dim = record_dim_name

    record_stride = sum(
        ve["vsize"] for ve in var_entries
        if ve["dims"] and ve["dims"][0] == record_dim
    )

    out_vars = {}
    for e in var_entries:
        dtype, size = _NCTYPE_TO_DTYPE[e["nc_type"]]
        is_record = len(e["dims"]) > 0 and e["dims"][0] == record_dim

        shape_tail = [dims[d] for d in e["dims"][1:]] if is_record else [dims[d] for d in e["dims"]]
        n_per_record = int(np.prod(shape_tail)) if shape_tail else 1

        if is_record:
            data = np.empty((numrecs,) + tuple(shape_tail), dtype=dtype)
            for rec in range(numrecs):
                off = e["begin"] + rec * record_stride
                raw = buf[off: off + n_per_record * size]
                data[rec] = np.frombuffer(raw, dtype=dtype).reshape(shape_tail)
        else:
            raw = buf[e["begin"]: e["begin"] + n_per_record * size]
            data = (np.frombuffer(raw, dtype=dtype).reshape(shape_tail)
                    if shape_tail else np.frombuffer(raw, dtype=dtype))

        out_vars[e["name"]] = {"data": data, "attrs": e["attrs"]}

    return {"dims": dims, "attrs": global_attrs, "vars": out_vars}
