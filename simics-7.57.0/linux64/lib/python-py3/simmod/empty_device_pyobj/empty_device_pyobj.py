# © 2015 Intel Corporation

# Use this file as a skeleton for your own device implementation in Python.

import pyobj
# Tie code to specific API, simplifying upgrade to new major version
import simics_7_api as simics


class empty_device_pyobj(pyobj.ConfObject):
    """This is the long-winded documentation for this Simics class.
    It can be as long as you want."""
    _class_desc = "one-line doc for the class"
    _do_not_init = object()

    def _initialize(self):
        super()._initialize()

    def _info(self):
        return []

    def _status(self):
        return [("Registers", [("value", self.value.val)])]

    class value(pyobj.SimpleAttribute(0, 'i')):
        """The <i>value</i> register."""

    class regs(pyobj.PortObject):
        """An example of a register bank."""
        namespace = 'bank'
        class io_memory(pyobj.Interface):
            def operation(self, mop, info):
                offset = (simics.SIM_get_mem_op_physical_address(mop)
                          + info.start - info.base)
                size = simics.SIM_get_mem_op_size(mop)

                if offset == 0x00 and size == 1:
                    if simics.SIM_mem_op_is_read(mop):
                        val = self._up._up.value.val
                        simics.SIM_set_mem_op_value_le(mop, val)
                    else:
                        val = simics.SIM_get_mem_op_value_le(mop)
                        self._up._up.value.val = val
                    return simics.Sim_PE_No_Exception
                else:
                    return simics.Sim_PE_IO_Error
