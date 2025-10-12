# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import stest
from dev_util import Register_LE
from simics import SIM_load_module, SimExc_General

# These legacy-comparison tests are a bit silly, and were really just
# used during development to flush out some annoying bugs. Since I
# wrote them I've kept them, but won't fail if the legacy-module isn't
# available. We have other tests that verify the actual functionality
# of the devices

try:
    SIM_load_module('X58-legacy')
except SimExc_General:
    print("No X58-legacy module present, can't test against legacy devices")
    import sys
    sys.exit(0)


def compare_devs(new_dev, old_dev, accepted_diffs={}):
    for offs in range(0, 0x1000, 4):
        new_val = Register_LE(new_dev, offs).read()
        old_real = Register_LE(old_dev, offs).read()
        old_val = accepted_diffs.get(offs, old_real)
        stest.expect_equal(
            new_val, old_val, f"{new_dev.name} regs at {hex(offs)} differ")
