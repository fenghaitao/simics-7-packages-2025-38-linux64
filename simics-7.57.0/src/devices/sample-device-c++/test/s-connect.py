# © 2024 Intel Corporation
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

dut1 = SIM_create_object('sample_device_cxx_connect', 'dut1', [])

class cls_provides_interrupt:
    cls = confclass('cls_provides_interrupt')
    cls.attr.state('[si]', default=["invalid", 0])

    @cls.iface.simple_interrupt.interrupt
    def interrupt(self, line):
        self.state = ["interrupt", line]

    @cls.iface.simple_interrupt.interrupt_clear
    def interrupt_clear(self, line):
        self.state = ["interrupt_clear", line]

class cls_provides_signal:
    cls = confclass('cls_provides_signal')
    cls.attr.state('b', default=False)

    @cls.iface.signal.signal_raise
    def signal_raise(self):
        stest.expect_false(self.state, "signal raised when already high")
        self.state = True

    @cls.iface.signal.signal_lower
    def signal_lower(self):
        stest.expect_true(self.state, "signal lowered when already low")
        self.state = False

class cls_provides_both:
    cls = confclass('cls_provides_both')
    cls.attr.signal_state('b', default=False)
    cls.attr.interrupt_state('[si]', default=["invalid", 0])

    @cls.iface.signal.signal_raise
    def signal_raise(self):
        stest.expect_false(self.state, "signal raised when already high")
        self.state = True

    @cls.iface.signal.signal_lower
    def signal_lower(self):
        stest.expect_true(self.state, "signal lowered when already low")
        self.state = False

    @cls.iface.simple_interrupt.interrupt
    def interrupt(self, line):
        self.state = ["interrupt", line]

    @cls.iface.simple_interrupt.interrupt_clear
    def interrupt_clear(self, line):
        self.state = ["interrupt_clear", line]

# irq_dev can be set with an object implementing simple_interrupt interface
stest.expect_equal(dut1.irq_dev, None)
obj_with_interrupt = SIM_create_object("cls_provides_interrupt",
                                       "obj_with_interrupt", [])
dut1.irq_dev = obj_with_interrupt
stest.expect_equal(dut1.irq_dev, obj_with_interrupt)

# irq_dev cannot be set with an object only implements signal interface
# since simple_interrupt interface is required
obj_with_signal = SIM_create_object("cls_provides_signal",
                                    "obj_with_signal", [])
try:
    dut1.irq_dev = obj_with_signal
except SimExc_InterfaceNotFound:
    pass
else:
    raise CliError("The set is expected to fail")

# irq_dev can be set to an object implements both interfaces
obj_with_both = SIM_create_object("cls_provides_both",
                                  "dev_provides_both", [])
dut1.irq_dev = obj_with_both
stest.expect_equal(dut1.irq_dev, obj_with_both)

# the connect attribute can be set when creating the object
stest.expect_equal(obj_with_interrupt.state, ["invalid", 0])
dut2 = SIM_create_object('sample_device_cxx_connect', 'dut2',
                         [["irq_dev", obj_with_interrupt]])
stest.expect_equal(obj_with_interrupt.state, ["interrupt", 0])

# the connect attribute is set to a descendant object during creation
dut3 = SIM_create_object('sample_device_cxx_connect_to_descendant', 'dut3', [])
stest.expect_equal(dut3.target_mem_space, dut3.port.memory_space)

class cls_provides_io_memory:
    cls = confclass('cls_provides_io_memory')

    @cls.iface.io_memory.operation
    def operation(self, mem_op, map_info):
        pass

dut4 = SIM_create_object('sample_device_cxx_connect_map_target', 'dut4', [])
obj_with_io_memory = SIM_create_object("cls_provides_io_memory",
                                       "obj_with_io_memory", [])

# map_target connect attribute can be set to an object with io_memory interface
stest.expect_equal(dut4.map_target, None)
dut4.map_target = obj_with_io_memory
stest.expect_equal(dut4.map_target, obj_with_io_memory)
