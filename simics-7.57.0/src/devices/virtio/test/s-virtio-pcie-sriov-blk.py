# © 2025 Intel Corporation
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
import dev_util
import virtio_common
import blk_test_common

N_VIRTUAL_FUNCTIONS = 5


def test_enable_virtual_functions_before_feature_negotiation(
    pf: virtio_common.VirtioDevicePCIE,
):
    pf.pcie_config_regs.sriov.control.write(dev_util.READ, vfe=0)
    pf.pcie_config_regs.sriov.num_vfs.write(5)
    with stest.expect_log_mgr(
        log_type="spec-viol",
        regex="Trying to enable SR-IOV without the VIRTIO_F_SR_IOV feature being negotiated",
    ):
        pf.pcie_config_regs.sriov.control.write(dev_util.READ, vfe=1)


def test_enable_virtual_functions_after_feature_negotiation(
    pf: virtio_common.VirtioDevicePCIE,
):
    pf.pcie_config_regs.sriov.control.write(dev_util.READ, vfe=0)
    pf.pcie_config_regs.sriov.num_vfs.write(5)
    pf.pcie_config_regs.sriov.control.write(dev_util.READ, vfe=1)


def run_tests():
    ram_img = simics.SIM_create_object(
        "image", "test_image", size=16384 * (N_VIRTUAL_FUNCTIONS + 1)
    )
    ram = simics.SIM_create_object("ram", "test_ram", image=ram_img)
    dev_objects = virtio_common.create_virtio_pcie_sriov_blk()

    pf = virtio_common.VirtioDevicePCIE(dev_objects["obj"].PF, ram_img)
    pf.dev_obj.cli_cmds.log_level(level=3, _r=True)
    pf.dev_obj.bank.pcie_config.cli_cmds.log_level(level=1)
    vfs = [
        virtio_common.VirtioPCIEVirtualFunction(
            dev_objects["obj"].VF[i], ram_img, 16384 * (i + 1)
        )
        for i in range(0, N_VIRTUAL_FUNCTIONS)
    ]

    dp = simics.SIM_create_object("pcie-downstream-port", "test_dp")
    dp.upstream_target = ram
    dp.devices = [[0, dev_objects["obj"]]]

    test_enable_virtual_functions_before_feature_negotiation(pf)

    expected_status = (
        virtio_common.VIRTIO_STATUS_ACKNOWLEDGE
        | virtio_common.VIRTIO_STATUS_DRIVER
        | virtio_common.VIRTIO_STATUS_FEATURES_OK
        | virtio_common.VIRTIO_STATUS_DRIVER_OK
    )
    with stest.expect_log_mgr(
        log_type="info",
        regex=r"Feature VIRTIO_F_SR_IOV \(feature bit 37\) has been enabled",
    ):
        stest.expect_equal(
            pf.init_device(
                expected_device_features=(1 << virtio_common.VIRTIO_F_VERSION_1)
                | (1 << virtio_common.VIRTIO_F_ACCESS_PLATFORM)
                | (1 << virtio_common.VIRTIO_F_SR_IOV)
            ),
            expected_status,
        )
    test_enable_virtual_functions_after_feature_negotiation(pf)

    blk_test_common.run_common_tests(pf, ram_img, dev_objects["images"][0], dp)

    pf.pcie_config_regs.sriov.vf_bar_01.write(-1)
    bar_read = pf.pcie_config_regs.sriov.vf_bar_01.read()
    stest.expect_equal(
        bar_read & 0xF,
        0xC,
        "BAR0 is expected to have a memory space indicator, be 64 bits and be preferable",
    )
    stest.expect_equal(
        bar_read & 0xFFFFFFFFFFFFFFF0,
        0xFFFFFFFFFFFFC000,
        "BAR0 is expected to have 14 size bits",
    )
    pf.pcie_config_regs.sriov.vf_bar_01.write(0x60000)
    pf.pcie_config_regs.sriov.control.write(dev_util.READ, vfmse=1)
    for i, (vf, image) in enumerate(zip(vfs, dev_objects["images"][1:])):
        vf.dev_obj.cli_cmds.log_level(level=3, _r=True)
        vf.dev_obj.bank.pcie_config.cli_cmds.log_level(level=1)
        stest.expect_equal(
            vf.init_device(
                expected_device_features=(1 << virtio_common.VIRTIO_F_VERSION_1)
                | (1 << virtio_common.VIRTIO_F_ACCESS_PLATFORM)
            ),
            expected_status,
        )
        blk_test_common.run_common_tests(vf, ram_img, image, dp, 0x60000 + (i * 0x4000))


run_tests()
