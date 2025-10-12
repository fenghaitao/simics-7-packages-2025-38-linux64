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


import simics
import cli
import math
from comp import *

class simple_memory_module(StandardComponent):
    """A simple memory module."""
    _class_desc = "simple memory module"

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_simple_memory_module_objects()

    def add_simple_memory_module_objects(self):
        self.add_connector(
            'mem_bus', 'mem-bus', False, False, False, simics.Sim_Connector_Direction_Up)

    class basename(StandardComponent.basename):
        val = "dimm"

    class memory_megs(SimpleConfigAttribute(1024, 'i')):
        """MB memory."""

    class component_connector(Interface):
        def get_check_data(self, cnt):
            return [self._up.memory_megs.val, 1]
        def get_connect_data(self, cnt):
            return [self._up.memory_megs.val, 1]
        def check(self, cnt, attr):
            return True
        def connect(self, cnt, attr):
            pass
        def disconnect(self, cnt):
            pass

class memory_module_comp(StandardComponent):
    '''This class implements the logic for calculating memory module
    parameters, but knows nothing about the actual SPD layout. The subclasses
    must implement all the methods that read/write actual SPD bytes.'''
    _class_desc = 'base memory module'
    _do_not_init = object()

    @staticmethod
    def is_po2(val):
        if val and not(val & (val - 1)):
            return 1
        return 0

    def _initialize(self):
        super()._initialize()
        self.byte = [0] * 256
        self.dflt_size_dep = ['r', 'c', 'd', 'b', 'w']
        self.user_size_dep = []

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_memory_module_objects()
        self.add_memory_module_connectors()

    def add_memory_module_objects(self):
        sdram_spd_image = self.add_pre_obj('sdram_spd_image', 'image')
        sdram_spd_image.size = 0x2000
        sdram_spd = self.add_pre_obj('sdram_spd', 'PCF8582C')
        sdram_spd.image = sdram_spd_image
        sdram_spd.address_bits = 8
        sdram_spd.address = 0
        sdram_spd.address_mask = 0x7f

    def add_memory_module_connectors(self):
        self.add_connector(
            'mem_bus', 'mem-bus', False, True, False, simics.Sim_Connector_Direction_Up)

    class component_connector(Interface):
        def get_check_data(self, cnt):
            return [self._up.byte[2],  # Memory type
                    self._up.get_size(), self._up.ranks.getter(),
                    self._up.module_data_width.getter(),
                    self._up.ecc_width.getter()]
        def get_connect_data(self, cnt):
            return [self._up.get_size(), self._up.ranks.getter()]
        def check(self, cnt, attr):
            return True
        def connect(self, cnt, attr):
            (i2c_bus, spd_address) = attr
            self._up.get_slot('sdram_spd').address = spd_address
            if i2c_bus.classname == 'i2c-bus':
                self._up.get_slot('sdram_spd').i2c_bus = i2c_bus
            elif i2c_bus.classname == 'i2c-link-endpoint':
                self._up.get_slot('sdram_spd').i2c_link_v2 = i2c_bus
                i2c_bus.device = self._up.get_slot('sdram_spd')
            else:
                raise comp.CompException('mem-bus can only connect to '
                                         'i2c-bus or i2c-link-endpoint')
        def disconnect(self, cnt):
            raise comp.CompException('disconnecting mem-bus '
                                     'connection not allowed')

    class component(StandardComponent.component):
        def post_instantiate(self):
            self._up.set_spd()

    def order_size_dep(self, val):
        n = []
        for i in self.dflt_size_dep:
            if i != val:
                n.append(i)
            else:
                self.user_size_dep.append(i)
        self.dflt_size_dep = n

    def get_size_params(self):
        d = self.rank_density.getter()
        r = self.rows.getter()
        c = self.columns.getter()
        b = self.banks.getter()
        w = self.module_data_width.getter() - self.ecc_width.getter()
        return (d, r, c, b, w)

    def size_dep_ok(self):
        (d, r, c, b, w) = self.get_size_params()
        return d == (2**(r + c - 23)) * b * w

    def calc_r(self):
        (d, r, c, b, w) = self.get_size_params()
        return int(math.log(d // ((2**(c - 23)) * b * w), 2))

    def calc_c(self):
        (d, r, c, b, w) = self.get_size_params()
        return int(math.log(d // ((2**(r - 23)) * b * w), 2))

    def calc_b(self):
        (d, r, c, b, w) = self.get_size_params()
        return int(d // (((2**(r + c - 23)) * w)))

    def calc_d(self):
        (d, r, c, b, w) = self.get_size_params()
        return int((2**(r + c - 23)) * b * w)

    def calc_w(self):
        (d, r, c, b, w) = self.get_size_params()
        return int(d // ((2**(r + c - 23)) * b))

    def calc_list(self, list):
        for i in list:
            if self.size_dep_ok():
                break
            if i == 'r':
                r = self.calc_r()
                self.set_val_rows(r)
            elif i == 'c':
                c = self.calc_c()
                self.set_val_columns(c)
            elif i == 'b':
                b = self.calc_b()
                self.set_val_banks(b)
            elif i == 'd':
                d = self.calc_d()
                self.set_val_rank_density(d)
            elif i == 'w':
                w = self.calc_w() + self.ecc_width.getter()
                self.set_val_module_data_width(w)
            else:
                print("ERROR, no parameter.")
                return

    def calc_size_dep(self):
        self.calc_list(self.dflt_size_dep)
        if self.size_dep_ok():
            return
        print ("Warning, conflicting memory SPD parameters, "
               "overriding user set values.")
        self.calc_list(self.user_size_dep)
        if not self.size_dep_ok():
            print ("ERROR, could not find any non conflicting memory SPD "
                   "parameters.")
            if (self.ecc_width.getter() > 0):
                print ("NOTE, do not forget to specify module data width when "
                       "setting ECC width.")
            just = [cli.Just_Left, cli.Just_Right]
            t = []
            t += [["Rank density", self.rank_density.getter()]]
            t += [["Rows", self.rows.getter()]]
            t += [["Columns", self.columns.getter()]]
            t += [["Banks", self.banks.getter()]]
            t += [["Module data width", self.module_data_width.getter()]]
            t += [["ECC data width", self.ecc_width.getter()]]
            t = [["Parameter", "Value"]] + t
            cli.print_columns(just, t)

    def set_spd(self):
        self.calc_size_dep()
        self.set_ecc_bytes()
        self.generate_checksum()
        image = self.get_slot('sdram_spd_image')
        image.iface.image.set(0, bytes(self.byte))

    def get_size(self):
        return self.rank_density.getter() * self.ranks.getter()

    class rows(ConfigAttribute):
        '''Number of rows.'''
        attrtype = 'i'
        def setter(self, val):
            if val < 0:
                return simics.Sim_Set_Illegal_Value
            self._up.set_val_rows(val)
            self._up.order_size_dep('r')

    class columns(ConfigAttribute):
        '''Number of columns.'''
        attrtype = 'i'
        def setter(self, val):
            if val < 0:
                return simics.Sim_Set_Illegal_Value
            self._up.set_val_columns(val)
            self._up.order_size_dep('c')

    class memory_megs(Attribute):
        '''Total about of memory in MB.'''
        attrtype = 'i'
        attrattr = simics.Sim_Attr_Pseudo
        def getter(self):
            return self._up.get_size()

    class ranks(ConfigAttribute):
        '''Number of ranks (logical banks).'''
        attrtype = 'i'
        def setter(self, val):
            if not self._up.is_po2(val):
                simics.SIM_attribute_error("%d is not a power of 2" % val)
                return simics.Sim_Set_Illegal_Value
            self._up.set_val_ranks(val)

    class module_data_width(ConfigAttribute):
        '''The module SDRAM width (including ECC width if enabled).'''
        attrtype = 'i'
        def setter(self, val):
            try:
                self._up.set_val_module_data_width(val)
            except ValueError:
                return simics.Sim_Set_Illegal_Value
            self._up.order_size_dep('w')

    class banks(ConfigAttribute):
        '''Number of banks.'''
        attrtype = 'i'
        def setter(self, val):
            if not self._up.is_po2(val):
                return simics.Sim_Set_Illegal_Value
            self._up.set_val_banks(val)
            self._up.order_size_dep('b')

    class rank_density(ConfigAttribute):
        '''The rank density.'''
        attrtype = 'i'
        def setter(self, val):
            if not self._up.is_po2(val):
                simics.SIM_attribute_error("%d is not a power of 2" % val)
                return simics.Sim_Set_Illegal_Value
            self._up.user_rank_density = val
            try:
                self._up.set_val_rank_density(val)
            except ValueError:
                return simics.Sim_Set_Illegal_Value
            self._up.order_size_dep('d')

    class primary_width(SimpleConfigAttribute(None, 'i')):
        '''Primary SDRAM width.'''

    class ecc_width(SimpleConfigAttribute(None, 'i')):
        '''The error correction width.'''

    class module_type(SimpleConfigAttribute(None, 's')):
        '''Type of memory.'''

    class cas_latency(SimpleConfigAttribute(None, 'i')):
        '''CAS-latency; each set bit corresponds to a latency
        the memory can handle.'''

class sdram_to_ddr2_base_comp(memory_module_comp):
    '''Base class for SDRAM, DDR1 and DDR2 memory modules. It implements all
    the SPD getter/setters that are shared between all three memory types'''
    _do_not_init = object()

    def _initialize(self):
        memory_module_comp._initialize(self)

        # default bytes
        self.byte[0]  = 0x80   # Number of Serial PD Bytes written during
                               # module production
        self.byte[1]  = 0x08   # Total number of Bytes in Serial PD device
        self.byte[2]  = 0x07   # Fundamental Memory Type
        self.byte[3]  = 0x0d   # Number of Row Addresses on this assembly
        self.byte[4]  = 0x0a   # Number of Column Addresses on this assembly
        self.byte[5]  = 0x01   # Number of DIMM Banks/Ranks
        self.byte[6]  = 0x40   # Data Width of this assembly
        self.byte[7]  = 0x00   # Reserved
        self.byte[8]  = 0x04   # Voltage Interface Level of this assembly
        self.byte[9]  = 0x25   # SDRAM Cycle time at Maximum Supported
                               # CAS Latency (CL) CL=X
        self.byte[10] = 0x60   # SDRAM Access from Clock
        self.byte[11] = 0x00   # DIMM configuration type
                               # (Non-parity Parity or ECC)
        self.byte[12] = 0x82   # Refresh Rate/Type
        self.byte[13] = 0x08   # Primary SDRAM Width
        self.byte[14] = 0x00   # Error Checking SDRAM Width
        self.byte[15] = 0x00   # Minimum clock delay, back-to-back random
                               # column access
        self.byte[16] = 0x0c   # SDRAM Device Attributes: Burst Lengths
                               # Supported
        self.byte[17] = 0x04   # SDRAM Device Attributes: Number of Banks on
                               # SDRAM Device
        self.byte[18] = 0x38   # SDRAM Device Attributes: CAS Latency
        self.byte[19] = 0x00   # Reserved
        self.byte[20] = 0x02   # DIMM Type Information
        self.byte[21] = 0x00   # SDRAM Module Attributes
        self.byte[22] = 0x01   # SDRAM Device Attributes: General
        self.byte[23] = 0x50   # Minimum Clock Cycle at CLX-1
        self.byte[24] = 0x60   # Maximum Data Access Time (tAC)
                               # from Clock at CLX-1
        self.byte[25] = 0x50   # Minimum Clock Cycle at CLX-2
        self.byte[26] = 0x60   # Maximum Data Access Time (tAC)
                               # from Clock at CLX-2
        self.byte[27] = 0x3c   # Minimum Row Precharge Time (tRP)
        self.byte[28] = 0x1e   # Minimum Row Active to Row Active delay (tRRD)
        self.byte[29] = 0x3c   # Minimum RAS to CAS delay (tRCD)
        self.byte[30] = 0x2d   # Minimum Active to Precharge Time (tRAS)
        self.byte[31] = 0x40   # Module Rank Density
        self.byte[32] = 0x60   # Address and Command Input Setup Time Before
                               # Clock (tIS)
        self.byte[33] = 0x60   # Address and Command Input Hold Time After
                               # Clock (tIH)
        self.byte[34] = 0x40   # Data Input Setup Time Before Clock (tDS)
        self.byte[35] = 0x40   # Data Input Hold Time After Clock (tDH)
        self.byte[36] = 0x3c   # Write recovery time (tWR)
        self.byte[37] = 0x28   # Internal write to read command delay (tWTR)
        self.byte[38] = 0x1e   # Internal read to precharge command delay (tRTP)
        self.byte[39] = 0x00   # Memory Analysis Probe Characteristics
        self.byte[40] = 0x00   # Extension of Byte 41 tRC and Byte 42 tRFC
        self.byte[41] = 0x3c   # SDRAM Device Minimum Active to
                               # Active/Auto Refresh Time (tRC)
        self.byte[42] = 0x69   # SDRAM Device Minimum Auto-Refresh to
                               # Active/Auto-Refresh Command Period (tRFC)
        self.byte[43] = 0x43   # SDRAM Device Maximum device cycle time (tCKmax)
        self.byte[44] = 0x23   # SDRAM Device maximum skew between
                               # DQS and DQ signals (tDQSQ)
        self.byte[45] = 0x2d   # SDRAM Device Maximum Read DataHold Skew
                               # Factor (tQHS)
        self.byte[46] = 0x00   # PLL Relock Time

        # Some software accepts only Micron, Smart or Samsung memories.
        self.byte[64] = 0xce   # Manufacturer JEDEC ID Code (default Samsung)

    def set_ecc_bytes(self):
        if self.byte[14] == 0:
            return
        self.byte[6] |= self.byte[14]
        self.byte[11] |= 0x2

    def generate_checksum(self):
        self.byte[63] = sum(self.byte[:63]) % 256

    class rows(memory_module_comp.rows):
        def getter(self):
            return self._up.byte[3]

    def set_val_rows(self, val):
        self.byte[3] = val

    class columns(memory_module_comp.columns):
        def getter(self):
            return self._up.byte[4]

    def set_val_columns(self, val):
        self.byte[4] = val

    class module_data_width(memory_module_comp.module_data_width):
        def getter(self):
            return 256 * self._up.byte[7] + self._up.byte[6]

    def set_val_module_data_width(self, val):
        if val < 256:
            self.byte[6] = val
        else:
            self.byte[6] = val % 256
            self.byte[7] = val // 256

    class primary_width(memory_module_comp.primary_width):
        def getter(self):
            return self._up.byte[13]
        def setter(self, val):
            if not self._up.is_po2(val):
                return simics.Sim_Set_Illegal_Value
            self._up.byte[13] = val

    class ecc_width(memory_module_comp.ecc_width):
        def getter(self):
            return self._up.byte[14]
        def setter(self, val):
            if not val in (0, 8):
                return simics.Sim_Set_Illegal_Value
            self._up.byte[14] = val

    class banks(memory_module_comp.banks):
        def getter(self):
            return self._up.byte[17]

    def set_val_banks(self, val):
        self.byte[17] = val

    class cas_latency(memory_module_comp.cas_latency):
        def getter(self):
            return self._up.byte[18]
        def setter(self, val):
            self._up.byte[18] = val & 0xff

class ddr_memory_module_comp(sdram_to_ddr2_base_comp):
    '''The "ddr_memory_module_comp" component represents a DDR memory module.'''
    _class_desc = 'a DDR memory module'

    class basename(sdram_to_ddr2_base_comp.basename):
        val = "ddr_memory"

    rank_density_little = {
        0x01 :   4,
        0x02 :   8,
        0x04 :  16,
        0x08 :  32,
        0x10 :  64,
        0x20 : 128,
        0x40 : 256,
        0x80 : 512}
    rank_density_big = {
        0x01 : 1024,
        0x02 : 2048,
        0x04 : 4096,
        0x08 :   32,
        0x10 :   64,
        0x20 :  128,
        0x40 :  256,
        0x80 :  512}

    def _initialize(self):
        sdram_to_ddr2_base_comp._initialize(self)
        self.user_rank_density = 0

    class speed(ConfigAttribute):
        '''PC standard speed. Supported values are PC2700 and none.'''
        attrtype = 's'
        def _initialize(self):
            self.val = "none"
        def getter(self):
            return self.val
        def setter(self, val):
            if val == "PC2700":
                self.val = val
                self._up.byte[8] = 0x40
                self._up.byte[9] = 0x60
                self._up.byte[10] = 0x70
                self._up.byte[12] = 0x82
                self._up.byte[15] = 0x01
                self._up.byte[16] = 0x0e
                self._up.byte[18] = 0x0c
                self._up.byte[19] = 0x01
                self._up.byte[20] = 0x02
                self._up.byte[22] = 0xc0
                self._up.byte[23] = 0x75
                self._up.byte[24] = 0x70
                self._up.byte[25] = 0
                self._up.byte[26] = 0
                self._up.byte[27] = 0x48
                self._up.byte[28] = 0x30
                self._up.byte[29] = 0x48
                self._up.byte[30] = 0x2a
                self._up.byte[32] = 0x75
                self._up.byte[33] = 0x75
                self._up.byte[34] = 0x45
                self._up.byte[35] = 0x45
                self._up.byte[36] = 0
                self._up.byte[37] = 0
                self._up.byte[38] = 0
                self._up.byte[39] = 0
                self._up.byte[40] = 0
                self._up.byte[41] = 0x3c
                self._up.byte[42] = 0x48
                self._up.byte[43] = 0x30
                self._up.byte[44] = 0x2d
                self._up.byte[45] = 0x55
                self._up.byte[46] = 0x00
            elif val == "none":
                self.val = val
            else:
                return simics.Sim_Set_Illegal_Value

    class banks(sdram_to_ddr2_base_comp.banks):
        '''Number of banks.'''

    class cas_latency(sdram_to_ddr2_base_comp.cas_latency):
        '''CAS-latency; each set bit corresponds to a latency
        the memory can handle.'''

    class columns(sdram_to_ddr2_base_comp.columns):
        '''Number of columns.'''

    class ecc_width(sdram_to_ddr2_base_comp.ecc_width):
        '''The error correction width.'''

    class module_data_width(sdram_to_ddr2_base_comp.module_data_width):
        '''The module SDRAM width (including ECC width if enabled).'''

    class primary_width(sdram_to_ddr2_base_comp.primary_width):
        '''Primary SDRAM width.'''

    class rows(sdram_to_ddr2_base_comp.rows):
        '''Number of rows.'''

    class ranks(sdram_to_ddr2_base_comp.ranks):
        '''Number of ranks (logical banks).'''
        def getter(self):
            return self._up.byte[5]

    def set_val_ranks(self, val):
        self.byte[5] = val

    class rank_density(sdram_to_ddr2_base_comp.rank_density):
        '''The rank density.'''
        def getter(self):
            if self._up.user_rank_density <= 64 and self._up.user_rank_density != 0:
                density = self._up.rank_density_little
            else:
                density = self._up.rank_density_big

            assert self._up.byte[31] in density
            return density[self._up.byte[31]]

    def set_val_rank_density(self, val):
        if self.user_rank_density <= 64 and self.user_rank_density != 0:
            density = self.rank_density_little
        else:
            density = self.rank_density_big

        assert val in list(density.values())
        for rank in density:
            if density[rank] == val:
                self.byte[31] = rank
                return

    class module_type(sdram_to_ddr2_base_comp.module_type):
        '''Type of memory.'''
        def getter(self):
            return "RDIMM" if self._up.byte[21] & 0x26 else "UDIMM"
        def setter(self, val):
            if val == "RDIMM":
                self._up.byte[21] |= 0x26
            elif val == "UDIMM":
                self._up.byte[21] &= ~0x26
            else:
                return simics.Sim_Set_Illegal_Value

class ddr2_memory_module_comp(sdram_to_ddr2_base_comp):
    '''The "ddr2_memory_module_comp" component represents a DDR2 memory module.'''
    _class_desc = 'a DDR2 memory module'

    class basename(sdram_to_ddr2_base_comp.basename):
        val = 'ddr2_memory'

    rank_density_val = {
        0x01 :  1024,
        0x02 :  2048,
        0x04 :  4096,
        0x08 :  8192,
        0x10 : 16384,
        0x20 :   128,
        0x40 :   256,
        0x80 :   512}

    def _initialize(self):
        sdram_to_ddr2_base_comp._initialize(self)
        self.byte[2]  = 0x08   # Fundamental Memory Type
        self.byte[5]  = 0x60   # Number of DIMM Ranks
        self.byte[8]  = 0x05   # Voltage Interface Level of this assembly
        self.byte[17] = 0x08   # SDRAM Device Attributes: Number of Banks on
                               # SDRAM Device
        self.byte[18] = 0x3c   # CL (2, 3, 4, 5, 6)
        self.byte[23] = 0x05   # CAS X - 1
        self.byte[24] = 0x05   # CL X - 1
        self.byte[31] = 0x80   # Module Rank Density

    class banks(sdram_to_ddr2_base_comp.banks):
        '''Number of banks.'''

    class cas_latency(sdram_to_ddr2_base_comp.cas_latency):
        '''CAS-latency; each set bit corresponds to a latency
        the memory can handle.'''

    class columns(sdram_to_ddr2_base_comp.columns):
        '''Number of columns.'''

    class ecc_width(sdram_to_ddr2_base_comp.ecc_width):
        '''The error correction width.'''

    class module_data_width(sdram_to_ddr2_base_comp.module_data_width):
        '''The module SDRAM width (including ECC width if enabled).'''

    class primary_width(sdram_to_ddr2_base_comp.primary_width):
        '''Primary SDRAM width.'''

    class rows(sdram_to_ddr2_base_comp.rows):
        '''Number of rows.'''

    class ranks(sdram_to_ddr2_base_comp.ranks):
        '''Number of ranks (logical banks).'''
        def getter(self):
            return (self._up.byte[5] & 0x3) + 1

    def set_val_ranks(self, val):
        self.byte[5] = (self.byte[5] & 0xf8) | ((val - 1) & 0x3)

    class rank_density(sdram_to_ddr2_base_comp.rank_density):
        '''The rank density.'''
        def getter(self):
            assert self._up.byte[31] in self._up.rank_density_val
            return self._up.rank_density_val[self._up.byte[31]]

    def set_val_rank_density(self, val):
        assert val in list(self.rank_density_val.values())
        for rank in self.rank_density_val:
            if self.rank_density_val[rank] == val:
                self.byte[31] = rank
                return

    class module_type(sdram_to_ddr2_base_comp.module_type):
        '''Type of memory.'''
        def getter(self):
            if self._up.byte[20] == 0x01:
                return "RDIMM"
            elif self._up.byte[20] == 0x02:
                return "UDIMM"
            elif self._up.byte[20] == 0x04:
                return "SO-DIMM"
            elif self._up.byte[20] == 0x08:
                return "Micro-DIMM"
            elif self._up.byte[20] == 0x10:
                return "Mini-RDIMM"
            elif self._up.byte[20] == 0x20:
                return "Mini-UDIMM"
            return "Unknown"
        def setter(self, val):
            if val == "RDIMM":
                self._up.byte[20] = 0x01
            elif val == "UDIMM":
                self._up.byte[20] = 0x02
            elif val == "SO-DIMM":
                self._up.byte[20] = 0x04
            elif val == "Micro-DIMM":
                self._up.byte[20] = 0x08
            elif val == "Mini-RDIMM":
                self._up.byte[20] = 0x10
            elif val == "Mini-UDIMM":
                self._up.byte[20] = 0x20
            else:
                return simics.Sim_Set_Illegal_Value

class ddr3_memory_module_comp(memory_module_comp):
    '''The "ddr3_memory_module_comp" component represents a DDR3 memory module.'''
    _class_desc = 'a DDR3 memory module'

    class basename(memory_module_comp.basename):
        val = 'ddr3_memory'

    def _initialize(self):
        memory_module_comp._initialize(self)

        # Default SPD data (timing values from MT4JTF6464AY-1G4B1)
        self.byte[0] |= 0 << 7  # CRC coverage
        self.byte[0] |= 1 << 4  # SPD bytes total
        self.byte[0] |= 1       # SPD bytes used
        self.byte[1] = 0x10     # DDR3 SPD revision 1.0
        self.byte[2] = 0x0b     # DRAM device type (DDR3)
        self.byte[3] = 0x2      # Module type (UDIMM)
        self.byte[4] = 3        # SDRAM capacity = 1GB
        self.byte[5] = 1        # Columns == 10
        self.byte[6] |= 1 << 2  # 1.2x V operable
        self.byte[6] |= 1 << 1  # 1.35 V operable
        self.byte[6] |= 0       # 1.5 V operable (yes, inversed polarity!)
        self.byte[7] |= 0x2     # SDRAM device with (16 bits)
        self.byte[8] |= 0x3     # Module bus width (64 bits)
        self.byte[9] = 0x52     # Fine timebase dividend / divisor
        self.byte[10] = 1       # Medium timebase dividend
        self.byte[11] = 8       # Medium timebase divisor
        self.byte[12] = 0xc     # SDRAM minimum cycle time (tckmin)
        self.byte[14] = 0x7c    # CAS latencies supported
        self.byte[15] = 0x00    # CAS latencies supported
        self.byte[16] = 0x69    # Minimum CAS latency time
        self.byte[17] = 0x78    # Minimum write recovery time
        self.byte[18] = 0x6c    # Minimum RAS# to CAS# delay time
        self.byte[19] = 0x3c    # Minimum row active to row active delay time
        self.byte[20] = 0x6c    # Minimum row precharge delay time
        self.byte[21] = 0x11    # Minimum active to precharge delay time
        self.byte[22] = 0x20    # Minimum active to precharge delay time
        self.byte[23] = 0x8c    # Minimum active to active/refresh delay
        self.byte[24] = 0x70    # Minimum refresh recovery delay time
        self.byte[25] = 0x03    # Minimum refresh recovery delay time
        self.byte[26] = 0x3c    # Minimum internal write to read command dt
        self.byte[27] = 0x3c    # Minimum internal read to precharge command
        self.byte[28] = 0x1     # Minimum four activate window delay time
        self.byte[29] = 0x68    # Minimum four activate window delay time
        self.byte[30] = 0x82    # SDRAM optional features
        self.byte[31] = 0x05    # SDRAM thermal and refresh options
        self.byte[32] = 0       # Module thermal sensor
        self.byte[33] = 0       # SDRAM device type

    def generate_checksum(self):
        crc_byte = (126, 117)[(self.byte[0] >> 7) & 1]

        crc = 0
        for byte in self.byte[:crc_byte]:
            crc = crc ^ (byte << 8)
            for i in range(8):
                if crc & 0x8000:
                    crc <<= 1
                    crc ^= 0x1021
                else:
                    crc <<= 1

        crc = crc & 0xffff
        self.byte[126] = crc & 0xff
        self.byte[127] = crc >> 8

    def set_ecc_bytes(self):
        pass

    # rows (0 = 12 rows, 1 = 13 rows, and so on)
    class rows(memory_module_comp.rows):
        '''Number of rows.'''
        def getter(self):
            return ((self._up.byte[5] >> 3) & 0x7) + 12

    def set_val_rows(self, val):
        self.byte[5] &= ~(0x7 << 3)
        self.byte[5] |= ((val - 12) & 0x7) << 3

    # columns (0 = 9 columns, 1 = 10 columns, and so on)
    class columns(memory_module_comp.columns):
        '''Number of columns.'''
        def getter(self):
            return (self._up.byte[5] & 0x7) + 9

    def set_val_columns(self, val):
        self.byte[5] &= ~0x7
        self.byte[5] |= (val - 9) & 0x7

    # ranks (0 = 1 rank, 1 = 2 ranks, and so on)
    class ranks(memory_module_comp.ranks):
        '''Number of ranks (logical banks).'''
        def getter(self):
            return ((self._up.byte[7] >> 3) & 0x7) + 1

    def set_val_ranks(self, val):
        self.byte[7] &= ~(0x7 << 3)
        self.byte[7] |= ((val - 1) & 0x7) << 3

    # rank density (in mega _bits_, 0 = 256 Mb, 1 = 512 Mb, and so on)
    # This is a bit ugly - DDR3 doesn't store the rank density, it stores
    # the SDRAM total capacity (not the same thing as the total module
    # capacity), which depends on both the SDRAM width, and the module bus
    # width. To allow create-and-connect to work with DDR3, and to keep the
    # user interface simple, we keep the rank-density attribute but recalculate
    # the rank-density to the SDRAM capacity
    class rank_density(memory_module_comp.rank_density):
        '''The rank density.'''
        def getter(self):
            sdram_capacity = (256 << (self._up.byte[4] & 0xf))
            primary_bus_width = (self._up.module_data_width.getter()
                                 - self._up.ecc_width.getter())
            rank_density = (sdram_capacity * primary_bus_width
                            // (8 * self._up.primary_width.getter()))
            return rank_density

    def set_val_rank_density(self, val):
        self.byte[4] &= ~0xf
        primary_bus_width = (self.module_data_width.getter()
                             - self.ecc_width.getter())
        sdram_capacity = (val * 8 * self.primary_width.getter()
                          // primary_bus_width)
        if sdram_capacity < 256:
            simics.SIM_attribute_error('SDRAM capacity must be at least 256 Mb. '
                                'Check your configuration of SDRAM width '
                                'and the module data bus width')
            raise ValueError()
        self.byte[4] |= (sdram_capacity.bit_length() - 9) & 0xf

    # module data width
    class module_data_width(memory_module_comp.module_data_width):
        '''The module SDRAM width (including ECC width if enabled).'''
        def getter(self):
            return ((8, 16, 32, 64)[self._up.byte[8] & 0x3]
                    + self._up.ecc_width.getter())

    def set_val_module_data_width(self, val):
        # Need to update the rank density / SDRAM capacity
        val -= self.ecc_width.getter()
        rank_density = self.rank_density.getter()
        self.byte[8] &= ~0x7
        self.byte[8] |= (val.bit_length() - 4) & 0x7
        self.set_val_rank_density(rank_density)

    # primary (SDRAM device) width (0 = 4 bits, 1 = 8 bits, 2 = 16 bits, ...)
    class primary_width(memory_module_comp.primary_width):
        '''Primary SDRAM width.'''
        def getter(self):
            return 4 << (self._up.byte[7] & 0x7)

        def setter(self, val):
            if not self._up.is_po2(val):
                return simics.Sim_Set_Illegal_Value

            # Need to update the rank density / SDRAM capacity
            rank_density = self._up.rank_density.getter()
            self._up.byte[7] &= ~0x7
            self._up.byte[7] |= (val.bit_length() - 3) & 0x7

            try:
                self._up.set_val_rank_density(rank_density)
            except ValueError:
                return simics.Sim_Set_Illegal_Value

    # ecc width
    class ecc_width(memory_module_comp.ecc_width):
        '''The error correction width.'''
        def getter(self):
            return (0, 8)[((self._up.byte[8] >> 3) & 0x1) == 1]

        def setter(self, val):
            if not val in (0, 8):
                return simics.Sim_Set_Illegal_Value
            self._up.byte[8] &= ~(0x3 << 3)
            self._up.byte[8] |= (val == 8) << 3

    # banks
    class banks(memory_module_comp.banks):
        '''Number of banks.'''
        def getter(self):
            return 8 << ((self._up.byte[4] >> 4) & 0x7)

    def set_val_banks(self, val):
        self.byte[4] &= ~(0x7 << 4)
        self.byte[4] |= ((val.bit_length() - 4) & 0x7) << 4

    class module_type(memory_module_comp.module_type):
        '''Type of memory.'''
        def getter(self):
            module_types = {
                0 : 'undefined',
                1 : 'RDIMM',
                2 : 'UDIMM',
                3 : 'SO-DIMM',
                4 : 'Micro-DIMM',
                5 : 'Mini-RDIMM',
                6 : 'Mini-UDIMM'}
            module_type = self._up.byte[3] & 0xf
            return module_types.get(module_type, 'unknown')

        def setter(self, val):
            module_types = {
                'RDIMM'      : 1,
                'UDIMM'      : 2,
                'SO-DIMM'    : 3,
                'Micro-DIMM' : 4,
                'Mini-RDIMM' : 5,
                'Mini-UDIMM' : 6}
            if not val in module_types:
                return simics.Sim_Set_Illegal_Value

            self._up.byte[3] &= ~0xf
            self._up.byte[3] |= module_types[val] & 0xf

    class cas_latency(memory_module_comp.cas_latency):
        '''CAS-latency; each set bit corresponds to a latency
        the memory can handle.'''
        def getter(self):
            return self._up.byte[15] << 8 | self._up.byte[14]

        def setter(self, val):
            self._up.byte[15] = (val >> 8) & 0xff
            self._up.byte[14] = val & 0xff

class sdram_memory_module_comp(sdram_to_ddr2_base_comp):
    '''The "sdram-memory-module-comp" component represents a SDRAM memory module.'''
    _class_desc = 'a SDRAM memory module'

    class basename(sdram_to_ddr2_base_comp.basename):
        val = 'sdram_memory'

    rank_density_val = {
        0x01 :   4,
        0x02 :   8,
        0x04 :  16,
        0x08 :  32,
        0x10 :  64,
        0x20 : 128,
        0x40 : 256,
        0x80 : 512}

    def _initialize(self):
        sdram_to_ddr2_base_comp._initialize(self)

        self.byte[2]  = 0x04 # Fundamental Memory Type (FPM EDO SDRAM DDR DDR2)
        self.byte[5]  = 0x01 # Number of DIMM Ranks
        self.byte[8]  = 0x05 # Voltage Interface Level of this assembly
        self.byte[17] = 0x04 # SDRAM Device Attr: Nbr of Banks on SDRAM Device
        self.byte[18] = 0x06 # SDRAM Device Attributes: CAS Latency
        self.byte[31] = 0x10 # Module Rank (ROW) Density

    class banks(sdram_to_ddr2_base_comp.banks):
        '''Number of banks.'''

    class cas_latency(sdram_to_ddr2_base_comp.cas_latency):
        '''CAS-latency; each set bit corresponds to a latency
        the memory can handle.'''
        def getter(self):
            return self._up.byte[18]
        def setter(self, val):
            self._up.byte[18] = val & 0xff
            self._up.byte[127] &= ~0x06
            self._up.byte[127] |= val & 0x06

    class columns(sdram_to_ddr2_base_comp.columns):
        '''Number of columns.'''

    class ecc_width(sdram_to_ddr2_base_comp.ecc_width):
        '''The error correction width.'''

    class module_data_width(sdram_to_ddr2_base_comp.module_data_width):
        '''The module SDRAM width (including ECC width if enabled).'''

    class primary_width(sdram_to_ddr2_base_comp.primary_width):
        '''Primary SDRAM width.'''

    class rows(sdram_to_ddr2_base_comp.rows):
        '''Number of rows.'''

    class ranks(sdram_to_ddr2_base_comp.ranks):
        '''Number of ranks (logical banks).'''
        def getter(self):
            return self._up.byte[5]

    def set_val_ranks(self, val):
        self.byte[5] = val

    class rank_density(sdram_to_ddr2_base_comp.rank_density):
        '''The rank density.'''
        def getter(self):
            assert self._up.byte[31] in self._up.rank_density_val
            return self._up.rank_density_val[self._up.byte[31]]

    def set_val_rank_density(self, val):
        assert val in list(self.rank_density_val.values())
        for rank in self.rank_density_val:
            if self.rank_density_val[rank] == val:
                self.byte[31] = rank
                return

    class module_type(sdram_to_ddr2_base_comp.module_type):
        '''Type of memory.'''
        def getter(self):
            if self._up.byte[21] & 0x26:
                return "RDIMM"
            else:
                return "UDIMM"

        def setter(self, val):
            if val == "RDIMM":
                self._up.byte[21] |= 0x26
            elif val == "UDIMM":
                self._up.byte[21] &= ~0x26
            else:
                return simics.Sim_Set_Illegal_Value
