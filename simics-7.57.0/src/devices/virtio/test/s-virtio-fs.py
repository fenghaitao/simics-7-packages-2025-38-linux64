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

import struct

import simics
import stest
import virtio_common

fuse_in_header_fmt = '<IIQQIIII'
fuse_out_header_fmt = '<IiQ'


class VirtioFuseMock:
    cls = simics.confclass('fuse-mock')

    # Keep a reference to the buffer_t to prevent double free
    res_buffer = None

    @cls.iface.virtiofs_fuse.handle_request
    def handle_request(self, req):
        response_payload = struct.pack(fuse_out_header_fmt,
                                       struct.calcsize(fuse_out_header_fmt) +
                                       len(b'The response'), 0, 0)

        self.res_buffer = simics.buffer_t(response_payload + b'The response')
        return self.res_buffer


def test_tag(dev: virtio_common.VirtioDevicePCIE, expected_tag: str):
    tag_name = []
    for i in range(36):
        tag_char = dev.virtio_config_regs.device_specific.tag[i].read()
        if tag_char == 0:
            break
        tag_name.append(tag_char)
    stest.expect_equal(''.join(map(chr, tag_name)), expected_tag)


def test_request(dev: virtio_common.VirtioDevicePCIE, ram_img: simics.conf_object_t):
    fuse_mock = simics.SIM_create_object('fuse-mock', 'fuse')
    dev.dev_obj.chan = fuse_mock

    virtq = dev.queues[1]
    buffers = []

    request_payload = struct.pack(fuse_in_header_fmt,
                                  struct.calcsize(fuse_in_header_fmt) +
                                  len(b'The request'), 0, 0, 0, 0, 0, 0, 0)

    # Request
    offset = dev.queues_mem_end
    buffers.append({
        'addr': offset,
        'len': struct.calcsize(fuse_in_header_fmt),
        'flags': virtio_common.VIRTQ_DESC_F_NEXT
    })
    virtio_common.write_ram(ram_img, buffers[0]['addr'], request_payload)

    offset += buffers[0]['len']
    buffers.append({
        'addr': offset,
        'len': len(b'The request'),
        'flags': virtio_common.VIRTQ_DESC_F_NEXT
    })
    virtio_common.write_ram(ram_img, buffers[1]['addr'], b'The request')

    # Response
    offset += buffers[1]['len']
    buffers.append({
        'addr': offset,
        'len': struct.calcsize(fuse_out_header_fmt) + len(b'The response'),
        'flags': virtio_common.VIRTQ_DESC_F_WRITE
    })

    virtq.give_buffers(buffers)
    dev.notify(1)

    stest.expect_equal(virtio_common.read_ram(ram_img,
        buffers[2]['addr'] + struct.calcsize(fuse_out_header_fmt),
        len(b'The response')), b'The response')


def run_tests():
    tag_name = 'Hello World!'
    dev_objects = virtio_common.create_virtio_pcie_fs(tag_name=tag_name)
    ram_img = simics.SIM_create_object("image", "test_image", size=32768)
    ram = simics.SIM_create_object("ram", "test_ram", image=ram_img)
    dev = virtio_common.VirtioDevicePCIE(dev_objects['obj'], ram_img)

    dp = simics.SIM_create_object("pcie-downstream-port", "test_dp")
    dp.upstream_target = ram
    dp.devices = [[0, dev_objects["obj"]]]

    dev.init_device(2)

    test_tag(dev, tag_name)
    test_request(dev, ram_img)


run_tests()
