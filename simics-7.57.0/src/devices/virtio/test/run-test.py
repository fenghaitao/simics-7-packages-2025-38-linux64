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

import testparams

testparams.add_subtests("s-info-status.py")
testparams.add_subtests("s-virtio-blk.py")
if not testparams.is_windows():
    testparams.add_subtests("s-virtio-fs.py")
testparams.add_subtests("s-virtio-net.py")
testparams.add_subtests("s-virtio-pcie-blk.py")
testparams.add_subtests("s-virtio-entropy.py")
