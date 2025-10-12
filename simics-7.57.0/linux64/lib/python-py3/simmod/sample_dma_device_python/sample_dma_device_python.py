# © 2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import pyobj
import simics
from enum import IntEnum

class sample_dma_device_python(pyobj.ConfObject):
    """This device models a Simics DMA device in Python."""
    _class_desc = "sample Python DMA device"

    def _initialize(self):
        super()._initialize()

    def _info(self):
        return []

    def _status(self):
        return [(None,
                 [("Interrupt target", self.intr_target.val),
                  ("memory space", self.target_mem.val),
                  ("throttle", self.throttle.val)])]

    class intr_target(pyobj.SimpleAttribute(None, 'o')):
        """The interrupt target"""

    class target_mem(pyobj.SimpleAttribute(None, 'o',
                                           simics.Sim_Attr_Required)):
        """The target memory space to do DMA transfer"""

    class throttle(pyobj.SimpleAttribute(1.0e-6, 'f')):
        "Delay in seconds per 32-bit word of memory copied, default is 1μs."

    class regs(pyobj.PortObject):
        """An example of a register bank."""
        namespace = 'bank'

        class ControlBits(IntEnum):
            EN = 31
            SWT = 30
            ECI = 29
            TC = 28
            SG = 27
            ERR = 26
            TS_MSB = 15
            TS_LSB = 0

        class RegOffset(IntEnum):
            MMIO_CONTROL = 0
            MMIO_SOURCE = 4
            MMIO_DEST = 8

        def _initialize(self):
            super()._initialize()
            self.regs = {
                'dma_control': 0,
                'dma_source': 0,
                'dma_destination': 0
            }
            self.interrupt_raised = False
            self.dma_complete_ev = simics.SIM_register_event(
                "dma_complete", None, simics.Sim_EC_Notsaved,
                lambda obj, func: func(), None, None, None, None)

        @staticmethod
        def get_field(register, start_bit, end_bit=None):
            if end_bit is None:
                end_bit = start_bit

            # Create a mask for the desired bits
            mask = (1 << (end_bit - start_bit + 1)) - 1

            # Shift the register right to align the desired bits with the mask
            return (register >> start_bit) & mask

        def read_mem(self, source, count):
            simics.SIM_log_info(4, self.obj, 0,
                                "Read mem from 0x%x, size 0x%x" % (source,
                                                                   count))
            assert self._up.target_mem.val
            return self._up.target_mem.val.iface.memory_space.read(
                self.obj, source, count, 0)

        def write_mem(self, destination, buffer, count):
            simics.SIM_log_info(4, self.obj, 0,
                                "Write mem to 0x%x, size 0x%x" % (destination,
                                                                  count))
            assert self._up.target_mem.val
            self._up.target_mem.val.iface.memory_space.write(
                self.obj, destination, tuple(buffer), 0)

        def dma_complete(self):
            simics.SIM_log_info(3, self.obj, 0, "DMA transfer completed")

            ctrl = self.regs['dma_control']
            # Clear the SWT bit
            ctrl &= ~(1 << self.ControlBits.SWT)

            # Update the TS range to 0
            ts_bit_size = self.ControlBits.TS_MSB - self.ControlBits.TS_LSB + 1
            ts_mask = ((1 << ts_bit_size) - 1) << self.ControlBits.TS_LSB
            ctrl &= ~ts_mask  # Clear the TS bits

            # Set the TC bit to 1
            ctrl |= (1 << self.ControlBits.TC)

            # Update the dma_control register
            self.regs['dma_control'] = ctrl

            if ctrl & (1 << self.ControlBits.ECI) and not self.interrupt_raised:
                simics.SIM_log_info(3, self.obj, 0, "Raise interrupt")
                self._up.intr_target.val.iface.signal.signal_raise()
                self.interrupt_raised = True

        def do_dma_transfer(self, old_val):
            ctrl = self.regs['dma_control']
            simics.SIM_log_info(3, self.obj, 0,
                                "Do DMA transfer 0x%x" % ctrl)

            # Software asked us to initiate a DMA transfer
            if not (ctrl & (1 << self.ControlBits.EN)):
                # Enable bit is not set, so we cannot transfer
                simics.SIM_log_info(3, self.obj, 0,
                                    "EN bit not set, SWT = 1 has no effect")
                return

            if ctrl & (1 << self.ControlBits.TC):
                simics.SIM_log_spec_violation(1, self.obj, 0,
                                              "Write 1 to TC is not allowed")
            else:
                if (old_val & (1 << self.ControlBits.TC)
                    and self.interrupt_raised):
                    simics.SIM_log_info(4, self.obj, 0, "Clear interrupt")
                    self._up.intr_target.val.iface.signal.signal_lower()
                    self.interrupt_raised = False

            # No need to do anything if we are not asked by software
            if not (ctrl & (1 << self.ControlBits.SWT)):
                return

            ts_bit_size = self.ControlBits.TS_MSB - self.ControlBits.TS_LSB + 1
            count = 4 * ((ctrl >> self.ControlBits.TS_LSB)
                         & ((1 << ts_bit_size) - 1))
            buf = self.read_mem(self.regs['dma_source'], count)
            self.write_mem(self.regs['dma_destination'], buf, count)

            delay = count / 4 * self._up.throttle.val
            simics.SIM_log_info(3, self.obj, 0,
                                f"Notify completion in {delay * 1.0e6} us")
            simics.SIM_event_post_time(simics.SIM_object_clock(self.obj),
                                       self.dma_complete_ev, self.obj, delay,
                                       self.dma_complete)

        class io_memory(pyobj.Interface):
            def operation(self, mop, info):
                offset = (simics.SIM_get_mem_op_physical_address(mop)
                          + info.start - info.base)
                size = simics.SIM_get_mem_op_size(mop)
                if size != 4:
                    simics.SIM_log_error(self._up.obj, 0,
                                         "Only support size 4 read/write")
                    return simics.Sim_PE_IO_Error

                if simics.SIM_mem_op_is_read(mop):
                    if offset == self._up.RegOffset.MMIO_CONTROL:
                        value = self._up.regs['dma_control']
                    elif offset == self._up.RegOffset.MMIO_SOURCE:
                        value = self._up.regs['dma_source']
                    elif offset == self._up.RegOffset.MMIO_DEST:
                        value = self._up.regs['dma_destination']
                    else:
                        simics.SIM_log_error(self._up.obj, 0,
                                             "Invalid offset %d" % offset)
                        return simics.Sim_PE_IO_Error
                    simics.SIM_log_info(
                        4, self._up.obj, 0,
                        "Read from offset 0x%x, value = 0x%x" % (offset, value))
                    simics.SIM_set_mem_op_value_be(mop, value)
                else:
                    value = simics.SIM_get_mem_op_value_be(mop)
                    simics.SIM_log_info(
                        4, self._up.obj, 0,
                        "Write to offset 0x%x, value = 0x%x" % (offset, value))
                    if offset == self._up.RegOffset.MMIO_CONTROL:
                        old_value = self._up.regs['dma_control']
                        if old_value != value:
                            self._up.regs['dma_control'] = value
                            self._up.do_dma_transfer(old_value)
                    elif offset == self._up.RegOffset.MMIO_SOURCE:
                        self._up.regs['dma_source'] = value
                    elif offset == self._up.RegOffset.MMIO_DEST:
                        self._up.regs['dma_destination'] = value
                    else:
                        simics.SIM_log_error(self._up.obj, 0,
                                             "Invalid offset %d" % offset)
                        return simics.Sim_PE_IO_Error
                return simics.Sim_PE_No_Exception
