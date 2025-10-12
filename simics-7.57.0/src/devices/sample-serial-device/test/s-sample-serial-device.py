# © 2012 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Test the sample serial device.

import dev_util
import stest
import conf
# SIMICS-21543
conf.sim.deprecation_level = 0

class Struct:
    pass

#
# Redefine the Serial class so it can handle more than one character.
#
class Serial2(dev_util.SerialDevice):
    def __init__(self):
        self.buffer = []

    def write(self, sim_obj, value):
        if len(self.buffer) == 10:
            return 0
        self.buffer.append(value)
        return 1

    def is_empty(self):
        return len(self.buffer) == 0

    def get_char(self):
        c = self.buffer.pop(0)
        serial_device.iface.serial_device.receive_ready()
        return c


#
# Set up the test environment.
#
def setup_test_environment():
    global serial_device
    global console
    global interrupt
    global regs

    serial_device = pre_conf_object('serial_device', 'sample_serial_device')
    other_devices = dev_util.Dev([Serial2, dev_util.Signal])
    serial_device.attr.console = other_devices.obj
    serial_device.attr.irq_dev = other_devices.obj
    console = other_devices.serial_device
    interrupt = other_devices.signal
    SIM_add_configuration([serial_device], None)
    serial_device = conf.serial_device

    regs = Struct()
    regs.rw = dev_util.Register((serial_device, 'registers', 0x00), 1)
    regs.status = dev_util.Register((serial_device, 'registers', 0x01), 1)
    regs.mask = dev_util.Register((serial_device, 'registers', 0x02), 1)


#
# Check that the interrupt level for the input characters interrupt is what's
# expected.
#
def check_interrupt_level(expected_level):
    if interrupt.level != expected_level:
        raise stest.TestFailure('expected interrupt count '
                                + str(expected_level)
                                + ', actual value ' + str(interrupt.level))


def do_test():
    # Simulate input of one character
    stest.expect_equal(regs.status.read(), 0)
    count = serial_device.iface.serial_device.write(0x41)
    stest.expect_equal(count, 1)
    stest.expect_equal(regs.status.read(), 1)
    check_interrupt_level(0)
    stest.expect_equal(regs.rw.read(), 0x41)
    stest.expect_equal(regs.status.read(), 0)
    stest.expect_equal(regs.rw.read(), 0)

    # Simulate input of a lot of characters
    # Make sure the input buffer expands in size
    for c in range(0, 256):
        count = serial_device.iface.serial_device.write(c)
        stest.expect_equal(count, 1)
        check_interrupt_level(0)
        if c % 10 == 0:
            # remove some characters to exercise the circular buffer behaviour
            stest.expect_equal(regs.status.read(), 1)
            stest.expect_equal(regs.rw.read(), c // 10)

    for c in range(26, 256):
        stest.expect_equal(regs.status.read(), 1)
        stest.expect_equal(regs.rw.read(), c)
    stest.expect_equal(regs.status.read(), 0)
    stest.expect_equal(regs.rw.read(), 0)

    # Test interrupt for input characters
    regs.mask.write(1)
    count = serial_device.iface.serial_device.write(0x50)
    stest.expect_equal(count, 1)
    check_interrupt_level(1)
    count = serial_device.iface.serial_device.write(0x51)
    stest.expect_equal(count, 1)
    check_interrupt_level(1)
    stest.expect_equal(regs.rw.read(), 0x50)
    check_interrupt_level(1)
    stest.expect_equal(regs.rw.read(), 0x51)
    check_interrupt_level(0)

    # Output one character to the "screen"
    stest.expect_equal(console.is_empty(), True)
    regs.rw.write(0x42)
    stest.expect_equal(console.is_empty(), False)
    stest.expect_equal(console.get_char(), 0x42)
    stest.expect_equal(console.is_empty(), True)

    # Output a lot of characters to the "screen"
    for c in range(0, 256):
        regs.rw.write(c)
    for c in range(0, 256):
        stest.expect_equal(console.get_char(), c)


#
# The test starts here.
#
setup_test_environment()
do_test()

print('Test passed without errors')
