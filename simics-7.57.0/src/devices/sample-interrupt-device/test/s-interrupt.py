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


import stest
import dev_util
import pyobj

class mock_signal(pyobj.ConfObject):
    class signal(pyobj.Interface):
        def _initialize(self):
            self.level = False
        def signal_lower(self):
            stest.expect_equal(self.level, True)
            self.level = False
        def signal_raise(self):
            stest.expect_equal(self.level, False)
            self.level = True

signal_obj = SIM_create_object("mock_signal", "mock_signal")
dev = SIM_create_object("sample_interrupt_device", "dev",
                        [["irq_dev", signal_obj]])

signal = SIM_object_data(signal_obj).signal
cause = dev_util.Register((dev, "regs", 0))
mask = dev_util.Register((dev, "regs", 4))

dev.regs_cause = 3

def expect_state(c, m, s):
    stest.expect_equal((cause.read(), mask.read(), signal.level),
                       (c, m, s))

# No interrupt
expect_state(3, 0, False)

# Enable interrupt by setting mask
mask.write(0x1)
expect_state(3, 1, True)

# Disable interrupt by clearing mask
mask.write(0x0)
expect_state(3, 0, False)

# Enable interrupt by setting mask
mask.write(0x1)
expect_state(3, 1, True)

# Clear interrupt by writing 1's to cause
cause.write(0xf)
expect_state(0, 1, False)

# Set cause register internally
dev.ports.generate_interrupt[3].signal.signal_raise()
dev.ports.generate_interrupt[3].signal.signal_lower()
expect_state(0x8, 1, False)

# Trigger internal interrupt
dev.ports.generate_interrupt[0].signal.signal_raise()
dev.ports.generate_interrupt[0].signal.signal_lower()
expect_state(0x9, 1, True)

# Clear interrupt by writing 1's to cause
cause.write(0xf)
expect_state(0, 1, False)
