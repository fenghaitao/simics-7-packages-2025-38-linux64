# © 2023 Intel Corporation
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
import sample_pcie_endpoint_common
import stest
import dev_util


def test_msix(dev, bar_mapped_bank, pcie_config):
    bar_mapped_bank.hello_world.write(1)
    with stest.expect_log_mgr(
        log_type="info", msg="can't raise MSI-X 1, MSI-X disabled"
    ):
        sample_pcie_endpoint_common.run_seconds(1)

    pcie_config.msix.control.write(dev_util.READ, enable=1)

    bar_mapped_bank.hello_world.write(1)
    with stest.expect_log_mgr(log_type="info", msg="raise MSI-X 1 @ 0x0 <= 0x0"):
        sample_pcie_endpoint_common.run_seconds(1)


def main():
    dev = sample_pcie_endpoint_common.create_sample_pcie_device("dev")
    up = sample_pcie_endpoint_common.create_fake_upstream_target("up")
    dev.iface.pcie_device.connected(up, 0)

    pcie_config = dev_util.bank_regs(dev.bank.pcie_config)
    bar_mapped_bank = dev_util.bank_regs(dev.bank.bar_mapped_bank)

    dev.bank.pcie_config.log_level = 2
    pcie_config.command.write(dev_util.READ, m=1)
    test_msix(dev, bar_mapped_bank, pcie_config)


main()
