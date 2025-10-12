# © 2012 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import stest
import conf

# SIMICS-21634
conf.sim.deprecation_level = 0

# Create a sample PCI express device
pcie = SIM_create_object('sample_pcie_device_old', 'sample_pcie_dev')
pcie_iface = pcie.iface.pci_express

# Check that the device is considered a PCIE device
def test_pcie():
    stest.expect_equal(pcie.attr.is_pcie_device, True)

# Test sending messages on the PCIE interface
def test_message():
    pcie_iface.send_message(pcie, PCIE_HP_Power_Indicator_On, "")
    stest.expect_equal(pcie.attr.power_indicator, "ON")

    pcie_iface.send_message(pcie, PCIE_HP_Attention_Indicator_Blink, "")
    stest.expect_equal(pcie.attr.attention_indicator, "BLINK")


test_pcie()
test_message()

print("All tests passed.")
