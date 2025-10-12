# © 2017 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import multiproc_test

def tests(suite):
    suite.add_simics_tests('s-*.py')
    multiproc_test.add_multiproc_test(suite, 'cable-on-multi-processes.py', 2)
    multiproc_test.add_multiproc_test(suite, 'link-multiproc.py', 2)
