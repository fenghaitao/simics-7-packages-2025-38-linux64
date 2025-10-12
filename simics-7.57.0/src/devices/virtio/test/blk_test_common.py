# © 2024 Intel Corporation
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

import struct


VIRTIO_BLK_T_IN = 0
VIRTIO_BLK_T_OUT = 1
VIRTIO_BLK_T_FLUSH = 4
VIRTIO_BLK_T_GET_ID = 8
VIRTIO_BLK_T_DISCARD = 11
VIRTIO_BLK_T_WRITE_ZEROES = 13

VIRTIO_BLK_S_OK = b'\x00'
VIRTIO_BLK_S_IOERR = b'\x01'
VIRTIO_BLK_S_UNSUPP = b'\x02'

CAPABILITIES_OFFSET = 0x40
SECTOR_SIZE = 512


def test_pcie_configuration_space(dev: virtio_common.VirtioDevicePCIE):
    if (isinstance(dev, virtio_common.VirtioPCIEVirtualFunction)):
        stest.expect_equal(dev.pcie_config_regs.vendor_id.read(), 0xFFFF)
        stest.expect_equal(dev.pcie_config_regs.device_id.read(), 0xFFFF)
    else:
        stest.expect_equal(dev.pcie_config_regs.vendor_id.read(), 0x1AF4)
        stest.expect_equal(dev.pcie_config_regs.device_id.read(), 0x1042)
        stest.expect_equal(dev.pcie_config_regs.revision_id.read() >= 0x01, True)
        stest.expect_equal(dev.pcie_config_regs.subsystem_id.read() >= 0x40, True)


def test_enable_bad_feature_bit(dev: virtio_common.VirtioDevicePCIE):
    dev.virtio_config_regs.common_config.driver_feature_select.write(0)
    with stest.expect_log_mgr(
        log_type="spec-viol",
        regex=r"Trying to enable unsupported feature VIRTIO_BLK_F_SIZE_MAX \(feature bit 1\)",
    ):
        dev.virtio_config_regs.common_config.driver_feature.write(0b10)


def test_capability_mappings(
    dev: virtio_common.VirtioDevicePCIE,
    dp: simics.conf_object_t,
    img_size: int,
    bar_mem_offset,
):
    num_queues = bar_mapped_memory(
        dp, dev.virtio_config_regs.common_config.num_queues.offset, 2, bar_mem_offset
    )
    stest.expect_equal(num_queues.read(), 1)

    capacity = bar_mapped_memory(
        dp, dev.virtio_config_regs.device_specific.capacity.offset, 8, bar_mem_offset
    )
    stest.expect_equal(capacity.read(), img_size / SECTOR_SIZE)


def test_get_id_request(
    dev: virtio_common.VirtioDevicePCIE, ram_img: simics.conf_object_t
):
    virtq = dev.queues[0]
    buffers = []

    blk_req_fmt = '<LLQ'
    blk_req = struct.pack(blk_req_fmt, VIRTIO_BLK_T_GET_ID, 0, 0)

    # Request
    offset = dev.queues_mem_end
    buffers.append({
        'addr': offset,
        'len': struct.calcsize(blk_req_fmt),
        'flags': virtio_common.VIRTQ_DESC_F_NEXT
    })
    virtio_common.write_ram(ram_img, buffers[0]['addr'], blk_req)

    # Id
    offset += buffers[0]['len']
    buffers.append({
        'addr': offset,
        'len': 20,
        'flags': (virtio_common.VIRTQ_DESC_F_NEXT |
                  virtio_common.VIRTQ_DESC_F_WRITE)
    })

    # Status response buffer
    offset += buffers[1]['len']
    buffers.append({
        'addr': offset,
        'len': 1,
        'flags': virtio_common.VIRTQ_DESC_F_WRITE
    })
    offset += buffers[2]['len']

    head_desc_idx = virtq.give_buffers(buffers)
    dev.notify(0)
    stest.expect_equal(dev.validate_msix_status(1), True)

    id = virtio_common.read_ram(ram_img, buffers[1]['addr'], 20)
    stest.expect_equal(id, "Simics Virtio Block\0".encode())

    stest.expect_equal(virtio_common.read_ram(ram_img, buffers[2]['addr'], 1), VIRTIO_BLK_S_OK)

    used_id, used_len = virtq.last_used_buffers()
    stest.expect_equal(used_id, head_desc_idx)
    stest.expect_equal(used_len, 1)


def test_write_request(dev: virtio_common.VirtioDevicePCIE,
                       ram_img: simics.conf_object_t,
                       disk_img_iface: simics.image_interface_t,
                       to_write: bytes):
    virtq = dev.queues[0]
    buffers = []

    blk_req_fmt = '<LLQ'
    blk_req = struct.pack(blk_req_fmt, VIRTIO_BLK_T_OUT, 0, 0)

    # Request
    offset = dev.queues_mem_end
    buffers.append({
        'addr': offset,
        'len': struct.calcsize(blk_req_fmt),
        'flags': virtio_common.VIRTQ_DESC_F_NEXT
    })
    virtio_common.write_ram(ram_img, buffers[0]['addr'], blk_req)

    # Data
    offset += buffers[0]['len']
    buffers.append({
        'addr': offset,
        'len': SECTOR_SIZE,
        'flags': virtio_common.VIRTQ_DESC_F_NEXT
    })
    # Write dummy data to request
    virtio_common.write_ram(ram_img, buffers[1]['addr'], to_write)

    # Status response buffer
    offset += buffers[1]['len']
    buffers.append({
        'addr': offset,
        'len': 1,
        'flags': virtio_common.VIRTQ_DESC_F_WRITE
    })

    offset += buffers[2]['len']

    head_desc_idx = virtq.give_buffers(buffers)
    dev.notify(0)
    stest.expect_equal(dev.validate_msix_status(1), True)

    stest.expect_equal(disk_img_iface.get(0, 6), to_write)

    stest.expect_equal(virtio_common.read_ram(ram_img, buffers[2]['addr'], 1), VIRTIO_BLK_S_OK)

    used_id, used_len = virtq.last_used_buffers()
    stest.expect_equal(used_id, head_desc_idx)
    stest.expect_equal(used_len, 1)


def test_invalid_request(dev: virtio_common.VirtioDevicePCIE,
                         ram_img: simics.conf_object_t):
    virtq = dev.queues[0]
    buffers = []

    blk_req_fmt = '<LLQ'
    blk_req = struct.pack(blk_req_fmt, 1234, 0, 0)

    # Request
    offset = dev.queues_mem_end
    buffers.append({
        'addr': offset,
        'len': struct.calcsize(blk_req_fmt),
        'flags': virtio_common.VIRTQ_DESC_F_NEXT
    })
    virtio_common.write_ram(ram_img, buffers[0]['addr'], blk_req)

    # Status response buffer
    offset += buffers[0]['len']
    buffers.append({
        'addr': offset,
        'len': 1,
        'flags': virtio_common.VIRTQ_DESC_F_WRITE
    })
    offset += buffers[1]['len']

    head_desc_idx = virtq.give_buffers(buffers)
    dev.notify(0)
    stest.expect_equal(dev.validate_msix_status(1), True)

    stest.expect_equal(virtio_common.read_ram(ram_img, buffers[1]["addr"], 1), VIRTIO_BLK_S_UNSUPP)

    used_id, used_len = virtq.last_used_buffers()
    stest.expect_equal(used_id, head_desc_idx)
    stest.expect_equal(used_len, 1)


def test_read_request(dev: virtio_common.VirtioDevicePCIE,
                      ram_img: simics.conf_object_t):
    virtq = dev.queues[0]
    buffers = []

    blk_req_fmt = '<LLQ'
    blk_req = struct.pack(blk_req_fmt, VIRTIO_BLK_T_IN, 0, 0)

    # Request
    offset = dev.queues_mem_end
    buffers.append({
        'addr': offset,
        'len': struct.calcsize(blk_req_fmt),
        'flags': virtio_common.VIRTQ_DESC_F_NEXT
    })
    virtio_common.write_ram(ram_img, buffers[0]['addr'], blk_req)

    # Data
    offset += buffers[0]['len']
    buffers.append({
        'addr': offset,
        'len': SECTOR_SIZE,
        'flags': virtio_common.VIRTQ_DESC_F_NEXT | virtio_common.VIRTQ_DESC_F_WRITE
    })

    # Status response buffer
    offset += buffers[1]['len']
    buffers.append({
        'addr': offset,
        'len': 1,
        'flags': virtio_common.VIRTQ_DESC_F_WRITE
    })

    offset += buffers[2]['len']

    head_desc_idx = virtq.give_buffers(buffers)
    virtq.disable_interrupt_response()
    dev.notify(0)
    stest.expect_equal(dev.validate_msix_status(1), False)
    virtq.enable_interrupt_response()

    stest.expect_equal(virtio_common.read_ram(ram_img, buffers[1]['addr'], 6), b'simics')

    stest.expect_equal(virtio_common.read_ram(ram_img, buffers[2]['addr'], 1), VIRTIO_BLK_S_OK)

    used_id, used_len = virtq.last_used_buffers()
    stest.expect_equal(used_id, head_desc_idx)
    stest.expect_equal(used_len, SECTOR_SIZE + 1)


def test_wrap_used_idx(dev: virtio_common.VirtioDevicePCIE,
                       ram_img: simics.conf_object_t,
                       disk_img_iface: simics.image_interface_t):
    for _ in range(dev.queues[0].queue_size + 1):
        test_write_request(dev, ram_img, disk_img_iface, b'simics')


def test_virtq_reset(uut: simics.conf_object_t):
    virtq_attrs = [attr[0] for attr in uut.attributes if attr[0].startswith('virtqs_')]

    # read POR state and modify state from POR
    por_state = []
    for virtq_attr in virtq_attrs:
        attr_l = getattr(uut, virtq_attr)
        for i in range(len(attr_l)):
            por_state.append(attr_l[i])
            attr_l[i] = attr_l[i] + 42
        setattr(uut, virtq_attr, attr_l)

    # Read back state and verify state is changed from POR state
    changed_state = []
    for virtq_attr in virtq_attrs:
        attr_l = getattr(uut, virtq_attr)
        for i in range(len(attr_l)):
            changed_state.append(attr_l[i])
    stest.expect_equal(any(por_state[i] == changed_state[i] for i in range(len(por_state))),
                       False)

    # trigger reset
    uut.port.HRESET.iface.signal.signal_raise()
    uut.port.HRESET.iface.signal.signal_lower()

    # get state after HRESET and ensure it matches POR state
    changed_state = []
    for virtq_attr in virtq_attrs:
        attr_l = getattr(uut, virtq_attr)
        for i in range(len(attr_l)):
            changed_state.append(attr_l[i])
    stest.expect_equal(all(por_state[i] == changed_state[i] for i in range(len(por_state))),
                       True)

def device_specific_setup(dev: virtio_common.VirtioDevicePCIE):
    pass

def bar_mapped_memory(
    dp: simics.conf_object_t, offset: int, size: int, bar_mem_offset: int = 0
) -> dev_util.Register_LE:
    # 0x50000 is the value written to the BAR register in the VirtioDevicePCIE
    return dev_util.Register_LE(dp.mem_space, offset + bar_mem_offset, size)


def run_common_tests(
    dev: virtio_common.VirtioDevicePCIE,
    ram_img: simics.conf_object_t,
    disk_img: simics.conf_object_t,
    dp: simics.conf_object_t,
    bar_mem_offset: int = 0x50000
):
    test_pcie_configuration_space(dev)
    test_enable_bad_feature_bit(dev)
    test_capability_mappings(dev, dp, disk_img.size, bar_mem_offset)
    # To verify wrap around used buffer
    if type(dev) is not virtio_common.VirtioPCIEVirtualFunction:
        dev.dev_obj.virtqs_avail_ring_idx = [65535]
    test_get_id_request(dev, ram_img)
    test_write_request(
        dev, ram_img, disk_img.iface.image, b"virtio"
    )
    test_invalid_request(dev, ram_img)
    test_wrap_used_idx(dev, ram_img, disk_img.iface.image)
    test_read_request(dev, ram_img)
    if type(dev) is not virtio_common.VirtioPCIEVirtualFunction:
        test_virtq_reset(
            virtio_common.create_virtio_pcie_blk()["obj"]
        )  # fresh object needed for POR state
