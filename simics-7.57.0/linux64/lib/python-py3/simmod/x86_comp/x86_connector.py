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


# A temporary PCI upstream connector which can be initialized
# by multiple functions


import simics
from comp import CompException
from connectors import StandardConnector

class I2CLinkV1DownConnector(StandardConnector):
    type = 'i2c-link'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, i2c_link):
        self.i2c_link = i2c_link
    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.i2c_link)]
    def connect(self, cmp, cnt, attr):
        pass
    def disconnect(self, cmp, cnt):
        pass

class KeyboardDownConnector(StandardConnector):
    type = 'keyboard'
    direction = simics.Sim_Connector_Direction_Down
    required = False
    hotpluggable = True
    multi = False

    def __init__(self, kbd):
        self.kbd = kbd
    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.kbd)]
    def connect(self, cmp, cnt, attr):
        kbd = cmp.get_slot(self.kbd)
        kbd.console = attr[0]
    def disconnect(self, cmp, cnt):
        kbd = cmp.get_slot(self.kbd)
        kbd.console = None

class MouseDownConnector(KeyboardDownConnector):
    type = 'mouse'
    def disconnect(self, cmp, cnt):
        pass

class SBInterruptUpConnector(StandardConnector):
    type = 'sb-interrupt'
    direction = simics.Sim_Connector_Direction_Up
    required = False
    hotpluggable = False
    multi = False

    def __init__(self, pic):
        self.pic = pic
    def get_connect_data(self, cmp, cnt):
        return [None, cmp.get_slot(self.pic)]
    def connect(self, cmp, cnt, attr):
        (dst, ioapic) = attr
        cmp.get_slot(self.pic).irq_dev = dst
    def disconnect(self, cmp, cnt):
        cmp.get_slot(self.pic).irq_dev = None

class X86ProcessorDownConnector(StandardConnector):
    def __init__(self, id, phys_mem, port_mem, callback = None, required = False, clock = None):
        if not isinstance(id, int) or id < 0:
            raise CompException('id must be an integer >= 0')
        self.id = id
        self.phys_mem = phys_mem
        self.port_mem = port_mem
        self.callback = callback
        self.type = 'x86-processor'
        self.hotpluggable = False
        self.required = required
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Down
        self.clock = clock

    def get_check_data(self, cmp, cnt):
        return []

    def get_connect_data(self, cmp, cnt):
        return [self.id,
                cmp.get_slot(self.phys_mem),
                cmp.get_slot(self.port_mem)]

    def connect(self, cmp, cnt, attr):
        (cpus,) = attr
        if self.callback:
            for cpu in cpus:
                self.callback(self.id, cpu)

    def disconnect(self, cmp, cnt):
        raise CompException('disconnecting x86-processor connection not allowed')

class X86ApicProcessorDownConnector(X86ProcessorDownConnector):
    def __init__(self, id, phys_mem, port_mem, apic_bus, callback = None, required = False, clock = None):
        X86ProcessorDownConnector.__init__(self, id, phys_mem, port_mem, callback, required)
        self.apic_bus = apic_bus
        self.type = 'x86-apic-processor'
        self.clock = clock

    def get_connect_data(self, cmp, cnt):
        # data format: [dict, phys_mem, port_mem, apic_bus]. We use
        # dict to allow us and our collaborators to extend
        # connect_data easily with new items and still be able to
        # share code (and not to break things once data passed between
        # connectors extended) and to insert their CPU models to
        # x58-ich10.
        return [{ 'id': self.id,
                  'phys_mem': cmp.get_slot(self.phys_mem),
                  'port_mem': cmp.get_slot(self.port_mem),
                  'apic_bus': cmp.get_slot(self.apic_bus),
                  'clock': self.clock and cmp.get_slot(self.clock),
                  # add new fields here, check collaborators' code to
                  # avoid key collisions
                },
                cmp.get_slot(self.phys_mem), # kept not to break old
                                             # collaborator packages
                cmp.get_slot(self.port_mem), # kept not to break old
                                             # collaborator packages
                cmp.get_slot(self.apic_bus), # kept not to break old
                                             # collaborator packages
        ]

class X86ResetBusDownConnector(StandardConnector):
    def __init__(self, reset, required = False):
        if not isinstance(reset, str):
            raise CompException('reset must be a string')
        self.reset = reset
        self.type = 'x86-reset-bus'
        self.hotpluggable = False
        self.required = required
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Down

    def get_connect_data(self, cmp, cnt):
        reset = cmp.get_slot(self.reset)
        return [reset]

    def connect(self, cmp, cnt, attr):
        pass

    def disconnect(self, cmp, cnt):
        raise CompException('disconnecting x86-reset-bus connection not allowed')

# LPC supports Memory, IO, Firmware, Bus Master IO, Bus Master Memory and DMA
# cycles, and serial interrupt transfer cycles as well.
class X86LpcBusDownConnector(StandardConnector):
    def __init__(self,
                 lpc_pic,          # serial interrupt controller
                 lpc_io = "",      # IO space
                 lpc_mem = "",     # Memory space
                 lpc_firmware = "",# Firmware memory space
                 lpc_bmio0 = "",   # Bus master IO space 0
                 lpc_bmio1 = "",   # Bus master IO space 1
                 lpc_bmm0 = "",    # Bus master Memory space 0
                 lpc_bmm1 = "",    # Bus master Memory space 1
                 lpc_dma = ""):    # DMA space
        self.parse_parameter("lpc_pic", lpc_pic)
        self.parse_parameter("lpc_io", lpc_io)
        self.parse_parameter("lpc_mem", lpc_mem)
        self.parse_parameter("lpc_firmware", lpc_firmware)
        self.parse_parameter("lpc_bmio0", lpc_bmio0)
        self.parse_parameter("lpc_bmio1", lpc_bmio1)
        self.parse_parameter("lpc_bmm0", lpc_bmm0)
        self.parse_parameter("lpc_bmm1", lpc_bmm1)
        self.parse_parameter("lpc_dma", lpc_dma)

        self.type = 'lpc-bus'
        self.hotpluggable = True
        self.required = False
        self.multi = True
        self.direction = simics.Sim_Connector_Direction_Down

    def parse_parameter(self, name, var):
        if not (isinstance(var, str)):
            raise CompException("%s must be a string" % (var,))
        setattr(self, name, var)

    def get_cmp_slot(self, cmp, name):
        if name == "":
            return
        return cmp.get_slot(name)

    def get_connect_data(self, cmp, cnt):
        return [self.get_cmp_slot(cmp, sn) for sn in [self.lpc_pic,
                                                      self.lpc_io,
                                                      self.lpc_mem,
                                                      self.lpc_firmware,
                                                      self.lpc_bmio0,
                                                      self.lpc_bmio1,
                                                      self.lpc_bmm0,
                                                      self.lpc_bmm1,
                                                      self.lpc_dma]]

    def connect(self, cmp, cnt, attr):
        sirq_dev = attr[0]
        if sirq_dev:
            cmp.get_slot(self.lpc_pic).SERIRQ_slave = sirq_dev

    def disconnect(self, cmp, cnt):
        cmp.get_slot(self.lpc_pic).SERIRQ_slave = None
