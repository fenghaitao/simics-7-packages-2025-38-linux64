# © 2013 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# tb_lan.py

# Search for unit-tests from intel-e1000
import simics
import dev_util
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "intel-e1000"))

# Import common testbench definitions for all devices that derive from intel-e1000
from test.tb_lan_common import *

# Device specific definitions
reta_bf  = Bitfield_LE_Ex({
        'CI'        : (7,4),   # CPU Index (Reserved)
        'QI'        : (3, 0),  # Queue Index
        })

# Define instantiation function for device i210
def Instantiate_i210_v2(tb):
    # i210 GbE MAC controller
    lan = simics.pre_conf_object('lan', 'i210_v2')
    lan.flash = tb.flash_ram
    lan.phy_address = PHY_ADDRESS
    lan.eth_phy = tb.phy
    lan.mii = tb.mii
    lan.queue = tb.sys_clk
    simics.SIM_add_configuration([lan], None)
    lan = simics.SIM_get_object(lan.name)
    lan.iface.pcie_device.connected(tb.pci, 0)

    tb.pcie_config = dev_util.bank_regs(lan.bank.pcie_config)
    tb.pcie_config.command.write(dev_util.READ, m=1)

# Instantiate for this device
tb = TestBench(Instantiate_i210_v2, use_legacy_pci_library=False)
lan_drv = IchLanDriver(tb, ICH9_LAN_REG_BASE)

tb.rss_multi_processors_supported = False
