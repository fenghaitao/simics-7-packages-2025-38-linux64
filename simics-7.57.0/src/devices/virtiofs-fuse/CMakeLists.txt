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

if(WIN32)
    # Only build FUSE interface for Windows
    # NOTE: files are *not* even distributed on Windows
    simics_add_module(virtiofs-fuse
        INTERFACES virtiofs_fuse
        SOURCES virtiofs-fuse-interface.h
        SIMICS_API 6
    )
else()
    simics_add_module(virtiofs-fuse
        CLASSES virtiofs_fuse
        SOURCES virtiofs-fuse.c module_load.py virtiofs-fuse-interface.h
        INTERFACES virtiofs_fuse
        INIT_LOCAL
        SIMICS_API 6
    )

    simics_add_sanitizers(virtiofs-fuse)

    add_subdirectory(test)
endif()
