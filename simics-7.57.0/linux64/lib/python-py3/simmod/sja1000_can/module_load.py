# © 2010 Intel Corporation
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

class_name = 'sja1000_can'

def pretty_port(dev):
    import simics
    if isinstance(dev, simics.conf_object_t):
        return "%s" % dev.name
    elif isinstance(dev, list):
        return "%s:%s" % (dev[0].name, dev[1])
    else:
        return "none"

#
# ------------------------ info -----------------------
#

def get_info(obj):

    return [(None, [("Class Desc", obj.class_desc),
                    ("Connection", pretty_port(obj.can_link)),
                    ("Interrupt device", pretty_port(obj.irq_target))])]

cli.new_info_command(class_name, get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    can_mode = ["BasicCAN", "PeliCAN"]
    flt_mode = ["Dual filter", "Single filter"]
    return [("Device Mode", [("CAN mode", can_mode[(obj.regs_cdr >> 7) & 1])]),
    ("Filter Mode", [("Flt mode", flt_mode[(obj.regs_peli_mode >> 3) & 1])])]

cli.new_status_command(class_name, get_status)
