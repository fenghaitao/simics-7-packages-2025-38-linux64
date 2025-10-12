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

if(SIMICS_ENABLE_TESTS_FROM_PACKAGES)
  simics_test_suite_begin()
    # Sanitizer reports failure:
    # Direct leak of 320 byte(s) in 1 object(s) allocated from:
    #0 0x7ff9244b7adb in calloc (/nfs/itm/tools/SLES15SP4-x86_64/conan_build_deps/7.16/gcc-15.1.0/bin/../lib/gcc/x86_64-pc-linux-gnu/15.1.0/../../../../lib64/libasan.so+0x13badb)
    #1 0x7bf921c21007 in lowlevel_zalloc /disk3/xiuliang/6-repo/core/src/core/util/simmalloc.c:330
    #2 0x7bf9204fdff0 in grow_allocation /disk3/xiuliang/6-repo/core/src/core/clock/queue.c:56
    simics_add_test(ats)

    simics_add_test(ats-direct-memory LABELS "sanitizer")
    simics_add_test(prs LABELS "sanitizer")
  simics_test_suite_end()
endif()
