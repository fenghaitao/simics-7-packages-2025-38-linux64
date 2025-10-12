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
from cdrom_common import *

def test_capacity(test_file, test_file_size):
    # Verify that file size is as expected
    stest.expect_equal(VT_logical_file_size(test_file), test_file_size)

    cdrom = create_simple(test_file)
    cdrom.iface.cdrom_media.insert()

    # ISO Image must have a size divisible by 2048, which is the capacity
    file_cap = test_file_size // 2048
    cap = cdrom.iface.cdrom_media.capacity()
    stest.expect_equal(cap, file_cap)

def test_not_iso():
    # Test to set the image to a non-ISO type image (i.e., size not
    # divisible by 2048). A SimExc_IllegalValue should be raised and
    # capacity should return as zero.
    test_file = 'not-an-iso.iso'
    not_iso_img = SIM_create_object('image', 'noiso',
                                    [['size', VT_logical_file_size(test_file)],
                                     ['files', [[test_file, 'ro', 0, 0]]]])
    cdrom = SIM_create_object('cdrom_image', 'not_an_iso')

    with stest.expect_exception_mgr(SimExc_IllegalValue):
        with stest.expect_log_mgr(cdrom):
            cdrom.image = not_iso_img

    cdrom.iface.cdrom_media.insert()
    cap = cdrom.iface.cdrom_media.capacity()
    stest.expect_equal(cap, 0)

test_capacity(simple_cd_test_file, 372736)

#Bug 19999 - [cdrom-image] Broken size check for large (>4GB) images
test_capacity('large-empty-iso.craff', 0x140000000)

test_not_iso()
