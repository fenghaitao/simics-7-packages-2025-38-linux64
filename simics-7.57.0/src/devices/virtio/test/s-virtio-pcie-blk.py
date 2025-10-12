# © 2022 Intel Corporation
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

import stest
import virtio_common

import blk_test_common


def run_tests():
    ram_img = simics.SIM_create_object("image", "test_image", size=16384)
    ram = simics.SIM_create_object("ram", "test_ram", image=ram_img)
    dev_objects = virtio_common.create_virtio_pcie_blk()

    dev = virtio_common.VirtioDevicePCIE(dev_objects["obj"], ram_img)

    dp = simics.SIM_create_object("pcie-downstream-port", "test_dp")
    dp.upstream_target = ram
    dp.devices = [[0, dev_objects["obj"]]]

    dev.dev_obj.cli_cmds.log_level(level=3, _r=True)
    dev.dev_obj.bank.pcie_config.cli_cmds.log_level(level=1)

    expected_status = (
        virtio_common.VIRTIO_STATUS_ACKNOWLEDGE
        | virtio_common.VIRTIO_STATUS_DRIVER
        | virtio_common.VIRTIO_STATUS_FEATURES_OK
        | virtio_common.VIRTIO_STATUS_DRIVER_OK
    )
    stest.expect_equal(dev.init_device(1), expected_status)
    # Ensure that reset works properly
    dp.iface.pcie_port_control.hot_reset()
    stest.expect_equal(
        dev.init_device(1, blk_test_common.device_specific_setup), expected_status
    )

    blk_test_common.run_common_tests(dev, ram_img, dev_objects['image'], dp)


run_tests()
