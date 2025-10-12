# © 2011 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import update_checkpoint

def upgrade_flash(obj):
    # AT24C04 was replaced by AT24Cxx class, remove old attr
    if hasattr(obj, 'A2A1'):
        delattr(obj, 'A2A1')

update_checkpoint.install_class_configuration_update(
    4004, "AT24C04",
    upgrade_flash)
