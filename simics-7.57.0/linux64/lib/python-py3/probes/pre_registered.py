# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

from .probes import register_probe
from .common import listify
from .probe_enums import *

register_probe(
    "dev.io_access_count",
    listify([(Probe_Key_Display_Name, "IO accesses"),
             (Probe_Key_Description,
              "Memory or port accesses towards the device."),
             (Probe_Key_Type, "int"),
             (Probe_Key_Categories, ["device", "io"]),
             (Probe_Key_Width, 12),
             # Aggregates explicitly defined by the hand-written
             # probes classes, which cache global and cell sum across
             # the probes:
             # - {sim,cell}.io_access_count
             # - {sim,cell}.io_access_class_histogram
             # - {sim,cell}.io_access_object_histogram
             ]))
