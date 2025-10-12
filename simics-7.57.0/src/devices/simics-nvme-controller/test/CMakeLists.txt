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

if(SIMICS_ENABLE_TESTS_FROM_PACKAGES)
  simics_add_test(info-status LABELS "sanitizer")
  # Sanitizer reports failure:
  # Direct leak of 80 byte(s) in 2 object(s) allocated from:
  #0 0x7f3c4eeebadb in calloc (/nfs/itm/tools/SLES15SP4-x86_64/conan_build_deps/7.16/gcc-15.1.0/bin/../lib/gcc/x86_64-pc-linux-gnu/15.1.0/../../../../lib64/libasan.so+0x13badb)
  #1 0x7f3c4dc37007 in lowlevel_zalloc /disk3/xiuliang/6-repo/core/src/core/util/simmalloc.c:330
  #2 0x7b3c4af2cf71 in alloc_spage_struct /disk3/xiuliang/6-repo/core/src/core/common/image.c:817
  simics_add_test(nvme)
endif()
