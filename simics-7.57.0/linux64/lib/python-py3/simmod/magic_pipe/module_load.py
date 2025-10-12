# © 2014 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import cli
import simics

def get_info(obj):
    rows = [("Core Magic", obj.hapnum)]
    return [(None, rows)]

def get_map(obj):
    rows = list()
    for [mmin, mmax, user, rd, wr] in obj.map:
        rstr = "0x%016x" % mmin
        if mmax > mmin:
            rstr += " - 0x%016x" % mmax
        if rd or wr:
            sstr = user.name
        else:
            sstr = "<reserved by %s>" % user.name
        rows += [(rstr, sstr)]
    return rows

def get_status(obj):
    rows  = [("Haps", obj.haps)]
    rows += [("Readers", len(obj.readers))]
    rows += [("Writers", len(obj.writers))]
    rows += get_map(obj)
    return [(None, rows)]

cli.new_info_command('magic_pipe', get_info)
cli.new_status_command('magic_pipe', get_status)
