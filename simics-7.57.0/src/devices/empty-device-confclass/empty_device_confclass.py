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

"""Use this file as a skeleton for your own device implementation in Python."""

# Tie code to specific API, simplifying upgrade to new major version
import simics_6_api as simics

class empty_device_confclass:
    """This is the long-winded documentation for this Simics class.
    It can be as long as you want."""

    # Create a conf-class with the name 'empty_device_confclass'.
    cls = simics.confclass('empty_device_confclass',
                           short_doc='one-line doc for the class',
                           doc='longer doc for the class')

    # Create an int attribute 'r1'.
    cls.attr.r1("i", default=0)

    # Create name space object that will be used as a bank.
    regs = cls.o.bank.regs()

    # Implement the 'io_memory' iface on the regs object.
    @regs.iface.io_memory.operation
    def operation(self, mop, info):
        offset = (simics.SIM_get_mem_op_physical_address(mop)
                  + info.start - info.base)
        size = simics.SIM_get_mem_op_size(mop)
        if offset == 0x00 and size == 1:
            if simics.SIM_mem_op_is_read(mop):
                simics.SIM_set_mem_op_value_le(mop, self.r1)
            else:
                self.r1 = simics.SIM_get_mem_op_value_le(mop)
            return simics.Sim_PE_No_Exception
        else:
            return simics.Sim_PE_IO_Error

    # Log when 'r1' changes.
    @cls.attr.r1.setter
    def r1(self, val):
        self.output(f"Attribute r1 changed from {self.r1} to {val}")
        self.r1 = val

    def output(self, s):
        print("empty_device_confclass: " + s)

    @cls.init
    def initialize(self):
        self.output("init")

    @cls.finalize
    def finalize(self):
        self.output("finalize")
