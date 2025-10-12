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

import struct
from tempfile import TemporaryDirectory
from typing import Tuple

import simics
import stest

FUSE_OP_INIT = 26

FUSE_MAJOR_VERSION = 7
FUSE_MINOR_VERSION = 31

fuse_in_header_fmt = '<IIQQIIII'
fuse_out_header_fmt = '<IiQ'

fuse_init_in_fmt = '<IIIII44x'
fuse_init_out_fmt = '<IIIIHHIIHHI28x'

dummy_init_req_header = struct.pack(
    fuse_in_header_fmt, struct.calcsize(fuse_in_header_fmt) +
    struct.calcsize(fuse_init_in_fmt), FUSE_OP_INIT, 2, 0, 0, 0, 0, 0)
dummy_init_req_payload = struct.pack(
    fuse_init_in_fmt, FUSE_MAJOR_VERSION, FUSE_MINOR_VERSION, 0, 0, 0)
dummy_init_req = dummy_init_req_header + dummy_init_req_payload


class VirtioFuseDevice:

    def __init__(self, shared_dir=TemporaryDirectory(),
                 name='virtiofs_fuse') -> None:
        self.dev = simics.SIM_create_object(
            'virtiofs_fuse', name, share=shared_dir.name)

    def handle_request(self, data: bytes) -> Tuple[bytes, bytes]:
        response = self.dev.iface.virtiofs_fuse.handle_request(data)
        response_header = bytes(
            response)[:struct.calcsize(fuse_out_header_fmt)]
        response_payload = bytes(
            response)[struct.calcsize(fuse_out_header_fmt):]
        return (response_header, response_payload)

    def connection_established(self) -> bool:
        return self.dev.connection_established

    def socket_path(self) -> str:
        return self.dev.socket_path


def test_connectivity(dev: VirtioFuseDevice):
    stest.expect_true(dev.connection_established())

    response_header, response_payload = dev.handle_request(dummy_init_req)

    response_header_unpacked = struct.unpack_from(
        fuse_out_header_fmt, response_header)
    stest.expect_equal(response_header_unpacked[2], 2)

    response_payload_unpacked = struct.unpack(
        fuse_init_out_fmt, response_payload)
    stest.expect_equal(response_payload_unpacked[0], FUSE_MAJOR_VERSION)


def run_tests():
    virtiofs_fuse_device = VirtioFuseDevice()
    test_connectivity(virtiofs_fuse_device)


run_tests()
