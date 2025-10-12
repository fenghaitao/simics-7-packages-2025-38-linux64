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


# tb_lan.py

# Search for unit-tests from intel-e1000
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "intel-e1000"))
import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

# Import common testbench definitions for all devices that derive from intel-e1000
from test.tb_lan_common import *

# Define instantiation function for device i82583v_v2
def Instantiate_i82583V_v2(tb):
    # i82583v GbE MAC controller
    lan = simics.pre_conf_object('lan', 'i82583V_v2')
    #lan.chipset_config = [tb.lpc, 'cs_conf']
    lan.pci_config_command = 0x4    # BME
    lan.flash = tb.flash_ram
    lan.flash_func = 0
    lan.phy_address = PHY_ADDRESS
    lan.phy = tb.phy
    lan.mii = tb.mii
    #lan.aes_gcm = [tb.aes_eng, 'gcm']
    #lan.irq_dev = [tb.pdev, "intr_pin"]
    #lan.irq_level = 13
    lan.pci_bus = tb.pci
    lan.queue = tb.sys_clk
    simics.SIM_add_configuration([lan], None)

# Instantiate for this device
tb = TestBench(Instantiate_i82583V_v2)
lan_drv = IchLanDriver(tb, ICH9_LAN_REG_BASE)

tb.jumbo_frames_supported = False
