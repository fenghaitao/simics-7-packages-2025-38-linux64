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


import simics, vmp_common
from comp import *
from component_utils import class_has_iface

class X86ProcessorUpConnector(StandardConnector):
    def __init__(self, required = False):
        self.type = 'x86-processor'
        self.hotpluggable = False
        self.required = required
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Up

    def get_connect_data(self, cmp, cnt):
        return [cmp.get_all_threads()]

    def connect(self, cmp, cnt, attr):
        (id, mem_space, port_space) = attr
        for t in cmp.get_all_threads():
            t.port_space = port_space
            t.physical_memory.default_target = [mem_space, 0, 0, None]
            t.shared_physical_memory = mem_space

    def disconnect(self, cmp, cnt):
        raise CompException('disconnecting x86-processor connection not allowed')

class X86ApicProcessorUpConnector(X86ProcessorUpConnector):
    def __init__(self, required = False):
        super().__init__(required)
        self.type = 'x86-apic-processor'

    def connect(self, cmp, cnt, attr):
        if isinstance(attr[0], int):
            # old collaborators' package connects to us,
            # use old format: [id /*not used*/, mem_space, port_space,
            # apic_bus, ... /* probably other items not interesting for us */]
            mem_space = attr[1]
            port_space = attr[2]
            apic_bus = attr[3]
        else:
            args_dict = attr[0]
            mem_space = args_dict['phys_mem']
            port_space = args_dict['port_mem']
            apic_bus = args_dict['apic_bus']
            # clock is optional (collaborators' packages can omit it)
            clock = args_dict.get('clock', None)

        for t in cmp.get_all_threads():
            t.port_space = port_space
            if cmp.cpu_threads > 1:
                t.cpuid_physical_apic_id = 0
            t.physical_memory.default_target = [mem_space, 0, 0, None]
            t.shared_physical_memory = mem_space
            t.apic.apic_id = 0     # temporary value
            t.apic.apic_bus = apic_bus
            if clock is None or class_has_iface(t.classname, 'cycle'):
                # If no separate clock is defined, or if the CPU
                # implements cycle, then it needs to be its own clock.
                t.queue = t
            else:
                t.queue = clock

    def get_connect_data(self, cmp, cnt):
        ls = [[[cpu, cpu.apic, True] for cpu in cmp.get_all_threads()]]
        ls[0][0][2] = False # First CPU in component is not logical
        return ls

class processor_x86(StandardConnectorComponent):
    """Base class for x86 processors."""
    _do_not_init = object()

    def _initialize(self, cpu_threads = 1, cpu_cores = 1):
        super()._initialize()
        self.cpu_threads = cpu_threads
        self.cpu_cores = cpu_cores
        self.tlbclass = "x86-tlb"

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()

    class basename(StandardConnectorComponent.basename):
        val = "processor"

    class freq_mhz(SimpleConfigAttribute(20, 'i')):
        """Processor frequency in MHz, default is 10 MHz."""
        def setter(self, val):
            if val <= 0:
                raise CompException('Illegal processor frequency %d' % val)
            self.val = val

    class cpi(SimpleConfigAttribute(1, 'i')):
        """Cycles per instruction."""

    class threads(Attribute):
        """The number of threads per core."""
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = "i"
        def getter(self):
            return self._up.cpu_threads
        def setter(self, val):
            pass

    class cores(Attribute):
        """The number of processor cores."""
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = "i"
        def getter(self):
            return self._up.cpu_cores
        def setter(self, val):
            pass

    class use_vmp(SimpleConfigAttribute(True, 'b')):
        """Enable VMP at setup by setting attribute to True, disable
        VMP at setup by setting attribute to False. The attribute can
        be changed at run-time but the setting will only affect the
        threads in the component at instantiation. This option affects
        simulated time. See the performance chapter in the Simics
        User's Guide for more information about VMP."""

    def get_all_threads(self):
        return [x for y in self.get_slot('core') for x in y]

    def add_objects(self):
        idx = "[%d][%d]" % (self.cpu_cores, self.cpu_threads)
        cores = self.add_pre_obj('core' + idx, self.cpuclass)
        mems = self.add_pre_obj('mem' + idx, 'memory-space')
        has_tlb = simics.SIM_class_has_attribute(self.cpuclass, "tlb")
        if has_tlb:
            tlbs = self.add_pre_obj('tlb' + idx, self.tlbclass)
        for c in range(self.cpu_cores):
            for t in range(self.cpu_threads):
                core = cores[c][t]
                mem = mems[c][t]
                core.freq_mhz = self.freq_mhz.val
                if simics.SIM_class_has_attribute(self.cpuclass, "step_rate"):
                    core.step_rate = [1, self.cpi.val, 0]
                core.physical_memory = mem
                if has_tlb:
                    tlb = tlbs[c][t]
                    core.tlb = tlb
                    tlb.cpu = core
                if (c,t) == (0, 0): bsp = 1
                else: bsp = 0
                if simics.SIM_class_has_attribute(self.cpuclass, "bsp"):
                    core.bsp = bsp
                if simics.SIM_class_has_attribute(self.cpuclass, "fabric_bsp"):
                    core.fabric_bsp = bsp
                mem.map = []
                core.package_group = cores[0][0]
                if self.cpu_threads > 1:
                    core.threads = cores[c]

    class component(StandardConnectorComponent.component):
        def post_instantiate(self):
            super().post_instantiate()
            if self._up.use_vmp.val:
                self._up.vmp_enable(True, True, True)

    def vmp_enable(self, vmp_timing, startup, enable):
        for t in self.get_all_threads():
            if not vmp_common.setup_vmp(t, vmp_timing, startup, enable):
                # failed to activate - but we still need to set timing model
                enable = False


class processor_x86_apic(processor_x86):
    """Base class for x86 APIC processors."""
    _do_not_init = object()

    def _initialize(self, cpu_threads, cpu_cores):
        super()._initialize(cpu_threads, cpu_cores)
        self.apic_type = "P4"

    def setup(self):
        if self.n_cores.val != -1:
            self.cpu_cores = self.n_cores.val
        if self.n_threads.val != -1:
            self.cpu_threads = self.n_threads.val

        super().setup()
        if not self.instantiated.val:
            self.add_processor_x86_apic_objects()
        self.add_connectors()

    class n_cores(SimpleConfigAttribute(-1, 'i|n')):
        """Quantity of CPU cores"""
        def setter(self, val):
            if val != -1 and (val < 1 or val > 128):
                raise CompException('Illegal number of cores %d (must be'
                                    ' between 1 and 128)' % val)
            self.val = val

    class n_threads(SimpleConfigAttribute(-1, 'i|n')):
        """Quantity of threads per 1 CPU core"""
        def setter(self, val):
            if val != -1 and (val < 1 or val > 8):
                raise CompException('Illegal number of threads %d (must be'
                                    ' between 1 and 8)' % val)
            self.val = val

    class package_number(SimpleConfigAttribute(0, 'i')):
        """CPU package identification number"""

    class apic_freq_mhz(SimpleConfigAttribute(10.0, 'f')):
        """APIC bus frequency in MHz, default is 10 MHz."""
        def setter(self, val):
            if val <= 0:
                raise CompException('Illegal apic frequency %f' % val)
            self.val = val

    def add_connectors(self):
        self.add_connector('socket', X86ApicProcessorUpConnector())

    def add_processor_x86_apic_objects(self):
        idx = "[%d][%d]" % (self.cpu_cores, self.cpu_threads)
        apics = self.add_pre_obj('apic' + idx, 'x2apic_v2')
        for c in range(self.cpu_cores):
            for t in range(self.cpu_threads):
                apic = apics[c][t]
                thread = self.get_slot('core')[c][t]
                apic.bank.apic_regs.queue = thread
                apic.cpu = thread
                if class_has_iface(thread.classname, 'cycle'):
                    apic.queue = thread
                apic.cpu_bus_divisor = (float(self.freq_mhz.val)
                                        / self.apic_freq_mhz.val)
                if self.apic_type == "P4":
                    apic.physical_broadcast_address = 255
                    apic.bank.apic_regs.Version = 0x14
                    apic.apic_type = "P4"
                elif self.apic_type == "P6":
                    apic.physical_broadcast_address = 15
                    apic.bank.apic_regs.Version = 0x18
                    apic.apic_type = "P6"
                else:
                    raise CompException('Unknown APIC type %s' % self.apic_type)
                thread.apic = apic
                self.get_slot('mem')[c][t].map += [
                    [0xfee00000, apic.bank.apic_regs, 0, 0, 0x4000]]
                thread.cpuid_logical_processor_count = self.cpu_cores * self.cpu_threads

    def intel_cpu_name(self, t, model, sku=""):
        cpu_name = model + " "*(36 - len(model) - len(sku)) + sku
        freq = "%.2fGHz" % (self.freq_mhz.val / 1000.0)
        t.cpuid_processor_name = cpu_name + "  @ " + freq
