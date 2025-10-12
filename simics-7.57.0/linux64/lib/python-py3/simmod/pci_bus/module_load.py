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

import simics
import deprecation

from functools import cmp_to_key
from cli import (
    get_last_loaded_module,
    new_info_command,
)
from simicsutils.internal import py3_cmp
device_name = get_last_loaded_module()

#
# -------------------- info --------------------
#

def slot_cmp(left, right):
    (slot1, fun1, name1, en1) = left
    (slot2, fun2, name2, en2) = right
    if slot1 == slot2:
        return py3_cmp(fun1, fun2)
    return py3_cmp(slot1, slot2)

def get_info(obj):
    devs = sorted(obj.pci_devices, key = cmp_to_key(slot_cmp))
    if isinstance(obj.bridge, list):
        bridge_info = [("Bridge devices", [bobj.name for bobj in obj.bridge])]
    else:
        bridge_info = [("Bridge device", obj.bridge.name if obj.bridge else "none")]
    if obj.interrupt:
        bridge_info += [("Interrupt devices", [iobj.name for iobj in obj.interrupt])]

    return [ (None,
              bridge_info +
              [("PCI Bus Number", "0x%x" % obj.bus_number)]),
             (None,
              [ ("Config space", obj.conf_space),
                ("IO space", obj.io_space),
                ("Memory space", obj.memory_space)]),
             ("Connected devices",
              [ ("Slot %d function %d" % (dev[0], dev[1]),
                 "%s%s" % (dev[2].name, "" if dev[3] else " (disabled)"))
                for dev in devs ] ) ]

new_info_command(device_name, get_info)

if device_name == "pcie-bus":
    deprecation.DEPRECATED(simics.SIM_VERSION_7,
                           "The old PCIe bus and the pci-express interfaces have been deprecated.",
                           "Use pcie-downstream-port instead.")
