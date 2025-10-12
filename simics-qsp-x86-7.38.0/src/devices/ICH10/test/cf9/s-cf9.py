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


# tests the Reset Register (CF9) on ICH10 module.

import pyobj
import dev_util
import stest

varraise = 0
varlower = 0

class ich10_reset_signal_mock(pyobj.ConfObject):

    class signal(pyobj.Interface):
        def signal_raise(self):
            global varraise
            varraise = 1
        def signal_lower(self):
            global varlower
            varlower = 1

SIM_create_object("ich10_reset_signal_mock", "reset_signal_mock", [])
SIM_create_object("ich10_cf9", "cf9",
                  [["reset_signal", conf.reset_signal_mock]])

reg = dev_util.Register_LE(conf.cf9, 0, 1)
reg.write(0x6) # Command 6 does hard reset, which is what we listen to.
stest.expect_equal(varraise, 1)
stest.expect_equal(varlower, 1)

print("Success")
