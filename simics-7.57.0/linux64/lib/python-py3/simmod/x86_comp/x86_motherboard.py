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


kB = 1<<10
MB = 1<<20
GB = 1<<30

from .x86_comp_cmos import register_cmos_commands
from .x86_connector import (
    X86ApicProcessorDownConnector, X86ResetBusDownConnector,
    X86ProcessorDownConnector)

import os, time
import simics, conf, cmputil, cli
from comp import *
from component_utils import get_highest_2exp

class motherboard_generic(StandardConnectorComponent):
    """The motherboard component is the basic block in an x86 system.
    Processor, northbridge, and southbridge components should be connected
    to this component."""
    _class_desc = 'a PCI-based system with no built-in IO-APIC'
    _do_not_init = object()

    def _initialize(self):
        super()._initialize()

        self.do_init_cmos = True
        self.use_shadow = True
        self.use_hostfs = True
        self.linux_acpi_bug_workaround = True
        self.map_ram = True
        self.use_pc_config = True
        self.use_ioapic = True
        self.cpu_map = {} # Store cpu -> apic, is_logical

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.memory_megs = 0
            self.add_motherboard_generic_objects()
        self.add_motherboard_generic_connectors()


    # NOTE: Should not be a ConfigAttribute, updated from processor connector
    class cpus_per_slot(Attribute):
        """The processors connected to the motherboard in ID order."""
        attrtype = '[[o|n*]*]'
        def _initialize(self):
            self.val = []
        def getter(self):
            if component_utils.get_writing_template() or not self._up.instantiated.val:
                return []
            return self.val
        def setter(self, val):
            self.val = val
            self._up.cpu_list.rebuild()

        def get_cpu_list(self):
            ret = []
            for l in self.val:
                if l:
                    for c in l:
                        ret.append(c)
            return ret

        def add_cpu(self, id, cpu):
            # TODO, should be done in a smarter way
            if len(self.val) <= id:
                self.val += [None] * (id + 1 - len(self.val))
            if self.val[id] == None:
                self.val[id] = [cpu]
            else:
                self.val[id].append(cpu)
            self._up.cpu_list.rebuild()

    class basename(StandardComponent.basename):
        val = "motherboard"

    class rtc_time(SimpleConfigAttribute(default_rtc_start_time, 's')):
        """The date and time of the Real-Time clock. Please note that time-zone
 information is not supported and will be silently dropped when passed to the
 RTC object."""
        def setter(self, val):
            def illegal_value(val):
                simics.SIM_attribute_error(
                    "Expected time format: YYYY-MM-DD HH:MM:SS, "
                    "e.g. 2006-01-25 12:43:31; got '%s'" % val)
                return simics.Sim_Set_Illegal_Value

            # Strip timezone
            # (same logic is used when passing value to RTC in init_cmos())
            m = re.match(r'(\d+)-(\d+)-(\d+) (\d+):(\d+):(\d+)', val)
            if not m:
                return illegal_value(val)
            # m.group(N)... to please fisketur :(
            self.val = '%s-%s-%s %s:%s:%s' % (m.group(1), m.group(2),
                                              m.group(3), m.group(4),
                                              m.group(5), m.group(6))

            # Validate more than just the format
            try:
                time.strptime(self.val, '%Y-%m-%d %H:%M:%S')
            except Exception:
                return illegal_value(val)

            # Issue warning when deprecated time-zone format is used. Time-zone
            # format is supported for backwards compatibility of target
            # scripts, but the underlying RTC does not support it and that
            # should not go silently undetected.
            if len(val.split()) > 2:
                print('Warning: time-zone format not supported by RTC')

    class break_on_reboot(SimpleConfigAttribute(False, 'b')):
        """If true, the simulation will stop when machine is rebooted."""

    class bios(SimpleConfigAttribute('', 's')):
        """The x86 BIOS file to use."""
        def lookup(self):
            if self.val:
                lookup = simics.SIM_lookup_file(self.val)
                if not lookup:
                    print('lookup of bios file %s failed' % self.val)
                    return ''
                return lookup
            return self.val

    class acpi(SimpleConfigAttribute(True, 'b')):
        """Use ACPI when True, default value is True."""

    class system_clock(SimpleConfigAttribute(False, 'b')):
        """If true, the motherboard will contain a clock separate from the processor, which will be used as queue for all devices. The class used for the clock is taken from system_clock_class."""

    class system_clock_class(SimpleConfigAttribute('clock', 's')):
        """The class used for the system_clock."""

    class cpu_list(StandardConnectorComponent.cpu_list):
        def getter(self):
            if component_utils.get_writing_template() or not self._up.instantiated.val:
                return []
            return self.val

        def rebuild(self):
            self.val = self._up.cpus_per_slot.get_cpu_list()

    class component_queue(StandardComponent.component_queue):
        def getter(self):
            if self._up.system_clock.val:
                return self._up.get_slot('clock')
            else:
                if not self._up.cpu_list.val:
                    return None
                return self._up.cpu_list.val[0]

    def mem_bus_callback(self, cnt, attr):
        (memory_megs, memory_ranks) = attr
        self.memory_megs += memory_megs

    def x86_apic_processor_callback(self, id, info):
        (cpu, apic, is_logical) = info
        self.callback_add_cpu(id, cpu, apic, is_logical)

    def x86_processor_callback(self, id, cpu):
        self.callback_add_cpu(id, cpu, None, False)

    def add_motherboard_generic_connectors(self):
        # Memory DIMMs
        dimms = []
        for i in range(4):
            # the first socket is required, can't run without memory
            dimms.append(self.add_connector(
                    None, MemBusDownConnector(
                        'smbus', 0x50 + 2 * i, connect_callback = self.mem_bus_callback,
                        required = (i == 0))))
        self.add_slot('dimm', dimms)

        # Reset
        self.add_connector('reset_bus', X86ResetBusDownConnector('reset'))

    def add_motherboard_generic_objects(self):
        # Clock
        if self.system_clock.val:
            clock = self.add_pre_obj('clock', self.system_clock_class.val)
            clock.freq_mhz = 2000

        # RAM
        dram_space = self.add_pre_obj('dram_space', 'memory-space')
        ram_image = self.add_pre_obj('ram_image', 'image')
        ram = self.add_pre_obj('ram', 'ram')
        ram.image = ram_image

        # Reset
        reset = self.add_pre_obj('reset', 'x86-reset-bus')
        reset.reset_targets = []

        # PC config
        if self.use_pc_config:
            conf_obj = self.add_pre_obj('conf', 'pc-config')
            conf_obj.megs = self.memory_megs
            conf_obj.user_rsdp_address = 0
            conf_obj.build_acpi_tables = self.acpi.val

        # BIOS in ROM
        if self.bios.lookup():
            rom_image = self.add_pre_obj('rom_image', 'image')
            rom = self.add_pre_obj('rom', 'rom')
            rom.image = rom_image

            bios_size = self.get_bios_size()

            self.bios.using_qemu_bios = False
            if bios_size == 128*1024:
                # We guess that we are using a QEMU BIOS if the size of the bios is
                # 128 kb (the Virtutech BIOS is 64 kb)
                self.bios.using_qemu_bios = True

                # Linux ACPI bug workaround not needed for QEMU BIOS
                self.linux_acpi_bug_workaround = False

        # Port space
        port_mem = self.add_pre_obj('port_mem', 'port-space')
        port_mem.map = []
        if self.use_pc_config:
            port_mem.map = [
                [0x402, conf_obj, 0, 0, 1],
                [0x510, conf_obj, 3, 0, 2],
                [0x511, conf_obj, 4, 0, 1],
                [0xfff0, conf_obj, 0, 0, 1],
                [0xfff1, conf_obj, 1, 0, 1],
                [0xfff2, conf_obj, 2, 0, 2]]

        phys_mem = self.add_pre_obj('phys_mem', 'memory-space')
        phys_mem.map = []

        # PC shadow
        if self.use_shadow:
            shadow = self.add_pre_obj('shadow', 'pc-shadow')
            shadow_mem = self.add_pre_obj('shadow_mem', 'memory-space')
            shadow_mem.map = [[0x100000, dram_space, 0, 0, 0x100000]]
            port_mem.map += [
                [0xfff4, shadow, 0,     0, 1],
                [0xfff5, shadow, 0,     1, 1]]

        # Linux ACPI bug workaround
        if self.linux_acpi_bug_workaround:
            rom1_image = self.add_pre_obj('rom1_image', 'image')
            rom1_image.size = 0x10000
            rom1 = self.add_pre_obj('rom1', 'rom')
            rom1.image = rom1_image
            if self.use_pc_config:
                conf_obj.user_rsdp_address = 0xef000

        # Broadcast object
        bcast = self.add_pre_obj('bcast', 'x86_broadcast')
        bcast.images = [ram_image]

        # SMBUS
        self.add_pre_obj('smbus', 'i2c-bus')

    def setup_pcimem(self):
        pci_mem = self.get_slot('northbridge.pci_mem')

        # hotfs
        if self.use_hostfs:
            hfs = self.add_pre_obj('hfs', 'hostfs')
            pci_mem.map += [[0x0ffe81000, hfs,    0, 0, 0x10]]

        # Linux ACPI bug workaround
        if self.linux_acpi_bug_workaround:
            pci_mem.map += [[0x000e0000, self.get_slot('rom1'), 0, 0, 0x10000]]

        self.get_slot('phys_mem').default_target = [pci_mem, 0, 0, None]
        pci_mem.default_target = [self.get_slot('dram_space'), 0, 0, None]


    def copy_shadow(self):
        # TODO, should be done in a smarter way
        if self.use_shadow:
            # move all ROM mappings to shadow memory
            pci_mem = self.get_slot('northbridge.pci_mem')
            self.get_slot('shadow_mem').map += ([x for x in pci_mem.map
                                       if x[0] >= 0xc0000 and x[0] < 0x100000])
            pci_mem.map = [x for x in pci_mem.map
                           if x[0] < 0xc0000 or x[0] >= 0x100000]
            pci_mem.map += ([
                    [0x0000c0000, self.get_slot('shadow'), 0, 0, 0x40000,
                     self.get_slot('shadow_mem'), 1]])

    def get_bios_size(self):
        if not self.bios.lookup():
            return 0
        bios_size = os.stat(self.bios.lookup()).st_size
        # Default bios contains trailing garbage
        if self.bios.val.startswith("rombios-2."):
            return 64 * kB
        if bios_size > MB:
            raise CompException(
                "The BIOS file %s is %d bytes, the limit is 1 MB." % (
                    self.bios.val, bios_size))
        return bios_size

    def pc_config_cpu_list(self):
        return [[cpu, self.cpu_map[cpu][0],
                                self.cpu_map[cpu][1]] for cpu in self.cpu_list.val]

    def callback_add_cpu(self, id, cpu, apic, is_logical):
        self.cpu_map[cpu] = (apic, is_logical)
        self.cpus_per_slot.add_cpu(id, cpu)
        cpu.system = self.get_slot('bcast')
        self.get_slot('reset').reset_targets = self.cpu_list.val
        self.get_slot('bcast').cpus = self.cpu_list.val
        if self.use_pc_config:
            self.get_slot('conf').cpu_list = self.pc_config_cpu_list()
            self.get_slot('conf').ioapic_id = len(self.cpu_list.val)
        # BIOS may access unmapped addresses during boot. Do not break
        # on such events.
        if simics.SIM_class_has_attribute(simics.SIM_get_class(cpu.classname),
                                          "outside_memory_whitelist"):
            cpu.outside_memory_whitelist = [[0, 0]]

    def setup_memory(self):
        if not self.memory_megs:
            raise CompException("No memory DIMMs connected can not setup component.")

        if self.bios.val and not self.bios.lookup():
            raise CompException("BIOS attribute set, but file not found."
                                " Can not setup component.")

        self.get_slot('ram_image').size = self.memory_megs * MB
        self.get_slot('dram_space').map = [
            [0, self.get_slot('ram'), 0, 0, self.memory_megs * MB]]
        if self.use_pc_config:
            self.get_slot('conf').megs = self.memory_megs
            self.get_slot('conf').memory_space = self.get_slot('dram_space')
        if self.map_ram and not self.bios.val:
            self.get_slot('phys_mem').map += [
                [0x00000000, self.get_slot('dram_space'), 0, 0, self.memory_megs * MB]]

        # from may_instantiate
        if not self.bios.lookup():
            return
        bios_size = self.get_bios_size()
        self.get_slot('rom_image').size = bios_size
        pci_mem = self.get_slot('northbridge.pci_mem')
        pci_mem.map += [
            [0x100000000 - bios_size, self.get_slot('rom'), 0, 0, bios_size]]

        if self.bios.using_qemu_bios:
            pci_mem.map += [
                [0x000e0000, self.get_slot('rom'), 0, bios_size - 0x20000, 0x20000]]
        else:
            pci_mem.map += [
                [0x000f0000, self.get_slot('rom'), 0, bios_size - 0x10000, 0x10000]]

        if self.map_ram:
            ram_map = [[0x000000000, self.get_slot('dram_space'), 0, 0, 0xa0000]]
            pci_window_size = 256

            # The QEMU BIOS has a 512 MB PCI window.
            if self.bios.using_qemu_bios:
                pci_window_size = 512

            high_mem = 4096 - pci_window_size
            if self.memory_megs > high_mem:
                high_mem *= MB
                highest = (self.memory_megs - 4096) * 1024 * 1024
                ram_map += [
                    [0x000100000, self.get_slot('dram_space'), 0, 0x100000,
                     high_mem  - 0x100000, None, 0]]
                if highest > 0:
                    ram_map += [[0x100000000, self.get_slot('dram_space'), 0,
                                 0x100000000, highest, None, 0]]
            else:
                megs = (self.memory_megs - 1) * MB
                ram_map += [
                    [0x000100000, self.get_slot('ram'), 0, 0x100000, megs, None, 0]]
            self.get_slot('phys_mem').map += ram_map

    def calc_mtrr_mask(self, classname, size):
        return (~(size - 1)
                & ((1 << simics.SIM_get_class(classname).physical_bits) - 1))

    def set_mtrr(self, cpu):
        def calc_mtrr_mask(size):
            return (~(size - 1) & ((1 << cpu.physical_bits) - 1))

        if hasattr(cpu, 'ia32_mtrr_def_type'):
            cpu.ia32_mtrr_def_type = 0xc00
        elif hasattr(cpu, 'mtrr_def_type'):
            cpu.mtrr_def_type = 0xc00
        else:
            return
        megs_remaining = self.memory_megs
        next_mtrr = 0
        next_base = 0
        if hasattr(cpu, 'ia32_mtrr_physbase0'):
            attribute_base_name = 'ia32_mtrr_physbase'
            attribute_mask_name = 'ia32_mtrr_physmask'
        elif hasattr(cpu, 'mtrr_physbase0'):
            attribute_base_name = 'mtrr_physbase'
            attribute_mask_name = 'mtrr_physmask'
        else:
            assert hasattr(cpu, 'mtrr_base0')
            attribute_base_name = 'mtrr_base'
            attribute_mask_name = 'mtrr_mask'
        while megs_remaining:
            if next_mtrr > 7:
                print(('Warning: %d megabytes of memory not mapped by '
                       'MTRRs' % megs_remaining))
                break
            this_size = get_highest_2exp(megs_remaining)
            mask = calc_mtrr_mask(this_size * 1024 * 1024)

            setattr(cpu, "%s%d" % (attribute_base_name, next_mtrr),
                    next_base | 0x06)
            setattr(cpu, "%s%d" % (attribute_mask_name, next_mtrr),
                    mask | 0x800)
            megs_remaining = megs_remaining - this_size
            next_base = next_base + this_size * 1024 * 1024
            next_mtrr += 1
        if hasattr(cpu, 'mtrr_fix_64k_00000'):
            cpu.mtrr_fix_64k_00000 = 0x0606060606060606
            cpu.mtrr_fix_16k_80000 = 0x0606060606060606
            cpu.mtrr_fix_16k_a0000 = 0
            cpu.mtrr_fix_4k_c0000 = 0
            cpu.mtrr_fix_4k_c8000 = 0
            cpu.mtrr_fix_4k_d0000 = 0
            cpu.mtrr_fix_4k_d8000 = 0
            cpu.mtrr_fix_4k_f0000 = 0
            cpu.mtrr_fix_4k_f8000 = 0
        else:
            cpu.ia32_mtrr_fix_64k_00000 = 0x0606060606060606
            cpu.ia32_mtrr_fix_16k_80000 = 0x0606060606060606
            cpu.ia32_mtrr_fix_16k_a0000 = 0
            cpu.ia32_mtrr_fix_4k_c0000 = 0
            cpu.ia32_mtrr_fix_4k_c8000 = 0
            cpu.ia32_mtrr_fix_4k_d0000 = 0
            cpu.ia32_mtrr_fix_4k_d8000 = 0
            cpu.ia32_mtrr_fix_4k_f0000 = 0
            cpu.ia32_mtrr_fix_4k_f8000 = 0

    def init_bios(self):
        if self.bios.lookup():
            # Load the bios into the ROM area, so that checkpoints not
            # depend on the BIOS file being available all time.
            bios_size = self.get_bios_size()
            simics.SIM_load_file(self.get_slot('northbridge.pci_mem'),
                                 self.bios.val, 0x100000000 - bios_size, 0)

            if not self.bios.using_qemu_bios:
                # Specific machine configuration when using the old
                # Virtutech BIOS

                # Add a mapping for power management
                power = self.get_slot('southbridge.power')
                config_space = power.config_registers
                config_space[0x40 // 4] = 0x8001 # Map I/O @ 0x8000
                config_space[0x80 // 4] = 0x01 # I/O enabled
                power.config_registers = config_space
                power_map = [
                    [0x8000, power, 0,  0x0, 1],
                    [0x8001, power, 0,  0x1, 1],
                    [0x8002, power, 0,  0x2, 1],
                    [0x8003, power, 0,  0x3, 1],
                    [0x8004, power, 0,  0x4, 1],
                    [0x8005, power, 0,  0x5, 1],
                    [0x8006, power, 0,  0x6, 1],
                    [0x8007, power, 0,  0x7, 1],
                    [0x8008, power, 0,  0x8, 1],
                    [0x8009, power, 0,  0x9, 1],
                    [0x800a, power, 0,  0xa, 1],
                    [0x800b, power, 0,  0xb, 1],
                    [0x800c, power, 0,  0xc, 1],
                    [0x800d, power, 0,  0xd, 1],
                    [0x800e, power, 0,  0xe, 1],
                    [0x800f, power, 0,  0xf, 1],
                    [0x8010, power, 0, 0x10, 1],
                    [0x8011, power, 0, 0x11, 1],
                    [0x8012, power, 0, 0x12, 1],
                    [0x8013, power, 0, 0x13, 1],
                    [0x8014, power, 0, 0x14, 1],
                    [0x8015, power, 0, 0x15, 1],
                    [0x8016, power, 0, 0x16, 1],
                    [0x8017, power, 0, 0x17, 1],
                    [0x8018, power, 0, 0x18, 1],
                    [0x8019, power, 0, 0x19, 1],
                    [0x801a, power, 0, 0x1a, 1],
                    [0x801b, power, 0, 0x1b, 1],
                    [0x801c, power, 0, 0x1c, 1],
                    [0x801d, power, 0, 0x1d, 1],
                    [0x801e, power, 0, 0x1e, 1],
                    [0x801f, power, 0, 0x1f, 1],
                    [0x8020, power, 0, 0x20, 1],
                    [0x8021, power, 0, 0x21, 1],
                    [0x8022, power, 0, 0x22, 1],
                    [0x8023, power, 0, 0x23, 1],
                    [0x8024, power, 0, 0x24, 1],
                    [0x8025, power, 0, 0x25, 1],
                    [0x8026, power, 0, 0x26, 1],
                    [0x8027, power, 0, 0x27, 1],
                    [0x8028, power, 0, 0x28, 1],
                    [0x8029, power, 0, 0x29, 1],
                    [0x802a, power, 0, 0x2a, 1],
                    [0x802b, power, 0, 0x2b, 1],
                    [0x802c, power, 0, 0x2c, 1],
                    [0x802d, power, 0, 0x2d, 1],
                    [0x802e, power, 0, 0x2e, 1],
                    [0x802f, power, 0, 0x2f, 1],
                    [0x8030, power, 0, 0x30, 1],
                    [0x8031, power, 0, 0x31, 1],
                    [0x8032, power, 0, 0x32, 1],
                    [0x8033, power, 0, 0x33, 1],
                    [0x8034, power, 0, 0x34, 1],
                    [0x8035, power, 0, 0x35, 1],
                    [0x8036, power, 0, 0x36, 1],
                    [0x8037, power, 0, 0x37, 1]]
                self.get_slot('southbridge.isa_bus').map += power_map

                # Setup PCI to IRQ mapping
                pci_to_isa = self.get_slot('southbridge.pci_to_isa')
                pci_to_isa.pirqrca = 10
                pci_to_isa.pirqrcb = 11
                pci_to_isa.pirqrcc = 10
                pci_to_isa.pirqrcd = 11

    def init_cmos(self):
        if not self.do_init_cmos:
            return
        try:
            rtc = self.get_slot('southbridge.rtc')
        except CompException:
            rtc = None
        if not rtc:
            #print "CMOS device not found - can not write information."
            return
        # set nvram info
        cli.run_command('%s.cmos-init' % self.obj.name)
        cli.run_command('%s.cmos-base-mem 640' % self.obj.name)
        cli.run_command('%s.cmos-extended-mem %d' %
                    (self.obj.name, self.memory_megs - 1))
        m = re.match(r'(\d+)-(\d+)-(\d+) (\d+):(\d+):(\d+)', self.rtc_time.val)
        cli.run_command(('%s.set-date-time '
                     + 'year=%s month=%s mday=%s '
                     + 'hour=%s minute=%s second=%s')
                    % ((rtc.name,) + m.groups()))
        cli.run_command('%s.cmos-boot-dev C' % self.obj.name)
        try:
            flp = self.get_slot('sio.flp')
        except CompException:
            flp = None
        if flp:
            if len(flp.drives):
                cli.run_command('%s.cmos-floppy A "1.44"' % self.obj.name)
            if len(flp.drives) > 1:
                cli.run_command('%s.cmos-floppy B "1.44"' % self.obj.name)
        try:
            ide0 = self.get_slot('southbridge.ide0')
        except CompException:
            try:
                ide0 = self.get_slot('southbridge.ide[0]')
            except CompException:
                ide0 = None
        if ide0 and ide0.master:
            size = ide0.master.disk_sectors
            # Our BIOS does LBA directly: set sectors 63 and heads to x * 16
            bios_S = 63
            # The following would probably work if our BIOS had support
            # for proper 'translation'. Now it seems to fail.
            #if size < 504 * 1024 * 1024 / 512:
            #    bios_H = 16
            #elif size < 1008 * 1024 * 1024 / 512:
            #    bios_H = 32
            #elif size < 2016 * 1024 * 1024 / 512:
            #    bios_H = 64
            #elif size < 4032 * 1024 * 1024 / 512:
            #    bios_H = 128
            if size < 4032 * 1024 * 1024 // 512:
                bios_H = 16
            else:
                # 255 is de facto standard since DOS and early Windows can't
                # handle 256 heads, this is known as the 4GB limit
                bios_H = 255
            bios_C = size // (bios_H * bios_S)
            #if bios_C * bios_H * bios_S != size:
            #    print 'Disk size can not be translated to exact BIOS CHS'
            #    print 'Using CHS: %d %d %d' % (bios_C, bios_H, bios_S)
            cli.run_command('%s.cmos-hd C %d %d %d' % (self.obj.name,
                                                   bios_C, bios_H, bios_S))

    def update_cpus(self):
        cpus_per_slot = []
        for slot_val in self.cpus_per_slot.val:
            val = []
            for cpu in slot_val:
                if cpu == None:
                    val.append(None)
                else:
                    val.append(get_pre_obj_object(cpu))
            cpus_per_slot.append(val)
        self.cpus_per_slot.val = cpus_per_slot
        self.cpu_list.rebuild()

    class component(StandardComponent.component):
        def pre_instantiate(self):
            return self._up.pre_instantiate_motherboard_generic()
        def post_instantiate(self):
            self._up.post_instantiate_motherboard_generic()

    def pre_instantiate_motherboard_generic(self):
        self.setup_memory()
        self.setup_southbridge_pre_instantiate()
        return True

    def setup_southbridge_pre_instantiate(self):
        pass # to be overridden by subclasses

    def post_instantiate_motherboard_generic(self):
        self.init_bios()
        self.init_cmos()
        self.copy_shadow()
        self.update_cpus()
        for cpu in self.cpu_list.val:
            self.set_mtrr(cpu)


# x86_apic_bus_system_component
class motherboard_apic_bus(motherboard_generic):
    """Base class for x86 APIC bus motherboards."""
    _do_not_init = object()

    def setup(self):
        motherboard_generic.setup(self)
        if not self.instantiated.val:
            self.add_motherboard_apic_bus_objects()

    def add_motherboard_apic_bus_objects(self):

        apic_bus = self.add_pre_obj('apic_bus', 'apic-bus')
        apic_bus.apics = []
        apic_bus.ioapic = None
        apic_bus.pic = None

    def setup_apic(self):
        apic_id_list = [ 0, 1, 6, 7, 4, 5, 2, 3,
                         8, 9,14,15,12,13,10,11]
        apics_list = []
        la = len(apic_id_list)
        for i in range(len(self.cpu_list.val)):
            apics_list += [self.cpu_list.val[i].apic]
            a_id = (i//la)*la + apic_id_list[i % la]
            self.cpu_list.val[i].apic.apic_id = a_id
            try:
                self.cpu_list.val[i].cpuid_physical_apic_id = a_id
            except:
                pass
        self.get_slot('apic_bus').apics = apics_list
        i = len(self.cpu_list.val)
        if self.get_slot('apic_bus').ioapic != None:
            for ioapic in self.get_slot('apic_bus').ioapic:
                try:
                    ioapic.ioapic_id = ((i//la)*la + apic_id_list[i % la]) << 24
                except:
                    ioapic.ioapic_id = i << 24
                i = i + 1
        self.cpu_list.val[0].apic.iface.apic_cpu.power_on(1, self.cpu_list.val[0].cpuid_physical_apic_id)
        for c in self.cpu_list.val[1:]:
            c.iface.x86_reg_access.set_activity_state(simics.X86_Activity_Wait_For_SIPI)
            c.apic.iface.apic_cpu.power_on(0, c.cpuid_physical_apic_id)

    class component(StandardComponent.component):
        def pre_instantiate(self):
            return self._up.pre_instantiate_motherboard_generic()
        def post_instantiate(self):
            self._up.post_instantiate_motherboard_generic()
            self._up.post_instantiate_motherboard_apci_bus()

    def post_instantiate_motherboard_apci_bus(self):
        self.setup_apic()

# x86_apic_system_component
class motherboard_apic(motherboard_apic_bus):
    """Base class for x86 APIC motherboards."""
    _do_not_init = object()

    def setup(self):
        motherboard_apic_bus.setup(self)
        if self.use_ioapic and not self.instantiated.val:
            self.add_motherboard_apic_objects()
        self.add_motherboard_apic_connectors()

    def add_motherboard_apic_connectors(self):
        # Processors
        cpus = []
        clock_slot = None
        if self.system_clock.val:
            clock_slot = 'clock'
        for i in range(8):
            cpus.append(self.add_connector('', X86ApicProcessorDownConnector(
                        i, 'phys_mem', 'port_mem', 'apic_bus', self.x86_apic_processor_callback,
                        clock = clock_slot)))
        self.add_slot('cpu', cpus)

    def add_motherboard_apic_objects(self):
        ioapic = self.add_pre_obj('ioapic', 'io-apic')
        ioapic.apic_bus = self.get_slot('apic_bus')
        ioapic.ioapic_id = 0
        self.get_slot('apic_bus').ioapic = [ioapic]

    def setup_northbridge_ioapic(self):
        self.get_slot('northbridge.pci_mem').map += [
            [0xfec00000, self.get_slot('ioapic'), 0, 0, 0x20]]

    def setup_northbridge(self):

        # start north_bridge_component, x86_chipset
        nbb = self.get_slot('northbridge.bridge')
        ps = self.get_slot('port_mem')
        ps.map += [
            [0xcf8, nbb, 0, 0xcf8, 4],
            [0xcf9, nbb, 0, 0xcf9, 2],
            [0xcfa, nbb, 0, 0xcfa, 2],
            [0xcfb, nbb, 0, 0xcfb, 1],
            [0xcfc, nbb, 0, 0xcfc, 4],
            [0xcfd, nbb, 0, 0xcfd, 2],
            [0xcfe, nbb, 0, 0xcfe, 2],
            [0xcff, nbb, 0, 0xcff, 1]]
        ps.default_target = [self.get_slot('northbridge.pci_io'), 0, 0, None]
        # end

class motherboard_x86_simple(motherboard_apic):
    """X86 simple motherboard."""
    _class_desc = "simple X86 motherboard"
    _do_not_init = object()

    def setup(self):
        self.use_shadow = False
        self.use_pc_config = False
        self.use_ioapic = False
        motherboard_apic.setup(self)

class motherboard_x86_simple_no_apic(motherboard_generic):
    """X86 simple motherboard for processors without APIC."""
    _class_desc = "simple MB for processors without APIC"
    _do_not_init = object()

    class component(StandardComponent.component):
        def pre_instantiate(self):
            return self._up.pre_instantiate_motherboard_generic()
        def post_instantiate(self):
            self._up.post_instantiate_motherboard_generic()

    def setup(self):
        motherboard_generic.setup(self)
        self.use_shadow = False
        self.add_motherboard_connectors()

    def add_motherboard_connectors(self):
        # Processors
        cpus = []
        clock_slot = None
        if self.system_clock.val:
            clock_slot = 'clock'
        for i in range(1):
            cpus.append(self.add_connector('', X86ProcessorDownConnector(
                        i, 'phys_mem', 'port_mem', self.x86_processor_callback,
                        clock = clock_slot)))
        self.add_slot('cpu', cpus)
