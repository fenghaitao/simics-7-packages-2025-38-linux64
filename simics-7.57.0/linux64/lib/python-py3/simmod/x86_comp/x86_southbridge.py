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


import simics, flash_memory
from comp import *

class std_pc_io_port_map:
    def __init__(self):
        self.map = []

    # Add 3x15 IO ports of DMA
    def add_dma_iop(self, dma):
        for i in range(0x00, 0x10):
            self.map += [[i, dma, 0, i, 1]]
        for i in range(0x81, 0x90):
            self.map += [[i, dma, 0, i, 1]]
        for i in range(0xc0, 0xe0, 2):
            self.map += [[i, dma, 0, i, 1]]

    # Add 2x3 IO ports of Intel 8259A PIC
    def add_8259_iop(self, i8259):
        for i in range(2): # 0 --- port-A, 1 --- port-B
            self.map += [[0x020 + i, i8259, 0, 0x20 + i, 1]] # Master PIC
            self.map += [[0x0a0 + i, i8259, 0, 0xa0 + i, 1]] # Slave PIC
        for i in range(2): # 0 --- Master PIC, 1 --- Slave PIC
            self.map += [[0x4d0 + i, i8259, 0, 0x4d0 + i, 1]]

    # Add 5 IO ports of Intel® 8254
    def add_8254_iop(self, i8254):
        for i in range(4):
            self.map += [[0x040 + i, i8254, 0, i, 1]]
        self.map += [[0x061, i8254, 1, 0, 1]]

    # Add 2 IO ports of RTC
    def add_rtc_iop(self, rtc):
        for i in range(2):
            self.map += [[0x070 + i, rtc, 0, i, 1]]

    # Add 8 IO ports of primary IDE channel
    def add_primary_ide_iop(self, ide):
        self.map += [[0x1f0, ide, 0, 0x0, 4]] # ???4
        for i in range(1, 8):
            self.map += [[0x1f0 + i, ide, 0, i, 1]]
        self.map += [[0x3f6, ide, 0, 8, 1]]

    # Add 8 IO ports of secondary IDE channel
    def add_secondary_ide_iop(self, ide):
        self.map += [[0x170, ide, 0, 0x0, 4]] # ???4
        for i in range(1, 8):
            self.map += [[0x170 + i, ide, 0, i, 1]]
        self.map += [[0x376, ide, 0, 8, 1]]

    # Add 4 IO ports of 82077 floppy controller
    def add_82077_iop(self, i82077):
        self.map += [[0x3f2, i82077, 0, 0, 1],
                     [0x3f4, i82077, 0, 2, 1],
                     [0x3f5, i82077, 0, 3, 1],
                     [0x3f7, i82077, 0, 5, 1]]

    # Add 2 IO ports of 8042 keyboard/mouse controller
    def add_8204_iop(self, i8204):
        self.map += [[0x60, i8204, 0, 0, 1],
                     [0x64, i8204, 0, 4, 1]]

    # Add 8 IO ports of com UART
    def add_com_iop(self, com, num):
        if num > 3:
            num = 3
        base = (0x3F8, 0x2F8, 0x3E8, 0x2E8)[num]
        for i in range(8):
            self.map += [[base + i, com, 0, i, 1]]

    # Add 2 IO ports for APM
    def add_apm_iop(self, lpc):
        self.map += [[0xb2, lpc, 2, 0, 1],
                     [0xb3, lpc, 2, 1, 1]]

class southbridge_x86(StandardConnectorComponent):
    """Base component for PC southbridge."""
    _do_not_init = object()

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_connectors(self):
        ide_cnt = [['ide0_master', 'ide0', True],
                   ['ide0_slave', 'ide0', False],
                   ['ide1_master', 'ide1', True],
                   ['ide1_slave', 'ide1', False]]
        for (slave, dev, master) in ide_cnt:
            self.add_connector(slave, IdeSlotDownConnector(dev, master))

    def add_objects(self):
        std_map = std_pc_io_port_map()

        pic = self.add_pre_obj('pic', 'i8259x2')
        std_map.add_8259_iop(pic)

        isa = self.add_pre_obj('isa', 'ISA')
        isa_bus = self.add_pre_obj('isa_bus', 'port-space')
        isa.pic = pic
        # The following table is only used when isa is connected to an IO-APIC
        isa.irq_to_pin = [2,   1,  0,  3,  4,  5,  6,  7,  8,  9,
                                 10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
                                 20, 21, 22, 23, 24, 25, 26, 27, 28, 29,
                                 30, 31]

        pit = self.add_pre_obj('pit', 'i8254')
        pit.irq_level = 0
        pit.gate = [1, 1, 0, 0]
        pit.out = [1, 1, 1, 0]
        pit.irq_dev = isa
        std_map.add_8254_iop(pit)

        dma = self.add_pre_obj('dma', 'i8237x2')
        std_map.add_dma_iop(dma)

        rtc= self.add_pre_obj('rtc', 'DS12887')
        rtc.registers_a = 0x20
        rtc.registers_b = 0x02
        rtc.irq_level = 8
        rtc.irq_dev = isa
        std_map.add_rtc_iop(rtc)

        ide0 = self.add_pre_obj('ide0', 'ide')
        ide0.irq_dev = isa
        ide0.primary = 1
        ide0.irq_level = 14
        ide0.interrupt_delay = 1.0e-5
        std_map.add_primary_ide_iop(ide0)

        ide1 = self.add_pre_obj('ide1', 'ide')
        ide1.irq_dev = isa
        ide1.primary = 0
        ide1.irq_level = 15
        ide1.interrupt_delay = 1.0e-5
        std_map.add_secondary_ide_iop(ide1)

        isa_bus.map = std_map.map
