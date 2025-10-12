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

def set_image_and_test_expected_exception(image):
    try:
        cdrom.image = image
        raise stest.TestFailure("Should not be able to set image attribute when"
                                + " CD-ROM is in use")
    except SimExc_IllegalValue:
        pass     # Expected

test_file = simple_cd_test_file
cdrom = create_simple(test_file)

# Newly created media is unused
stest.expect_false(cdrom.in_use)

# Eject fresh media should give error
with stest.allow_log_mgr(cdrom):
    cdrom.iface.cdrom_media.eject()

# Inserting media makes it used
r = cdrom.iface.cdrom_media.insert()
stest.expect_equal(r, 0)
stest.expect_true(cdrom.in_use)

# Test that we can only insert meda once
with stest.allow_log_mgr(cdrom):
    r = cdrom.iface.cdrom_media.insert()
    stest.expect_equal(r, -1)

# Eject media should cause it to be unused
cdrom.iface.cdrom_media.eject()
stest.expect_false(cdrom.in_use)

# Eject twice should give error
with stest.allow_log_mgr(cdrom):
    cdrom.iface.cdrom_media.eject()

# Test that we can't change the image while the CD is in use (bug 20058)
cdrom = create_simple(simple_cd_test_file)
org_image = cdrom.image
new_image = image_from_file(simple_cd_test_file, 'new_image')

# Not inserted, should work just fine
cdrom.image = new_image
cdrom.image = None
cdrom.image = org_image

cdrom.iface.cdrom_media.insert()
stest.expect_true(cdrom.in_use)

# Set same image should work
cdrom.image = org_image

# Set different image should give exception
stest.untrap_log('error')
set_image_and_test_expected_exception(new_image)
set_image_and_test_expected_exception(None)
