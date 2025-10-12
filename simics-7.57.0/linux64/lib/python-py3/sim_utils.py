# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import inspect

def arity_check(fun, arity, name):
    if not inspect.ismethod(fun) or inspect.isfunction(fun):
        return ""

    spec = inspect.getfullargspec(fun)
    self_arg = 1 if inspect.ismethod(fun) and fun.__self__ is not None else 0
    argc = len(spec.args) - self_arg
    ndefs = len(spec.defaults) if spec.defaults else 0
    minargs = argc - ndefs
    maxargs = float("inf") if spec.varargs else argc

    if arity >= minargs and arity <= maxargs:
        return ""

    def plural(x):
        return 's' if x > 1 else ''

    if minargs == maxargs:
        args = minargs
        qual = ""
    elif arity < minargs:
        args = minargs
        qual = "at least "
    else:
        args = maxargs
        qual = "at most "
    err = (f"Function taking {arity} argument{plural(arity)}"
           f" required ({name}), but '{fun.__name__}' used here takes"
           f" {qual}{args} argument{plural(args)}.")
    return err

def int128_from_bytes(data):
    return int.from_bytes(data, byteorder='little', signed=True)

def int128_to_bytes(data):
    return data.to_bytes(length=16, byteorder='little', signed=True)
