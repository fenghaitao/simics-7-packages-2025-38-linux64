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


# This demonstrates how you can use pyobj to implement a device in Python.

import pyobj
import simics

class sample_device_python(pyobj.ConfObject):
    """This device does nothing useful, but can be used as a starting point
       when writing Simics devices in Python.

       The source can be found at
       <tt>[simics]/src/devices/sample-device-python/</tt>."""

    _class_desc = "sample Python device"

    def _initialize(self):
        super()._initialize()

    def _status(self):
        return [("Registers", [("Temperature", self.temperature.val)])]

    class temperature(pyobj.SimpleAttribute(0, 'i')):
        """The <i>temperature</i> register."""

    class io_memory(pyobj.Interface):
        def operation(self, mop, info):
            # offset within our device
            offset = (simics.SIM_get_mem_op_physical_address(mop)
                      + info.start - info.base)

            # Find out what to do:
            if offset == 0x00:
                # our register 0 is read-only and reads the temperature
                if simics.SIM_mem_op_is_read(mop):
                    # this is a little endian device
                    val = self._up.temperature.val
                    if not simics.SIM_get_mem_op_inquiry(mop):
                        simics.SIM_log_info(1, self._up.obj, 0,
                                            "Reading temperature %d" % val)
                    simics.SIM_set_mem_op_value_le(mop, val)
                else:
                    simics.SIM_log_spec_violation(1, self._up.obj, 0,
                                                  "Write to read-only "
                                                  "temperature register.")
            elif offset == 0x01:
                # our register 1 is write-only, and sets the temperature
                if simics.SIM_mem_op_is_write(mop):
                    # this is a little endian device
                    val = simics.SIM_get_mem_op_value_le(mop)
                    simics.SIM_log_info(1, self._up.obj, 0,
                                        "Writing temperature %d" % val)
                    self._up.temperature.val = val
                elif simics.SIM_get_mem_op_inquiry(mop):
                    return simics.Sim_PE_Inquiry_Unhandled
                else:
                    simics.SIM_log_spec_violation(1, self._up.obj, 0,
                                                  "Read from write-only "
                                                  "temperature register.")
                    simics.SIM_set_mem_op_value_le(mop, 0)
            else:
                if simics.SIM_get_mem_op_inquiry(mop):
                    return simics.Sim_PE_Inquiry_Unhandled
                # bad offset
                if simics.SIM_mem_op_is_read(mop):
                    simics.SIM_set_mem_op_value_le(mop, 0)
                simics.SIM_log_error(self._up.obj, 0, "Illegal offset 0x%x, "
                                     "check mapping." % offset)
            return simics.Sim_PE_No_Exception
